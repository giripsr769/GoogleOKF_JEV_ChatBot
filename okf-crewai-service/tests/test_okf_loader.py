from datetime import datetime, timezone
from pathlib import Path

import pytest

from okf_chat.core.okf_loader import Bundle, check_bundle, parse_schema, parse_time, split_front

REAL_BUNDLE = Path(__file__).resolve().parent.parent / "okf_bundle"


def write(root: Path, rel: str, text: str) -> None:
    path = root / rel
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(text, encoding="utf-8")


def table_md(name: str, body: str = "", extra: str = "", cols=("id",)) -> str:
    rows = "\n".join(f"| `{c}` | integer |  | the {c} |" for c in cols)
    return (
        f'---\ntype: "Postgres Table"\ntitle: "{name}"\ndescription: "The {name} table."\n'
        f'resource: "postgres://db/public/{name}"\ncolumns: [{", ".join(cols)}]\n{extra}---\n\n'
        f"# Schema\n\n| Column | Type | Key | Description |\n|---|---|---|---|\n{rows}\n\n{body}"
    )


@pytest.fixture
def bundle_dir(tmp_path):
    write(tmp_path, "index.md", '---\nokf_version: "0.2"\n---\n\n# Sections\n\n* [Tables](/tables/index.md) - all tables\n')
    write(tmp_path, "tables/index.md", "# Sales\n\n* [orders](/tables/orders.md) - the orders\n* [customers](customers.md) - the customers\n")
    write(tmp_path, "tables/orders.md", table_md("orders", "# Relationships\n\n- references [customers](/tables/customers.md).\n", cols=("id", "customer_id")))
    write(tmp_path, "tables/customers.md", table_md("customers"))
    write(tmp_path, "log.md", "# Directory Update Log\n\n## 2026-11-03\n* **Creation**: made.\n")
    return tmp_path


# ---------------------------------------------------------------- loading
def test_loads_concepts_and_columns(bundle_dir):
    b = Bundle.load(bundle_dir)
    assert set(b.tables()) == {"orders", "customers"}
    orders = b.table("orders")
    assert orders.column_names == ["id", "customer_id"]
    assert [c.name for c in orders.columns] == ["id", "customer_id"]
    assert orders.resource == "postgres://db/public/orders"
    assert b.okf_version == "0.2"


def test_missing_bundle_folder_raises(tmp_path):
    with pytest.raises(FileNotFoundError):
        Bundle.load(tmp_path / "nope")


def test_reserved_files_are_not_concepts(bundle_dir):
    assert not any(p.endswith(("index.md", "log.md")) for p in Bundle.load(bundle_dir).concepts)


def test_unknown_type_and_keys_are_tolerated_and_preserved(bundle_dir):
    write(bundle_dir, "references/glossary.md", '---\ntype: "Glossary Term"\nmy_custom_key: 42\n---\nBody.\n')
    b = Bundle.load(bundle_dir)
    c = b.get("/references/glossary.md")
    assert c.type == "Glossary Term" and c.front["my_custom_key"] == 42
    assert check_bundle(bundle_dir).ok


def test_file_without_frontmatter_is_skipped_with_warning(bundle_dir):
    write(bundle_dir, "notes.md", "just text, no frontmatter\n")
    b = Bundle.load(bundle_dir)
    assert "/notes.md" not in b.concepts
    assert any("notes.md" in w for w in b.warnings)


def test_broken_link_is_a_warning_not_an_error(bundle_dir):
    write(bundle_dir, "tables/orders.md", table_md("orders", "See [ghost](/tables/ghost.md).\n"))
    report = check_bundle(bundle_dir)
    assert report.ok
    assert any("broken link /tables/ghost.md" in w for w in report.warnings)


def test_relative_links_resolve_from_the_linking_file(bundle_dir):
    write(bundle_dir, "tables/orders.md", table_md("orders", "See [c](./customers.md) and [d](../index.md#top).\n"))
    links = Bundle.load(bundle_dir).table("orders").links
    assert "/tables/customers.md" in links and "/index.md" in links


def test_external_links_and_anchors_are_ignored(bundle_dir):
    write(bundle_dir, "tables/orders.md", table_md("orders", "[web](https://example.com/a.md) [top](#schema)\n"))
    assert Bundle.load(bundle_dir).table("orders").links == []


# ---------------------------------------------------------------- navigation
def test_related_tables_follow_links_in_both_directions(bundle_dir):
    b = Bundle.load(bundle_dir)
    assert b.related_tables("orders") == {"customers"}  # orders links to customers
    assert b.related_tables("customers") == {"orders"}  # backlink
    assert b.related_tables("nope") == set()


def test_index_entries_parse_sections_links_and_descriptions(bundle_dir):
    entries = Bundle.load(bundle_dir).index_entries("/tables")
    assert [(e.title, e.url, e.description, e.section) for e in entries] == [
        ("orders", "/tables/orders.md", "the orders", "Sales"),
        ("customers", "/tables/customers.md", "the customers", "Sales"),  # relative link resolved
    ]
    assert Bundle.load(bundle_dir).index_entries("/missing") == []


def test_sensitive_tables(bundle_dir):
    write(bundle_dir, "tables/salaries.md", table_md("salaries", extra="sensitive: true\n"))
    assert Bundle.load(bundle_dir).sensitive_tables() == {"salaries"}


