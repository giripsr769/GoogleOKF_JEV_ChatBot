"""Decide whether a model-written SQL string is safe to run, and rewrite it into the exact text that will run.

This is the hard gate between the model and the database. It is plain code with fixed rules: a model cannot
talk it out of anything. The database role (SELECT-only, read-only transactions, a timeout) is a second, independent gate.

Rules: exactly one statement; a read-only SELECT (or UNION/INTERSECT/EXCEPT of SELECTs); no writes, DDL, SET, COPY,
EXPLAIN, SELECT INTO, row locks or FETCH anywhere in the tree; only tables the question was allowed to see, resolved by
sqlglot's scope analysis so a CTE cannot shadow a real table; no system schemas, table functions or dangerous
functions; a row limit on the outermost query. The returned SQL is regenerated from the parsed tree, so comments and
anything the parser ignored are gone: what was checked is what runs.
"""
from __future__ import annotations

from dataclasses import dataclass, field
from typing import Iterable

import sqlglot
from sqlglot import exp
from sqlglot.errors import SqlglotError
from sqlglot.optimizer.scope import traverse_scope

DIALECT = "postgres"

# Statement kinds that must not appear anywhere in the tree, including inside a CTE. Names missing from this
# sqlglot version are skipped, so an upgrade cannot crash the import.
_FORBIDDEN_NODE_NAMES = [
    "Insert", "Update", "Delete", "Merge", "Create", "Drop", "Alter", "AlterTable", "TruncateTable", "Command",
    "Set", "Copy", "Grant", "Revoke", "Use", "Transaction", "Commit", "Rollback", "Analyze", "Pragma", "LoadData",
    "Refresh", "Declare", "Execute", "Kill", "Comment",
]
FORBIDDEN_NODES = tuple(c for c in (getattr(exp, n, None) for n in _FORBIDDEN_NODE_NAMES) if isinstance(c, type))

DENIED_FUNCTIONS = {
    "set_config", "current_setting", "dblink", "dblink_exec", "query_to_xml", "table_to_xml", "database_to_xml",
    "schema_to_xml", "xpath", "txid_current", "version", "inet_server_addr", "inet_client_addr",
}
DENIED_FUNCTION_PREFIXES = ("pg_", "lo_", "dblink", "txid_")  # pg_sleep, pg_read_file, lo_import, ...
# handy for date spines, harmless; sqlglot names generate_series EXPLODING_GENERATE_SERIES in the Postgres dialect
ALLOWED_TABLE_FUNCTIONS = {"generate_series", "exploding_generate_series"}


@dataclass
class SqlCheck:
    ok: bool
    sql: str = ""  # the statement to run: regenerated from the parsed tree, with the row limit applied
    tables: list[str] = field(default_factory=list)  # physical tables the statement reads
    code: str | None = None  # why it was rejected
    reasons: list[str] = field(default_factory=list)  # plain English for the SQL writer's retry; never shown to the user
    limited: bool = False  # a LIMIT was added or lowered


def _reject(code: str, reason: str) -> SqlCheck:
    return SqlCheck(False, code=code, reasons=[reason])


def _is_denied_function(name: str) -> bool:
    name = name.lower()
    return name in DENIED_FUNCTIONS or name.startswith(DENIED_FUNCTION_PREFIXES)


