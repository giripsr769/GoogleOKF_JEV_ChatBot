"""Builder and CLI tests. They build into a scratch schema of the Docker database and skip without it."""
import uuid

import psycopg
import pytest
from test_sql_executor import ADMIN_URL, needs_admin

from okf_chat import cli
from okf_chat.builder.build_from_db import build_bundle
from okf_chat.core.okf_loader import Bundle, check_bundle

pytestmark = needs_admin


@pytest.fixture
def schema():
    """A throwaway schema: customers <- orders, a `salaries` table nobody can read, a table called `index`, and a commented table."""
    name = "t_" + uuid.uuid4().hex[:8]
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute(f'CREATE SCHEMA "{name}"')
        c.execute(f"""
            CREATE TABLE "{name}".customers (id serial PRIMARY KEY, full_name text NOT NULL);
            CREATE TABLE "{name}".orders (id serial PRIMARY KEY, customer_id int REFERENCES "{name}".customers(id), total numeric);
            CREATE TABLE "{name}".salaries (id serial PRIMARY KEY, amount numeric);
            CREATE TABLE "{name}"."index" (id serial PRIMARY KEY);
            COMMENT ON TABLE "{name}".orders IS 'Customer purchases.';
            COMMENT ON COLUMN "{name}".orders.total IS 'Order total in USD.';
            REVOKE ALL ON ALL TABLES IN SCHEMA "{name}" FROM okf_readonly;
            GRANT USAGE ON SCHEMA "{name}" TO okf_readonly;
            GRANT SELECT ON "{name}".customers, "{name}".orders, "{name}"."index" TO okf_readonly;
        """)
    yield name
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute(f'DROP SCHEMA "{name}" CASCADE')


def build(tmp_path, schema, **kw):
    return build_bundle(ADMIN_URL, tmp_path, schema=schema, **kw)


def test_build_conforms_and_flags_sensitive(tmp_path, schema):
    r = build(tmp_path, schema)
    assert sorted(r.created) == ["customers", "index", "orders", "salaries"]
    assert r.sensitive == ["salaries"]
    assert check_bundle(tmp_path).ok
    bundle = Bundle.load(tmp_path)
    assert bundle.sensitive_tables() == {"salaries"}
    assert len(bundle.tables()) == 4


def test_rendering_has_keys_links_and_comments(tmp_path, schema):
    build(tmp_path, schema)
    text = (tmp_path / "tables" / "orders.md").read_text(encoding="utf-8")
    assert "Customer purchases." in text and "Order total in USD." in text
    assert "FK → [customers](/tables/customers.md)" in text
    assert "Referenced by" in (tmp_path / "tables" / "customers.md").read_text(encoding="utf-8")


def test_reserved_filename_is_avoided(tmp_path, schema):
    build(tmp_path, schema)
    assert (tmp_path / "tables" / "index_table.md").exists()
    assert "# Tables" in (tmp_path / "tables" / "index.md").read_text(encoding="utf-8")  # the real index is untouched
    assert "index" in Bundle.load(tmp_path).tables()


def test_rebuild_is_idempotent(tmp_path, schema):
    build(tmp_path, schema)
    r = build(tmp_path, schema)
    assert not r.created and not r.updated and not r.removed
    assert len(r.unchanged) == 4


def test_hand_edits_survive_rebuild(tmp_path, schema):
    build(tmp_path, schema)
    path = tmp_path / "tables" / "customers.md"
    text = path.read_text(encoding="utf-8")
    text = text.replace("Table `customers` with 2 columns. Add a one-sentence description.", "People who buy from us.")
    text = text.replace("auto_description: true\n", "")
    text += "\n# Notes\n\nCustomers never get deleted.\n"
    path.write_text(text, encoding="utf-8")
    build(tmp_path, schema)
    again = path.read_text(encoding="utf-8")
    assert "People who buy from us." in again and "Customers never get deleted." in again
    assert "auto_description" not in again


def test_database_comment_beats_fallback_but_hand_edit_beats_comment(tmp_path, schema):
    build(tmp_path, schema)
    path = tmp_path / "tables" / "orders.md"
    assert Bundle.load(tmp_path).table("orders").description == "Customer purchases."
    path.write_text(path.read_text(encoding="utf-8").replace("Customer purchases.", "Every sale."), encoding="utf-8")
    build(tmp_path, schema)
    assert Bundle.load(tmp_path).table("orders").description == "Every sale."


