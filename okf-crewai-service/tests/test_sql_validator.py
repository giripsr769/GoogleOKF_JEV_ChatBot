import pytest

from okf_chat.core.sql_validator import validate_sql

ALLOWED = {"customers", "orders", "order_items", "products", "salaries"}  # salaries was "shown", yet it is sensitive
SENSITIVE = {"salaries"}


def check(sql, **kw):
    return validate_sql(sql, kw.pop("allowed", ALLOWED), kw.pop("sensitive", SENSITIVE), **kw)


# ---------------------------------------------------------------- queries that must pass
@pytest.mark.parametrize("sql, tables", [
    ("SELECT * FROM customers", ["customers"]),
    ("SELECT count(*) FROM customers;", ["customers"]),
    ("SELECT c.full_name, SUM(o.total_amount) AS t FROM customers c JOIN orders o ON o.customer_id = c.id GROUP BY 1 ORDER BY t DESC LIMIT 3", ["customers", "orders"]),
    ("SELECT * FROM public.customers", ["customers"]),
    ("SELECT * FROM CUSTOMERS", ["customers"]),
    ("WITH big AS (SELECT * FROM orders WHERE total_amount > 100) SELECT * FROM big", ["orders"]),
    ("SELECT id FROM customers UNION SELECT customer_id FROM orders", ["customers", "orders"]),
    ("SELECT id FROM customers INTERSECT SELECT customer_id FROM orders", ["customers", "orders"]),
    ("SELECT * FROM customers WHERE id IN (SELECT customer_id FROM orders)", ["customers", "orders"]),
    ("SELECT x, count(*) OVER (PARTITION BY x) FROM (SELECT status AS x FROM orders) s", ["orders"]),
    ("SELECT d::date FROM generate_series('2026-01-01'::date, '2026-01-05'::date, interval '1 day') d", []),
    ("SELECT 1", []),
    ("SELECT * FROM unnest(ARRAY[1,2]) u", []),
    ("SELECT date_trunc('month', ordered_at), count(*) FROM orders GROUP BY 1", ["orders"]),
    ("SELECT * FROM customers WHERE email LIKE '%@example.com'", ["customers"]),
])
def test_safe_reads_pass(sql, tables):
    r = check(sql)
    assert r.ok, r.reasons
    assert r.tables == tables


def test_a_cte_name_that_is_not_a_real_table_is_fine():
    assert check("WITH recent AS (SELECT * FROM orders) SELECT * FROM recent").tables == ["orders"]


# ---------------------------------------------------------------- the row limit
def test_a_limit_is_added_when_missing():
    r = check("SELECT * FROM customers", max_rows=100)
    assert r.limited and r.sql.endswith("LIMIT 100")


def test_a_larger_limit_is_lowered():
    r = check("SELECT * FROM customers LIMIT 5000", max_rows=100)
    assert r.limited and r.sql.endswith("LIMIT 100")


def test_a_smaller_limit_is_kept():
    r = check("SELECT * FROM customers LIMIT 3", max_rows=100)
    assert not r.limited and r.sql.endswith("LIMIT 3")


def test_a_non_literal_limit_is_replaced():
    r = check("SELECT * FROM customers LIMIT ALL", max_rows=100)
    assert r.ok and r.sql.endswith("LIMIT 100")


def test_fetch_first_becomes_a_limit_with_the_users_number():
    r = check("SELECT * FROM customers FETCH FIRST 5 ROWS ONLY", max_rows=100)
    assert r.ok and r.sql.endswith("LIMIT 5") and "FETCH" not in r.sql and not r.limited


def test_fetch_first_row_means_one_row():
    assert check("SELECT * FROM customers FETCH FIRST ROW ONLY").sql.endswith("LIMIT 1")


def test_a_huge_fetch_first_is_lowered():
    r = check("SELECT * FROM customers FETCH FIRST 9999 ROWS ONLY", max_rows=100)
    assert r.sql.endswith("LIMIT 100") and r.limited


def test_union_gets_a_limit_on_the_whole_result():
    r = check("SELECT id FROM customers UNION SELECT customer_id FROM orders", max_rows=50)
    assert r.sql.endswith("LIMIT 50")


def test_only_the_outermost_query_is_limited():
    r = check("SELECT * FROM (SELECT * FROM customers) s", max_rows=100)
    assert r.sql.count("LIMIT") == 1 and r.sql.endswith("LIMIT 100")


# ---------------------------------------------------------------- the sql that runs is the sql that was checked
def test_comments_are_stripped_from_the_rewritten_sql():
    r = check("SELECT /* hi; DROP TABLE customers */ id FROM customers -- tail; DELETE FROM orders")
    assert r.ok and "--" not in r.sql and "/*" not in r.sql and "DROP" not in r.sql and "DELETE" not in r.sql


def test_the_rewritten_sql_is_itself_valid_and_stable():
    first = check("SELECT c.id FROM customers c JOIN orders o ON o.customer_id = c.id")
    again = check(first.sql)
    assert again.ok and again.sql == first.sql and not again.limited


