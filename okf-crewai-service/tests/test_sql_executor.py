"""Executor tests. The integration tests need the Docker database (`docker compose up -d`) and skip themselves without it."""
import json
import os
import time
from datetime import date, datetime, timedelta
from decimal import Decimal
from uuid import UUID

import psycopg
import pytest

from okf_chat.core.sql_executor import ReadOnlyExecutor, SqlExecutionError, UnsafeDatabaseRole, jsonable

READONLY_URL = os.getenv("TEST_DATABASE_URL", "postgresql://okf_readonly:okf_readonly@localhost:5433/shop")
ADMIN_URL = os.getenv("TEST_ADMIN_URL", "postgresql://postgres:postgres@localhost:5433/shop")


def _reachable(url: str) -> bool:
    try:
        psycopg.connect(url, connect_timeout=2).close()
        return True
    except psycopg.Error:
        return False


needs_db = pytest.mark.skipif(not _reachable(READONLY_URL), reason="test database not running (docker compose up -d)")
needs_admin = pytest.mark.skipif(not _reachable(ADMIN_URL), reason="admin login to the test database not available")


@pytest.fixture
def ex():
    return ReadOnlyExecutor(READONLY_URL, statement_timeout_ms=3000, max_rows=100)


def run_error(executor, sql) -> SqlExecutionError:
    with pytest.raises(SqlExecutionError) as info:
        executor.run(sql)
    return info.value


# ---------------------------------------------------------------- jsonable (no database needed)
def test_jsonable_converts_database_types():
    value = {
        "n": Decimal("12.50"), "ts": datetime(2026, 11, 3, 10, 30), "d": date(2026, 11, 3),
        "gap": timedelta(minutes=2), "id": UUID("12345678-1234-5678-1234-567812345678"), "raw": b"\x01\xff", "list": [Decimal("1.5")],
    }
    out = jsonable(value)
    assert out == {"n": 12.5, "ts": "2026-11-03T10:30:00", "d": "2026-11-03", "gap": 120.0,
                   "id": "12345678-1234-5678-1234-567812345678", "raw": "01ff", "list": [1.5]}
    json.dumps(out)  # must not raise


# ---------------------------------------------------------------- running queries
@needs_db
def test_select_returns_columns_rows_and_timing(ex):
    r = ex.run("SELECT id, full_name FROM customers ORDER BY id LIMIT 4")
    assert r.columns == ["id", "full_name"] and r.row_count == 4 and not r.truncated
    assert r.rows[0] == {"id": 1, "full_name": "Asha Rao"} and r.elapsed_ms > 0


@needs_db
def test_results_are_json_serialisable(ex):
    r = ex.run("SELECT total_amount, ordered_at, id FROM orders ORDER BY id")
    json.dumps(r.rows)
    assert isinstance(r.rows[0]["total_amount"], float) and isinstance(r.rows[0]["ordered_at"], str)


@needs_db
def test_rows_beyond_max_rows_are_cut_and_flagged():
    r = ReadOnlyExecutor(READONLY_URL, max_rows=3).run("SELECT g FROM generate_series(1, 10) g")
    assert r.row_count == 3 and r.truncated and [x["g"] for x in r.rows] == [1, 2, 3]


@needs_db
def test_exactly_max_rows_is_not_truncated():
    r = ReadOnlyExecutor(READONLY_URL, max_rows=3).run("SELECT g FROM generate_series(1, 3) g")
    assert r.row_count == 3 and not r.truncated


@needs_db
def test_duplicate_column_names_do_not_collapse(ex):
    r = ex.run("SELECT o.id, c.id FROM orders o JOIN customers c ON c.id = o.customer_id ORDER BY o.id LIMIT 1")
    assert r.columns == ["id", "id_2"] and set(r.rows[0]) == {"id", "id_2"}


@needs_db
def test_percent_signs_in_like_patterns_are_left_alone(ex):
    # every sample email ends in @example.com, so the pattern must match all of them ('%' must not be read as a parameter)
    assert ex.run("SELECT count(*) FILTER (WHERE email LIKE '%@example.com') = count(*) AS ok FROM customers").rows == [{"ok": True}]


@needs_db
def test_empty_result_still_has_columns(ex):
    r = ex.run("SELECT id, full_name FROM customers WHERE id = -1")
    assert r.columns == ["id", "full_name"] and r.rows == [] and r.row_count == 0


@needs_db
async def test_async_execute_runs_in_a_thread(ex):
    r = await ex.execute("SELECT count(*) AS n FROM customers")
    assert r.rows == [{"n": ex.run("SELECT count(*) AS n FROM customers").rows[0]["n"]}]


