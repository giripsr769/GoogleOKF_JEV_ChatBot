"""Deterministic test of generate_validated retry rules, using a fake OpenAI client (no network).
Run inside the container: python tests/test_retry.py"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src.okf_loader import OKFTable  # noqa: E402
from src.security import SQLParseError, SQLValidationError  # noqa: E402
from src.sql_generator import generate_validated  # noqa: E402

TABLES = [OKFTable(table="orders", description="d")]


class Fake:
    def __init__(self, outputs):
        self.outputs, self.prompts = list(outputs), []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kw):
        self.prompts.append(kw["messages"][1]["content"])
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.outputs.pop(0)))])


async def case(name, outputs, expect_exc=None, expect_attempts=None, expect_calls=None):
    c = Fake(outputs)
    try:
        sql, attempts = await generate_validated(c, "q", TABLES)
        got = ("ok", attempts)
    except SQLValidationError as e:
        got = (type(e).__name__, None)
    want = (expect_exc or "ok", expect_attempts)
    good = got == want and len(c.prompts) == expect_calls
    print(f"{'PASS' if good else 'FAIL'}  {name}: got={got} calls={len(c.prompts)}")
    return good, c


async def main():
    results = []
    results.append((await case("valid first time", ["SELECT id FROM orders"], None, 1, 1))[0])
    ok, c = await case("garbled then valid -> retry succeeds", ["SELECT id FROM orders\u201d\u3011\u3010", "SELECT id FROM orders"], None, 2, 2)
    results.append(ok and "not valid SQL" in c.prompts[1] and "not valid SQL" not in c.prompts[0])
    results.append((await case("empty then valid -> retry succeeds", ["", "SELECT id FROM orders"], None, 2, 2))[0])
    results.append((await case("garbled twice -> gives up after 2", ["SELEC ((", "SELEC (("], "SQLParseError", None, 2))[0])
    results.append((await case("DROP is NOT retried", ["DROP TABLE orders", "SELECT id FROM orders"], "SQLValidationError", None, 1))[0])
    results.append((await case("forbidden table NOT retried", ["SELECT * FROM pg_user", "SELECT id FROM orders"], "SQLValidationError", None, 1))[0])
    results.append((await case("pg_sleep NOT retried", ["SELECT pg_sleep(5)", "SELECT id FROM orders"], "SQLValidationError", None, 1))[0])
    print("\nALL PASS" if all(results) else "\nSOME FAILED")
    sys.exit(0 if all(results) else 1)


asyncio.run(main())