def validate_sql(sql: str, allowed_tables: Iterable[str], sensitive_tables: Iterable[str] = (), max_rows: int = 100) -> SqlCheck:
    allowed = {t.lower() for t in allowed_tables}
    sensitive = {t.lower() for t in sensitive_tables}
    if not sql or not sql.strip():
        return _reject("empty", "No SQL was produced.")

    try:
        statements = sqlglot.parse(sql, read=DIALECT)
    except SqlglotError as exc:
        return _reject("syntax", f"The SQL could not be parsed: {str(exc).splitlines()[0][:200]}")
    statements = [s for s in statements if s is not None]
    if not statements:
        return _reject("empty", "No SQL statement was found.")
    if len(statements) > 1:
        return _reject("multiple_statements", "Only one statement is allowed; remove everything after the first.")

    tree = statements[0]
    if not isinstance(tree, (exp.Select, exp.SetOperation)):
        return _reject("not_select", "Only a read-only SELECT query is allowed.")

    bad = tree.find(*FORBIDDEN_NODES) if FORBIDDEN_NODES else None
    if bad is not None:
        return _reject("forbidden_statement", f"{type(bad).__name__.upper()} is not allowed; only reading data is permitted.")
    for select in tree.find_all(exp.Select):
        if select.args.get("into"):
            return _reject("select_into", "SELECT ... INTO creates a table and is not allowed.")
        if select.args.get("locks"):
            return _reject("locking", "Row locking (FOR UPDATE / FOR SHARE) is not allowed.")
    fetch = tree.args.get("limit")
    if isinstance(fetch, exp.Fetch):  # only plain "FETCH FIRST n ROWS ONLY" maps exactly onto LIMIT n
        options = fetch.args.get("limit_options")
        if options is not None and options.sql().upper() != "ROWS ONLY":
            return _reject("fetch", "FETCH ... WITH TIES / PERCENT is not supported; use LIMIT.")

    for func in tree.find_all(exp.Func):
        name = func.name if isinstance(func, exp.Anonymous) else func.sql_name()
        if _is_denied_function(name):
            return _reject("forbidden_function", f"The function {name}() is not allowed.")

    tables, problem = _check_tables(tree, allowed, sensitive)
    if problem:
        return problem

    limited = _apply_limit(tree, max_rows)
    return SqlCheck(True, sql=tree.sql(dialect=DIALECT, comments=False), tables=tables, limited=limited)


def _check_tables(tree: exp.Expression, allowed: set[str], sensitive: set[str]) -> tuple[list[str], SqlCheck | None]:
    """Every physical table the statement reads must be allowed. Uses scopes, so CTE names never hide a real table."""
    try:
        scopes = traverse_scope(tree)
    except SqlglotError as exc:
        return [], _reject("unsupported", f"The query structure is not supported: {str(exc).splitlines()[0][:150]}")
    used: set[str] = set()
    for scope in scopes:
        for source in scope.sources.values():
            if not isinstance(source, exp.Table):
                continue  # a CTE or subquery: its own scope is checked separately
            if isinstance(source.this, exp.Func) or not source.name:  # FROM some_function(...)
                fname = source.this.name if isinstance(source.this, exp.Anonymous) else source.this.sql_name() if isinstance(source.this, exp.Func) else ""
                if fname.lower() in ALLOWED_TABLE_FUNCTIONS:
                    continue
                return [], _reject("forbidden_function", f"The table function {fname or '(unnamed)'}() is not allowed.")
            name = source.name.lower()
            if source.catalog or (source.db and source.db.lower() != "public"):
                return [], _reject("table_not_allowed", f"Only tables in the public schema are available, not '{source.db}.{source.name}'.")
            if name in sensitive:
                return [], _reject("sensitive_table", f"The table '{name}' is restricted and cannot be queried.")
            if name not in allowed:
                shown = ", ".join(sorted(allowed - sensitive)) or "(none)"
                return [], _reject("table_not_allowed", f"The table '{name}' is not available. Use only these tables: {shown}.")
            used.add(name)
    return sorted(used), None


def _apply_limit(tree: exp.Expression, max_rows: int) -> bool:
    """Make sure the outermost query returns at most max_rows. True when a LIMIT was added or lowered.
    FETCH FIRST n ROWS ONLY is rewritten as LIMIT n, keeping the user's n."""
    limit = tree.args.get("limit")
    if isinstance(limit, exp.Limit):
        expr = limit.expression
    elif isinstance(limit, exp.Fetch):
        expr = limit.args.get("count") or exp.Literal.number(1)  # FETCH FIRST ROW ONLY means one row
    else:
        expr = None
    if isinstance(expr, exp.Literal) and expr.is_int and int(expr.name) <= max_rows:
        tree.set("limit", exp.Limit(expression=exp.Literal.number(int(expr.name))))  # normalises FETCH to LIMIT
        return False
    tree.set("limit", exp.Limit(expression=exp.Literal.number(max_rows)))
    return True
