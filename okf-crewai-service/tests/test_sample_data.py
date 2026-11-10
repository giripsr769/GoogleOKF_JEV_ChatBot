"""The sample database must hold realistic text, never generated placeholders. Skips without the Docker database."""
import re

import psycopg
import pytest
from test_sql_executor import READONLY_URL, needs_db

pytestmark = needs_db

# "departments name 1", "employees1@example.com", "CODE001": what the original generator produced
PLACEHOLDER = re.compile(r"^\S+ \S+ \d+$|^[a-z_]+\d+@example\.com$|^CODE\d+$")


def test_no_placeholder_text_in_any_readable_table():
    found = []
    with psycopg.connect(READONLY_URL) as conn:
        cols = conn.execute(
            "SELECT cl.relname, a.attname FROM pg_class cl "
            "JOIN pg_namespace n ON n.oid = cl.relnamespace AND n.nspname = 'public' "
            "JOIN pg_attribute a ON a.attrelid = cl.oid AND a.attnum > 0 AND NOT a.attisdropped "
            "WHERE cl.relkind = 'r' AND a.atttypid IN ('text'::regtype, 'varchar'::regtype) "
            "AND has_table_privilege(current_user, cl.oid, 'SELECT')"
        ).fetchall()
        assert len(cols) > 30  # the check really looked at the tables
        for table, column in cols:
            for (value,) in conn.execute(f'SELECT DISTINCT "{column}" FROM "{table}" WHERE "{column}" IS NOT NULL'):
                if PLACEHOLDER.match(value):
                    found.append(f"{table}.{column}: {value}")
    assert not found, "placeholder values: " + "; ".join(found[:10])


def test_job_title_salary_ranges_are_not_upside_down():
    with psycopg.connect(READONLY_URL) as conn:
        assert conn.execute("SELECT count(*) FROM job_titles WHERE min_salary > max_salary").fetchone()[0] == 0
