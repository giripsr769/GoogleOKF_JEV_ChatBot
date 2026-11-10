"""End-to-end evaluation of the whole pipeline on the question sets, with the real OpenAI, TypeSafe and database.

    python tools/eval_pipeline.py                # both sets
    python tools/eval_pipeline.py --only held    # just the held-out set
    python tools/eval_pipeline.py -v             # print every question, not only the problems

What counts as correct:
  * questions with expected tables : answered, and the SQL used at least those tables
  * expect "blocked" / "denied"    : refused (a Refusal, never an answer)
DATABASE_URL comes from SMOKE_DATABASE_URL (default: the Docker read-only login), never from .env.
Costs a few cents. Results are written to tests/last_run_pipeline.json (git-ignored).
"""
import asyncio
import contextvars
import json
import os
import statistics
import sys
import time
from pathlib import Path

from okf_chat.config import get_settings
from okf_chat.core.pipeline import Refusal
from okf_chat.factory import build_pipeline

ROOT = Path(__file__).resolve().parent.parent
URL = os.getenv("SMOKE_DATABASE_URL", "postgresql://okf_readonly:okf_readonly@localhost:5433/shop")
CONCURRENCY = 4
_RECORD: contextvars.ContextVar[list] = contextvars.ContextVar("record")


class RecordingJudge:
    """Wraps Jev and notes every call (which questions, what scores, and the SQL when there is one) for the current request."""

    def __init__(self, inner):
        self.inner = inner

    async def noul(self, state, questions):
        scores = await self.inner.noul(state, questions)
        _RECORD.get([]).append({
            "ids": sorted(questions)[:6], "scores": scores,
            "sql": state.get("sql") if isinstance(state, dict) else None,
            "reply": state.get("reply") if isinstance(state, dict) else None,
        })
        return scores

    async def aclose(self):
        await self.inner.aclose()


def load(only: str | None):
    # "fresh" was written after the guards were calibrated on the other two, so it is the honest generalisation check
    sets = [("tuning", "eval_questions.json"), ("held-out", "heldout_questions.json"), ("fresh", "fresh_questions.json")]
    for name, fn in sets:
        if only and not name.startswith(only):
            continue
        for item in json.loads((ROOT / "tests" / "data" / fn).read_text(encoding="utf-8")):
            yield name, item


async def run_one(pipeline, sem, name, item):
    async with sem:
        calls: list = []
        _RECORD.set(calls)  # each request runs in its own task, so this list belongs to this question only
        t0 = time.perf_counter()
        try:
            r = await pipeline.ask(item["q"])
            outcome = {"kind": "answered", "tables": r.tables_used, "attempts": r.attempts, "answer": r.answer, "sql": r.sql, "rows": r.row_count, "risk": r.risk_score}
        except Refusal as ref:
            outcome = {"kind": "refused", "status": ref.status_code, "code": ref.code, "detail": ref.detail}
        except Exception as exc:  # a bug, not a refusal
            outcome = {"kind": "crashed", "error": f"{type(exc).__name__}: {exc}"}
        outcome["seconds"] = time.perf_counter() - t0
        outcome["jev_calls"] = calls
        return name, item, outcome


def judge(item, o) -> tuple[bool, str]:
    expect = item.get("expect")
    if expect in ("blocked", "denied"):
        return o["kind"] == "refused", "should have been refused" if o["kind"] != "refused" else ""
    if o["kind"] != "answered":
        return False, f"refused/crashed: {o.get('code') or o.get('error')} {o.get('detail', '')}"
    missing = set(item["tables"]) - set(o["tables"])
    return (not missing), f"SQL did not use {sorted(missing)}" if missing else ""


async def main(argv: list[str]) -> None:
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    verbose = "-v" in argv
    s = get_settings()
    pipeline = build_pipeline(s, database_url=URL)
    pipeline.judge = pipeline.navigator.judge = RecordingJudge(pipeline.judge)
    sem = asyncio.Semaphore(CONCURRENCY)
    try:
        t0 = time.perf_counter()
        results = await asyncio.gather(*(run_one(pipeline, sem, n, i) for n, i in load(only)))
        wall = time.perf_counter() - t0
    finally:
        await pipeline.aclose()

    stats: dict[str, list[bool]] = {}
    seconds, attempts, problems = [], [], []
    for name, item, o in results:
        ok, why = judge(item, o)
        group = f"{name}/{'refusal' if item.get('expect') else 'answer'}"
        stats.setdefault(group, []).append(ok)
        if o["kind"] == "answered":
            seconds.append(o["seconds"])
            attempts.append(o["attempts"])
        if verbose or not ok:
            tag = "ok " if ok else "BAD"
            print(f"{tag} [{name}] {item['q']}  ({o['seconds']:.1f}s)")
            if o["kind"] == "answered":
                print(f"      tables={o['tables']} attempts={o['attempts']} rows={o['rows']} risk={o['risk']:.2f}\n      A: {o['answer'][:150]}")
            elif o["kind"] == "refused":
                print(f"      {o['status']} {o['code']}: {o['detail'][:140]}")
            else:
                print(f"      {o['error']}")
            if why:
                print(f"      -> {why}")
            if item.get("note"):
                print(f"      note: {item['note']}")
        if not ok:
            problems.append(item["q"])

    print("\n=== summary")
    for group, oks in sorted(stats.items()):
        print(f"{group:<18} {sum(oks)}/{len(oks)}")
    if seconds:
        qs = statistics.quantiles(seconds, n=20) if len(seconds) > 1 else [seconds[0]] * 19
        print(f"latency (answered): median {statistics.median(seconds):.1f}s   p95 {qs[18]:.1f}s   max {max(seconds):.1f}s   "
              f"(wall time for all with {CONCURRENCY} at once: {wall:.0f}s)")
        print(f"SQL drafts needed: {dict(sorted({a: attempts.count(a) for a in set(attempts)}.items()))}")
    (ROOT / "tests" / "last_run_pipeline.json").write_text(
        json.dumps([{"set": n, "q": i["q"], "expect": i.get("expect"), **o} for n, i, o in results], indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
