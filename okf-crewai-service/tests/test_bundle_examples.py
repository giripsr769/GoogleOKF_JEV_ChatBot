"""The worked examples in the shipped okf_bundle must stay valid SQL over tables that exist (no database needed)."""
import re
from pathlib import Path

import pytest

from okf_chat.core.okf_loader import Bundle, section
from okf_chat.core.sql_validator import validate_sql

BUNDLE = Path(__file__).resolve().parent.parent / "okf_bundle"
pytestmark = pytest.mark.skipif(not BUNDLE.is_dir(), reason="no okf_bundle folder")


def examples():
    bundle = Bundle.load(BUNDLE)
    for name, concept in bundle.tables().items():
        for sql in re.findall(r"```sql\n(.*?)\n```", section(concept.body, "Examples"), re.S):
            yield name, sql


def test_every_table_has_examples_except_sensitive():
    bundle = Bundle.load(BUNDLE)
    have = {name for name, _ in examples()}
    assert set(bundle.tables()) - bundle.sensitive_tables() - have == set()
    assert not have & bundle.sensitive_tables()


def test_every_example_passes_the_validator():
    bundle = Bundle.load(BUNDLE)
    allowed, sensitive = set(bundle.tables()), bundle.sensitive_tables()
    found = list(examples())
    assert len(found) >= 49
    for name, sql in found:
        check = validate_sql(sql, allowed, sensitive, 100)
        assert check.ok, f"{name}: {check.reasons}"
