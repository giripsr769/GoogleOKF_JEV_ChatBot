"""Run validated SQL on Postgres with a read-only login, a read-only transaction and a hard time limit.

Three independent locks sit under the validator: the database role can only SELECT, every query runs inside a
READ ONLY transaction, and the server cancels anything slower than the statement timeout. On top of that,
`verify()` refuses to start when the login is a superuser or can write, so a mistake in .env cannot quietly
hand the model more power than intended.

Uses synchronous psycopg inside a worker thread: psycopg's async mode does not work on Windows' default event loop.
"""
from __future__ import annotations

import asyncio
import time
from dataclasses import dataclass, field
from datetime import date, datetime, time as dtime, timedelta
from decimal import Decimal
from uuid import UUID

import psycopg
from psycopg import errors as pgerr
from psycopg import sql as pgsql


class UnsafeDatabaseRole(RuntimeError):
    """The configured database login can do more than read. Refuse to run."""


class SqlExecutionError(Exception):
    """A query failed. `retryable` means the SQL writer may fix it from the message (a wrong column name, say)."""

    def __init__(self, code: str, message: str, retryable: bool = False):
        super().__init__(message)
        self.code, self.message, self.retryable = code, message, retryable


@dataclass
class ExecResult:
    columns: list[str]
    rows: list[dict]
    row_count: int
    truncated: bool  # more rows existed than max_rows
    elapsed_ms: float


@dataclass
class RoleReport:
    user: str
    problems: list[str] = field(default_factory=list)

    @property
    def safe(self) -> bool:
        return not self.problems


def jsonable(value):
    """Convert a database value into something json.dumps accepts."""
    if isinstance(value, Decimal):
        return float(value)
    if isinstance(value, (datetime, date, dtime)):
        return value.isoformat()
    if isinstance(value, timedelta):
        return value.total_seconds()
    if isinstance(value, UUID):
        return str(value)
    if isinstance(value, (bytes, bytearray, memoryview)):
        return bytes(value).hex()
    if isinstance(value, (list, tuple)):
        return [jsonable(v) for v in value]
    if isinstance(value, dict):
        return {str(k): jsonable(v) for k, v in value.items()}
    return value


def _unique(names: list[str]) -> list[str]:
    """SELECT a.id, b.id would collapse in a dict, so the second becomes id_2."""
    seen: dict[str, int] = {}
    out = []
    for n in names:
        seen[n] = seen.get(n, 0) + 1
        out.append(n if seen[n] == 1 else f"{n}_{seen[n]}")
    return out


_SQL_ERRORS = (
    pgerr.UndefinedColumn, pgerr.UndefinedTable, pgerr.UndefinedFunction, pgerr.SyntaxError, pgerr.AmbiguousColumn,
    pgerr.DatatypeMismatch, pgerr.InvalidTextRepresentation, pgerr.DivisionByZero, pgerr.GroupingError,
    pgerr.InvalidColumnReference, pgerr.AmbiguousFunction, pgerr.CannotCoerce, pgerr.NumericValueOutOfRange,
    pgerr.InvalidDatetimeFormat, pgerr.DatetimeFieldOverflow, pgerr.InvalidParameterValue,
)