def test_dropped_table_is_removed_but_foreign_files_stay(tmp_path, schema):
    build(tmp_path, schema)
    mine = tmp_path / "tables" / "notes_by_hand.md"
    mine.write_text('---\ntype: "Postgres Table"\ntitle: "hand_made"\ndescription: "mine"\n---\nmine\n', encoding="utf-8")
    with psycopg.connect(ADMIN_URL, autocommit=True) as c:
        c.execute(f'DROP TABLE "{schema}".salaries')
    r = build(tmp_path, schema)
    assert r.removed == ["salaries"]
    assert not (tmp_path / "tables" / "salaries.md").exists()
    assert mine.exists()
    assert "salaries" in (tmp_path / "log.md").read_text(encoding="utf-8")


def test_domains_group_tables_into_folders(tmp_path, schema):
    domains = tmp_path / "domains.yaml"
    domains.write_text("sales:\n  title: Sales\n  tables: [customers, orders]\n", encoding="utf-8")
    out = tmp_path / "bundle"
    build(out, schema, domains_file=domains)
    assert (out / "tables" / "sales" / "orders.md").exists()
    assert (out / "tables" / "sales" / "index.md").exists()
    assert (out / "tables" / "salaries.md").exists()
    assert check_bundle(out).ok


def test_seed_dir_supplies_descriptions_once(tmp_path, schema):
    seed = tmp_path / "seed"
    seed.mkdir()
    (seed / "customers.md").write_text(
        '---\ntitle: customers\ndescription: Shoppers.\ntags: [crm]\ncolumns:\n  - {name: full_name, description: Display name}\n---\n# customers\n\nNote from seed.\n',
        encoding="utf-8")
    out = tmp_path / "bundle"
    build(out, schema, seed_dir=seed)
    text = (out / "tables" / "customers.md").read_text(encoding="utf-8")
    assert "Shoppers." in text and "Display name" in text and "Note from seed." in text
    build(out, schema)  # seed not passed again: the knowledge now lives in the bundle
    assert "Shoppers." in (out / "tables" / "customers.md").read_text(encoding="utf-8")


def test_empty_schema_is_an_error(tmp_path, schema):
    with pytest.raises(SystemExit):
        build_bundle(ADMIN_URL, tmp_path, schema="no_such_schema_xyz")


# ---------------------------------------------------------------- CLI
def run_cli(monkeypatch, *argv):
    monkeypatch.setattr("sys.argv", ["okf-chat", *argv])
    return cli.main()


def test_cli_build_then_check(tmp_path, schema, monkeypatch, capsys):
    out = tmp_path / "b"
    assert run_cli(monkeypatch, "build", "--admin-url", ADMIN_URL, "--out", str(out), "--schema", schema) == 0
    assert "created 4" in capsys.readouterr().out
    assert run_cli(monkeypatch, "check", str(out)) == 0
    assert "conforms to OKF v0.2" in capsys.readouterr().out


def test_cli_check_fails_on_broken_bundle(tmp_path, monkeypatch, capsys):
    (tmp_path / "tables").mkdir()
    (tmp_path / "tables" / "x.md").write_text("no frontmatter at all", encoding="utf-8")
    assert run_cli(monkeypatch, "check", str(tmp_path)) == 1
    assert "error" in capsys.readouterr().out.lower()


def test_cli_build_needs_admin_url(monkeypatch, capsys):
    monkeypatch.delenv("ADMIN_DATABASE_URL", raising=False)
    assert run_cli(monkeypatch, "build", "--out", "nowhere") == 2
    assert "--admin-url" in capsys.readouterr().out


def test_cli_without_command_prints_help(monkeypatch, capsys):
    assert run_cli(monkeypatch) == 0
    assert "serve" in capsys.readouterr().out


def test_examples_section_survives_rebuild(tmp_path, schema):
    build(tmp_path, schema)
    path = tmp_path / "tables" / "customers.md"
    path.write_text(path.read_text(encoding="utf-8") + "\n# Examples\n\n**Q:** How many customers?\n\n```sql\nSELECT COUNT(*) FROM customers\n```\n", encoding="utf-8")
    build(tmp_path, schema)
    text = path.read_text(encoding="utf-8")
    assert text.count("# Examples") == 1 and "SELECT COUNT(*) FROM customers" in text
    assert check_bundle(tmp_path).ok