# ---------------------------------------------------------------- attacks that must be rejected
@pytest.mark.parametrize("sql, code", [
    ("", "empty"),
    ("   ", "empty"),
    ("-- just a comment", "empty"),
    ("SELEC * FROM", "syntax"),
    ("SELECT 1; DROP TABLE customers", "multiple_statements"),
    ("SELECT 1; SELECT 2", "multiple_statements"),
    ("DROP TABLE customers", "not_select"),
    ("DELETE FROM customers", "not_select"),
    ("UPDATE customers SET email = 'x'", "not_select"),
    ("INSERT INTO customers (full_name) VALUES ('x')", "not_select"),
    ("TRUNCATE customers", "not_select"),
    ("ALTER TABLE customers ADD COLUMN x int", "not_select"),
    ("CREATE TABLE x (a int)", "not_select"),
    ("CREATE TABLE x AS SELECT * FROM customers", "not_select"),
    ("GRANT ALL ON customers TO public", "not_select"),
    ("COPY customers TO '/tmp/x'", "not_select"),
    ("SET statement_timeout = 0", "not_select"),
    ("EXPLAIN ANALYZE DELETE FROM customers", "not_select"),
    ("CALL do_it()", "not_select"),
    ("DO $$ BEGIN PERFORM 1; END $$", "not_select"),
    ("BEGIN", "not_select"),
    ("WITH d AS (DELETE FROM customers RETURNING *) SELECT * FROM d", "forbidden_statement"),
    ("WITH u AS (UPDATE customers SET full_name = 'x' RETURNING *) SELECT * FROM u", "forbidden_statement"),
    ("WITH i AS (INSERT INTO customers (full_name) VALUES ('x') RETURNING *) SELECT * FROM i", "forbidden_statement"),
    ("SELECT * INTO newt FROM customers", "select_into"),
    ("SELECT * FROM customers FOR UPDATE", "locking"),
    ("SELECT * FROM customers FOR SHARE", "locking"),
    ("SELECT * FROM customers FETCH FIRST 5 ROWS WITH TIES", "fetch"),
    ("SELECT * FROM customers FETCH FIRST 10 PERCENT ROWS ONLY", "fetch"),
])
def test_attacks_are_rejected_with_the_right_code(sql, code):
    r = check(sql)
    assert not r.ok and r.code == code, (r.code, r.reasons)
    assert r.sql == "" and r.reasons  # nothing runnable is ever returned for a rejected query


@pytest.mark.parametrize("sql", [
    "SELECT pg_read_file('/etc/passwd')",
    "SELECT pg_sleep(10)",
    "SELECT * FROM customers WHERE id = 1 AND pg_sleep(5) IS NOT NULL",
    "SELECT set_config('statement_timeout', '0', false)",
    "SELECT current_setting('server_version')",
    "SELECT lo_import('/etc/passwd')",
    "SELECT dblink('host=evil', 'select 1')",
    "SELECT version()",
    "SELECT pg_terminate_backend(1)",
    "SELECT * FROM pg_read_file('/etc/passwd')",
    "SELECT * FROM pg_ls_dir('/')",
    "SELECT * FROM unnest(ARRAY[pg_read_file('/etc/passwd')]) u",
    "SELECT query_to_xml('select * from salaries', true, true, '')",
])
def test_dangerous_functions_are_rejected(sql):
    r = check(sql)
    assert not r.ok and r.code == "forbidden_function", (r.code, r.reasons)


@pytest.mark.parametrize("sql", [
    "SELECT * FROM pg_catalog.pg_user",
    "SELECT * FROM information_schema.tables",
    "SELECT * FROM pg_user",
    "SELECT * FROM pg_shadow",
    "SELECT * FROM other_schema.customers",
    "SELECT * FROM otherdb.public.customers",
    "SELECT * FROM vendors",
    "SELECT c.* FROM customers c JOIN vendors v ON v.id = c.id",
    "SELECT * FROM customers WHERE id IN (SELECT id FROM vendors)",
    "WITH x AS (SELECT * FROM vendors) SELECT * FROM x",
    "SELECT id FROM customers UNION SELECT id FROM vendors",
])
def test_tables_outside_the_allowed_set_are_rejected(sql):
    r = check(sql)
    assert not r.ok and r.code == "table_not_allowed", (r.code, r.reasons)


@pytest.mark.parametrize("sql", [
    "SELECT * FROM salaries",
    "SELECT * FROM SALARIES",
    "SELECT * FROM public.salaries",
    "SELECT * FROM salaries s",
    "SELECT e.* FROM customers e JOIN salaries s ON s.id = e.id",
    "SELECT * FROM customers WHERE id IN (SELECT id FROM salaries)",
    "SELECT * FROM (SELECT * FROM salaries) t",
    "WITH s AS (SELECT * FROM salaries) SELECT * FROM s",
    "SELECT id FROM customers UNION SELECT id FROM salaries",
    "SELECT * FROM customers, salaries",
    "SELECT * FROM customers CROSS JOIN LATERAL (SELECT * FROM salaries) s",
    # a CTE called salaries elsewhere in the statement must not hide the real table
    "SELECT * FROM salaries WHERE EXISTS (WITH salaries AS (SELECT 1 AS x) SELECT 1 FROM salaries)",
])
def test_sensitive_tables_are_rejected_however_they_are_reached(sql):
    r = check(sql)
    assert not r.ok and r.code == "sensitive_table", (r.code, r.reasons)


def test_sensitive_beats_allowed_even_when_the_table_was_shown():
    assert check("SELECT * FROM salaries", allowed={"salaries"}).code == "sensitive_table"


# ---------------------------------------------------------------- feedback for the SQL writer
def test_the_rejection_message_lists_what_is_available_without_naming_sensitive_tables():
    r = check("SELECT * FROM vendors")
    assert "customers" in r.reasons[0] and "orders" in r.reasons[0] and "salaries" not in r.reasons[0]


def test_tables_are_returned_sorted_and_unique():
    r = check("SELECT * FROM orders o JOIN customers c ON c.id = o.customer_id JOIN orders o2 ON o2.id = o.id")
    assert r.tables == ["customers", "orders"]


def test_rejections_never_leak_into_a_runnable_result():
    r = check("DROP TABLE customers")
    assert not r.ok and r.sql == "" and r.tables == []