class ReadOnlyExecutor:
    def __init__(self, database_url: str, statement_timeout_ms: int = 3000, max_rows: int = 100, connect_timeout_s: int = 5):
        self.url, self.timeout_ms, self.max_rows, self.connect_timeout_s = database_url, statement_timeout_ms, max_rows, connect_timeout_s

    # ---------------------------------------------------------------- role check
    def check_role(self) -> RoleReport:
        """Inspect the login. Anything beyond reading is a problem."""
        with psycopg.connect(self.url, connect_timeout=self.connect_timeout_s) as conn:
            user, = conn.execute("SELECT current_user").fetchone()
            report = RoleReport(user)
            flags = conn.execute(
                "SELECT rolsuper, rolcreaterole, rolcreatedb, rolreplication, rolbypassrls FROM pg_roles WHERE rolname = current_user"
            ).fetchone()
            for label, on in zip(("is a superuser", "can create roles", "can create databases", "can replicate", "bypasses row security"), flags):
                if on:
                    report.problems.append(f"the login {label}")
            writable = [r[0] for r in conn.execute(
                """SELECT n.nspname || '.' || c.relname FROM pg_class c JOIN pg_namespace n ON n.oid = c.relnamespace
                   WHERE c.relkind IN ('r', 'p') AND n.nspname NOT IN ('pg_catalog', 'information_schema') AND n.nspname !~ '^pg_'
                     AND (has_table_privilege(c.oid, 'INSERT') OR has_table_privilege(c.oid, 'UPDATE')
                          OR has_table_privilege(c.oid, 'DELETE') OR has_table_privilege(c.oid, 'TRUNCATE'))
                   ORDER BY 1 LIMIT 5"""
            ).fetchall()]
            if writable:
                report.problems.append(f"the login can write to: {', '.join(writable)}")
            creates = [r[0] for r in conn.execute(
                """SELECT nspname FROM pg_namespace WHERE nspname NOT IN ('pg_catalog', 'information_schema') AND nspname !~ '^pg_'
                   AND has_schema_privilege(nspname, 'CREATE')"""
            ).fetchall()]
            if creates:
                report.problems.append(f"the login can create objects in schema: {', '.join(creates)}")
            if conn.execute("SELECT has_database_privilege(current_database(), 'CREATE')").fetchone()[0]:
                report.problems.append("the login can create schemas in this database")
            conn.rollback()
        return report

    def verify(self) -> RoleReport:
        """Raise UnsafeDatabaseRole unless the login is read-only. Call once at startup."""
        report = self.check_role()
        if not report.safe:
            raise UnsafeDatabaseRole(
                f"Refusing to use database login '{report.user}': " + "; ".join(report.problems)
                + ". Set DATABASE_URL to a SELECT-only role such as okf_readonly."
            )
        return report

    # ---------------------------------------------------------------- running queries
    async def execute(self, sql: str) -> ExecResult:
        return await asyncio.to_thread(self.run, sql)

    def run(self, sql: str) -> ExecResult:
        t0 = time.perf_counter()
        try:
            with psycopg.connect(self.url, connect_timeout=self.connect_timeout_s) as conn:
                conn.read_only = True  # BEGIN READ ONLY: writes fail even if the role somehow allowed them
                with conn.cursor() as cur:
                    cur.execute(pgsql.SQL("SET LOCAL statement_timeout = {}").format(pgsql.Literal(int(self.timeout_ms))))
                    cur.execute(pgsql.SQL("SET LOCAL lock_timeout = {}").format(pgsql.Literal(int(self.timeout_ms))))
                    cur.execute(sql)  # no params, so a literal % (LIKE '%x%') is left alone
                    columns = _unique([d.name for d in cur.description]) if cur.description else []
                    fetched = cur.fetchmany(self.max_rows + 1) if cur.description else []
                conn.rollback()
        except pgerr.QueryCanceled:
            raise SqlExecutionError("timeout", f"The query took longer than {self.timeout_ms / 1000:g} seconds and was stopped.") from None
        except pgerr.InsufficientPrivilege as exc:
            raise SqlExecutionError("permission_denied", _first_line(exc)) from None
        except pgerr.ReadOnlySqlTransaction as exc:
            raise SqlExecutionError("read_only", _first_line(exc)) from None
        except _SQL_ERRORS as exc:
            raise SqlExecutionError("sql_error", _first_line(exc), retryable=True) from None
        except psycopg.OperationalError as exc:
            raise SqlExecutionError("unavailable", f"Could not reach the database: {_first_line(exc)}") from None
        except psycopg.Error as exc:
            raise SqlExecutionError("db_error", _first_line(exc)) from None

        truncated = len(fetched) > self.max_rows
        rows = [{c: jsonable(v) for c, v in zip(columns, row)} for row in fetched[: self.max_rows]]
        return ExecResult(columns, rows, len(rows), truncated, (time.perf_counter() - t0) * 1000)


def _first_line(exc: Exception) -> str:
    diag = getattr(exc, "diag", None)
    text = (diag.message_primary if diag and diag.message_primary else str(exc)).strip()
    hint = diag.message_hint if diag and diag.message_hint else ""
    return (text + (f" ({hint})" if hint else "")).splitlines()[0][:300]