# ---------------------------------------------------------------- the database says no, even without the validator
@needs_db
def test_writes_fail_and_change_nothing(ex):
    before = ex.run("SELECT count(*) AS n FROM customers").rows
    for sql in ("DELETE FROM customers", "UPDATE customers SET full_name = 'x'", "INSERT INTO customers (full_name) VALUES ('x')",
                "DROP TABLE customers", "TRUNCATE customers", "CREATE TABLE sneaky (a int)"):
        err = run_error(ex, sql)
        assert err.code in {"read_only", "permission_denied"}, (sql, err.code, err.message)
    assert ex.run("SELECT count(*) AS n FROM customers").rows == before


@needs_db
def test_restricted_table_is_denied(ex):
    err = run_error(ex, "SELECT * FROM salaries")
    assert err.code == "permission_denied" and "salaries" in err.message and not err.retryable


@needs_db
def test_multiple_statements_cannot_smuggle_a_write(ex):
    # psycopg runs a multi-statement string without parameters as one simple query; the READ ONLY transaction still blocks the write
    before = ex.run("SELECT count(*) AS n FROM customers").rows
    err = run_error(ex, "SELECT 1; DELETE FROM customers")
    assert err.code in {"read_only", "permission_denied"}
    assert ex.run("SELECT count(*) AS n FROM customers").rows == before


@needs_db
def test_set_role_or_transaction_escape_does_not_make_the_session_writable(ex):
    before = ex.run("SELECT count(*) AS n FROM customers").rows
    err = run_error(ex, "SET TRANSACTION READ WRITE; DELETE FROM customers")
    assert err.code in {"read_only", "permission_denied", "db_error", "sql_error"}
    assert ex.run("SELECT count(*) AS n FROM customers").rows == before


# ---------------------------------------------------------------- failures
@needs_db
def test_slow_queries_are_cancelled_quickly():
    executor = ReadOnlyExecutor(READONLY_URL, statement_timeout_ms=300)
    t0 = time.perf_counter()
    err = run_error(executor, "SELECT pg_sleep(5)")
    assert err.code == "timeout" and not err.retryable and time.perf_counter() - t0 < 2.5


@needs_db
def test_sql_mistakes_are_retryable_and_name_the_problem(ex):
    err = run_error(ex, "SELECT nope FROM customers")
    assert err.code == "sql_error" and err.retryable and "nope" in err.message
    assert run_error(ex, "SELECT * FROM no_such_table").retryable
    assert run_error(ex, "SELECT 1/0").retryable
    assert run_error(ex, "SELEC 1").retryable


def test_unreachable_database_is_reported_not_raised_raw():
    err = run_error(ReadOnlyExecutor("postgresql://okf_readonly:x@localhost:1/shop", connect_timeout_s=2), "SELECT 1")
    assert err.code == "unavailable" and not err.retryable


@needs_db
def test_the_connection_is_released_after_an_error(ex):
    run_error(ex, "SELECT nope FROM customers")
    assert ex.run("SELECT 1 AS one").rows == [{"one": 1}]  # a failed query leaves no broken session behind


# ---------------------------------------------------------------- refusing an unsafe login
@needs_db
def test_the_read_only_role_passes_verification(ex):
    report = ex.verify()
    assert report.safe and report.user == "okf_readonly"


@needs_admin
def test_a_superuser_login_is_refused():
    with pytest.raises(UnsafeDatabaseRole) as info:
        ReadOnlyExecutor(ADMIN_URL).verify()
    msg = str(info.value)
    assert "postgres" in msg and "superuser" in msg and "okf_readonly" in msg  # says what is wrong and how to fix it


@needs_admin
def test_a_role_that_can_write_is_refused_even_if_it_is_not_a_superuser():
    name = f"okf_test_writer_{os.getpid()}"
    with psycopg.connect(ADMIN_URL, autocommit=True) as admin:
        admin.execute(f"CREATE ROLE {name} LOGIN PASSWORD 'pw' NOSUPERUSER NOCREATEDB NOCREATEROLE")
        try:
            admin.execute(f"GRANT CONNECT ON DATABASE shop TO {name}")
            admin.execute(f"GRANT USAGE ON SCHEMA public TO {name}")
            admin.execute(f"GRANT SELECT, DELETE ON customers TO {name}")
            url = READONLY_URL.replace("okf_readonly:okf_readonly", f"{name}:pw")
            with pytest.raises(UnsafeDatabaseRole) as info:
                ReadOnlyExecutor(url).verify()
            assert "can write to" in str(info.value) and "customers" in str(info.value)
        finally:
            admin.execute(f"REVOKE ALL ON customers FROM {name}")
            admin.execute(f"REVOKE ALL ON SCHEMA public FROM {name}")
            admin.execute(f"REVOKE ALL ON DATABASE shop FROM {name}")
            admin.execute(f"DROP ROLE {name}")
