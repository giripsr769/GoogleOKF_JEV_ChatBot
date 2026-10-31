"""Timeout behaviour of the pipeline, without needing a slow upstream: dependencies are replaced with hung or
timing-out fakes and the endpoint function is called directly (no HTTP layer).
Run inside the container: python tests/test_timeout.py"""
import asyncio
import sys
import time
from pathlib import Path

import httpx2
import openai
from fastapi import HTTPException
from openai import AsyncOpenAI
from typesafe_sdk import TypeSafeAPITimeoutError

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import main  # noqa: E402
from src.jev_guard import JevGuard, scope_of  # noqa: E402
from src.okf_loader import SchemaIndex  # noqa: E402

fails = 0


def check(name, ok, extra=""):
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}{('  [' + str(extra) + ']') if extra else ''}")


async def call(q="How many customers are there in each country"):
    """returns (status_code, detail_or_response, seconds)"""
    t = time.perf_counter()
    try:
        r = await main.text_to_sql(main.QueryRequest(question=q))
        return 200, r, time.perf_counter() - t
    except HTTPException as e:
        return e.status_code, e.detail, time.perf_counter() - t


async def main_test():
    oc = AsyncOpenAI(timeout=main.OPENAI_TIMEOUT_S, max_retries=1)
    idx = SchemaIndex(oc)
    await idx.build_or_load()
    jev = JevGuard(scope=scope_of(idx.tables), timeout=main.JEV_TIMEOUT_S)
    main.app.state.openai, main.app.state.index, main.app.state.jev = oc, idx, jev
    real_gate = jev.gate

    check("defaults: pipeline 30s, OpenAI 20s, Jev 10s, DB 3s",
          (main.PIPELINE_TIMEOUT_S, main.OPENAI_TIMEOUT_S, main.JEV_TIMEOUT_S, main.STATEMENT_TIMEOUT_MS) == (30, 20, 10, 3000),
          (main.PIPELINE_TIMEOUT_S, main.OPENAI_TIMEOUT_S, main.JEV_TIMEOUT_S, main.STATEMENT_TIMEOUT_MS))
    check("OpenAI client has the configured timeout and 1 retry", getattr(oc.timeout, 'read', oc.timeout) == main.OPENAI_TIMEOUT_S and oc.max_retries == 1,
          (oc.timeout, oc.max_retries))

    # 1. a hung dependency: the request is cut off at the overall budget instead of hanging
    async def hung_gate(q):
        await asyncio.sleep(120)

    jev.gate = hung_gate
    main.PIPELINE_TIMEOUT_S = 1.0
    code, detail, took = await call()
    check("hung dependency -> 504 at the budget (about 1s, not 120s)", code == 504 and 0.9 < took < 3, f"{code} after {took:.1f}s")
    check("message says it timed out and how long", "timed out" in detail and "1 seconds" in detail, detail)

    # 2. SDK timeout errors become the same clean 504 (not a 500)
    main.PIPELINE_TIMEOUT_S = 30
    for label, exc in (
        ("OpenAI timeout", openai.APITimeoutError(request=httpx2.Request("POST", "http://x"))),
        ("TypeSafe (Jev) timeout", TypeSafeAPITimeoutError("slow")),
    ):
        async def boom(q, _e=exc):
            raise _e

        jev.gate = boom
        code, detail, took = await call()
        check(f"{label} -> 504", code == 504 and "timed out" in detail, f"{code} {detail}")

    # 3. unrelated errors are not disguised as timeouts
    async def other(q):
        raise ValueError("unrelated bug")

    jev.gate = other
    try:
        code, detail, _ = await call()
        check("unrelated errors are not reported as timeouts", code != 504, code)
    except ValueError:
        check("unrelated errors are not reported as timeouts (propagate as real errors)", True)

    # 4. a normal request is unaffected by the budget (real Jev + OpenAI + DB)
    jev.gate = real_gate
    code, resp, took = await call()
    check("normal request still succeeds", code == 200 and resp.row_count >= 1, f"{code} in {took:.1f}s")

    # 5. the database's own 3s limit still gives its own, different message
    real_exec = main._execute
    main._execute = lambda sql: real_exec("SELECT pg_sleep(5)")
    try:
        code, detail, took = await call()
    finally:
        main._execute = real_exec
    check("DB 3s limit keeps its own 504 message", code == 504 and "3 second" in str(detail) and "timed out" not in str(detail), f"{code} {detail} ({took:.1f}s)")

    await jev.aclose()


asyncio.run(main_test())
print(f"\n{'ALL PASS' if not fails else str(fails) + ' FAILED'}")
sys.exit(1 if fails else 0)