# ---------------------------------------------------------------- trust and lifecycle (spec section 5)
@pytest.mark.parametrize("verified, tier", [
    ("", "unverified"),
    ('verified: {by: "process:nightly", at: "2026-11-01T00:00:00Z"}\n', "machine-confirmed"),
    ('verified: {by: "human:asha", at: "2026-11-01T00:00:00Z"}\n', "human-reviewed"),
    ('verified:\n  - {by: "process:x", at: "2026-11-01T00:00:00Z"}\n  - {by: "human:y", at: "2026-11-02T00:00:00Z"}\n', "human-reviewed"),
])
def test_trust_tiers(bundle_dir, verified, tier):
    write(bundle_dir, "tables/orders.md", table_md("orders", extra=verified))
    assert Bundle.load(bundle_dir).table("orders").trust_tier == tier


def test_staleness_is_a_plain_comparison(bundle_dir):
    write(bundle_dir, "tables/orders.md", table_md("orders", extra='stale_after: "2026-11-02T00:00:00Z"\n'))
    c = Bundle.load(bundle_dir).table("orders")
    assert not c.is_stale(datetime(2026, 11, 1, tzinfo=timezone.utc))
    assert c.is_stale(datetime(2026, 11, 2, tzinfo=timezone.utc))  # now >= stale_after
    assert any("stale" in w for w in check_bundle(bundle_dir, now=datetime(2026, 12, 1, tzinfo=timezone.utc)).warnings)


def test_unquoted_yaml_timestamp_is_understood(bundle_dir):
    write(bundle_dir, "tables/orders.md", table_md("orders", extra="stale_after: 2026-11-02T00:00:00Z\n"))
    assert Bundle.load(bundle_dir).table("orders").stale_after == datetime(2026, 11, 2, tzinfo=timezone.utc)


def test_parse_time_handles_junk():
    assert parse_time("not a date") is None and parse_time(None) is None and parse_time("") is None


# ---------------------------------------------------------------- conformance (spec section 11)
def test_valid_bundle_conforms(bundle_dir):
    report = check_bundle(bundle_dir)
    assert report.ok and report.concepts == 2 and report.errors == []


def test_missing_type_is_an_error(bundle_dir):
    write(bundle_dir, "tables/orders.md", '---\ntitle: "orders"\n---\nBody\n')
    assert any("orders.md: frontmatter has no `type`" in e for e in check_bundle(bundle_dir).errors)


def test_blank_type_is_an_error(bundle_dir):
    write(bundle_dir, "tables/orders.md", '---\ntype: "  "\n---\nBody\n')
    assert not check_bundle(bundle_dir).ok


def test_unparseable_frontmatter_is_an_error(bundle_dir):
    write(bundle_dir, "tables/orders.md", "---\ntype: [unclosed\n---\nBody\n")
    assert any("orders.md" in e for e in check_bundle(bundle_dir).errors)


def test_only_root_index_may_have_frontmatter(bundle_dir):
    write(bundle_dir, "tables/index.md", '---\nokf_version: "0.2"\n---\n# T\n')
    assert any("only the bundle-root index.md" in e for e in check_bundle(bundle_dir).errors)


def test_log_headings_must_be_iso_dates(bundle_dir):
    write(bundle_dir, "log.md", "# Log\n\n## yesterday\n* **Update**: x\n")
    assert any("log date heading" in e for e in check_bundle(bundle_dir).errors)


def test_missing_index_is_only_a_warning(tmp_path):
    write(tmp_path, "a.md", '---\ntype: "Note"\n---\nhi\n')
    report = check_bundle(tmp_path)
    assert report.ok and any("index.md is missing" in w for w in report.warnings)


def test_newer_okf_version_is_best_effort(bundle_dir):
    write(bundle_dir, "index.md", '---\nokf_version: "0.9"\n---\n# x\n')
    b = Bundle.load(bundle_dir)
    assert b.tables() and any("0.9" in w for w in b.warnings)


def test_schema_column_mismatch_is_a_warning(bundle_dir):
    write(bundle_dir, "tables/orders.md", table_md("orders", cols=("id",)).replace("columns: [id]", "columns: [id, ghost]"))
    report = check_bundle(bundle_dir)
    assert report.ok and any("does not match the # Schema" in w for w in report.warnings)


def test_check_on_missing_folder(tmp_path):
    assert not check_bundle(tmp_path / "nope").ok


# ---------------------------------------------------------------- helpers
def test_split_front_without_frontmatter():
    assert split_front("# just a body\n") == ({}, "# just a body\n")


def test_parse_schema_handles_escaped_pipes_and_windows_newlines():
    body = "# Schema\n\n| Column | Type | Key | Description |\n|---|---|---|---|\n| `a` | text |  | x \\| y |\n"
    assert parse_schema(body)[0].description == "x | y"
    front, text = split_front('---\r\ntype: "T"\r\n---\r\nbody\r\n')
    assert front["type"] == "T" and "\r" not in text


# ---------------------------------------------------------------- the real generated bundle
@pytest.mark.skipif(not REAL_BUNDLE.is_dir(), reason="run `okf-chat build` first")
def test_real_bundle_conforms_and_flags_salaries():
    report = check_bundle(REAL_BUNDLE)
    assert report.ok, report.errors
    b = Bundle.load(REAL_BUNDLE)
    assert len(b.tables()) == 50
    assert b.sensitive_tables() == {"salaries"}
    assert "customers" in b.related_tables("orders") and "order_items" in b.related_tables("orders")
    assert len(b.index_entries("/tables")) == 50
