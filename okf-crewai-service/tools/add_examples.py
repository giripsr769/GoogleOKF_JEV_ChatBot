"""Write the worked examples in tools/examples.yaml into the OKF bundle as a `# Examples` section per table.

Every SQL is checked first with the real validator and run on the read-only database, so no broken example reaches the bundle.
Safe to re-run: an existing Examples section is replaced. The builder keeps the section on rebuilds.

    python tools/add_examples.py [--check]      (--check: validate only, write nothing)
"""
import os
import re
import sys
from pathlib import Path

import yaml

from okf_chat.core.okf_loader import Bundle, split_front
from okf_chat.core.sql_executor import ReadOnlyExecutor, SqlExecutionError
from okf_chat.core.sql_validator import validate_sql

ROOT = Path(__file__).resolve().parent.parent
URL = os.getenv("SMOKE_DATABASE_URL", "postgresql://okf_readonly:okf_readonly@localhost:5433/shop")
BUNDLE = ROOT / "okf_bundle"


def render(items: list[dict]) -> str:
    return "\n\n".join(f"**Q:** {i['q']}\n\n```sql\n{i['sql'].strip()}\n```" for i in items)


def set_examples(text: str, block: str) -> str:
    """Replace the `# Examples` section, or add it at the end."""
    text = text.replace("\r\n", "\n")
    text = re.sub(r"(?ms)^# Examples\s*\n.*?(?=^# |\Z)", "", text).rstrip("\n")
    return f"{text}\n\n# Examples\n\n{block}\n"


def main() -> int:
    check_only = "--check" in sys.argv
    data = yaml.safe_load((ROOT / "tools" / "examples.yaml").read_text(encoding="utf-8"))
    bundle = Bundle.load(BUNDLE)
    tables, sensitive = set(bundle.tables()), bundle.sensitive_tables()
    executor = ReadOnlyExecutor(URL, 3000, 100)
    executor.verify()
    problems, empty = [], []
    for table, items in data.items():
        if table not in tables or table in sensitive:
            problems.append(f"{table}: not a readable table in the bundle")
            continue
        for i in items:
            check = validate_sql(i["sql"], tables, sensitive, 100)
            if not check.ok:
                problems.append(f"{table}: validator rejected '{i['q']}': {'; '.join(check.reasons)}")
                continue
            try:
                if executor.run(check.sql).row_count == 0:
                    empty.append(f"{table}: '{i['q']}' returns no rows on the sample data")
            except SqlExecutionError as e:
                problems.append(f"{table}: '{i['q']}' failed on the database: {e}")
    for line in empty:
        print("note   ", line)
    for line in problems:
        print("ERROR  ", line)
    if problems:
        return 1
    uncovered = sorted(tables - sensitive - set(data))
    if uncovered:
        print("note    tables without examples:", ", ".join(uncovered))
    if check_only:
        print(f"{sum(len(v) for v in data.values())} examples valid")
        return 0
    written = 0
    for table, items in data.items():
        path = BUNDLE / bundle.table(table).path.lstrip("/")
        path.write_text(set_examples(path.read_text(encoding="utf-8"), render(items)), encoding="utf-8", newline="\n")
        written += 1
    print(f"examples written to {written} table files")
    return 0


if __name__ == "__main__":
    sys.exit(main())
