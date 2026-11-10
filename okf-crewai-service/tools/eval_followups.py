"""End-to-end evaluation of follow-up questions (chat memory), with the real OpenAI, TypeSafe and database.

    python tools/eval_followups.py                  # all conversations
    python tools/eval_followups.py --only attack    # one category
    python tools/eval_followups.py -v               # print every turn, not only the problems

Each conversation in tests/data/followup_conversations.json is asked turn by turn in one session. Conversations run
side by side; the turns inside one run in order. A turn is correct when:
  * "expect": "blocked" / "denied" : it was refused (a Refusal, never an answer)
  * otherwise                      : it was answered and
      "tables"   : the SQL used at least these tables
      "sql_has"  : the SQL contains each of these (case-insensitive)
      "sql_not"  : the SQL contains none of these
      "table"    : show_table matches (the user asked for / did not ask for a table)
A conversation passes only if every turn is correct.
DATABASE_URL comes from SMOKE_DATABASE_URL (default: the Docker read-only login), never from .env.
Costs a few cents. Results are written to tests/last_run_followups.json (git-ignored).
"""
import asyncio
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


def check(turn: dict, o: dict) -> tuple[bool, str]:
    if turn.get("expect") in ("blocked", "denied"):
        return o["kind"] == "refused", "should have been refused" if o["kind"] != "refused" else ""
    if o["kind"] != "answered":
        return False, f"refused/crashed: {o.get('code') or o.get('error')} {o.get('detail', '')}"
    sql = o["sql"].lower()
    problems = []
    if missing := set(turn.get("tables", [])) - set(o["tables"]):
        problems.append(f"SQL did not use {sorted(missing)}")
    problems += [f"SQL lacks '{s}'" for s in turn.get("sql_has", []) if s.lower() not in sql]
    problems += [f"SQL should not contain '{s}'" for s in turn.get("sql_not", []) if s.lower() in sql]
    if "table" in turn and o["show_table"] != turn["table"]:
        problems.append(f"show_table is {o['show_table']}, expected {turn['table']}")
    return not problems, "; ".join(problems)


async def run_conversation(pipeline, sem, conv: dict, run_id: str):
    async with sem:
        session = f"eval-{run_id}-{conv['id']}"
        turns = []
        for turn in conv["turns"]:
            t0 = time.perf_counter()
            try:
                r = await pipeline.ask(turn["q"], session)
                o = {"kind": "answered", "tables": r.tables_used, "sql": r.sql, "answer": r.answer, "rows": r.row_count,
                     "show_table": r.show_table, "standalone": r.standalone, "timings": r.timings_ms}
            except Refusal as ref:
                o = {"kind": "refused", "status": ref.status_code, "code": ref.code, "detail": ref.detail, "standalone": ref.standalone}
            except Exception as exc:  # a bug, not a refusal
                o = {"kind": "crashed", "error": f"{type(exc).__name__}: {exc}"}
            o["seconds"] = time.perf_counter() - t0
            turns.append((turn, o))
        return conv, turns


async def main(argv: list[str]) -> None:
    only = argv[argv.index("--only") + 1] if "--only" in argv else None
    verbose = "-v" in argv
    convs = [c for c in json.loads((ROOT / "tests" / "data" / "followup_conversations.json").read_text(encoding="utf-8"))
             if not only or c["category"].startswith(only)]
    pipeline = build_pipeline(get_settings(), database_url=URL)
    if not (pipeline.memory and pipeline.memory.enabled and pipeline.rewriter):
        raise SystemExit("Chat memory is switched off (MEMORY_TURNS=0): nothing to evaluate.")
    sem = asyncio.Semaphore(CONCURRENCY)
    try:
        t0 = time.perf_counter()
        results = await asyncio.gather(*(run_conversation(pipeline, sem, c, str(int(t0))) for c in convs))
        wall = time.perf_counter() - t0
    finally:
        await pipeline.aclose()

    by_cat: dict[str, list[bool]] = {}
    turn_ok, follow_up_seconds, saved = [], [], []
    for conv, turns in results:
        verdicts = [check(t, o) for t, o in turns]
        passed = all(ok for ok, _ in verdicts)
        by_cat.setdefault(conv["category"], []).append(passed)
        if verbose or not passed:
            print(f"{'ok ' if passed else 'BAD'} [{conv['category']}] {conv['id']}")
            if conv.get("note"):
                print(f"      note: {conv['note']}")
            for (t, o), (ok, why) in zip(turns, verdicts):
                print(f"   {'ok ' if ok else 'BAD'} {t['q']!r}  ({o['seconds']:.1f}s)")
                if o["kind"] == "answered":
                    if o["standalone"] != t["q"]:
                        print(f"        understood as: {o['standalone']}")
                    print(f"        tables={o['tables']} rows={o['rows']} show_table={o['show_table']}\n        A: {o['answer'][:130]}")
                    if not ok or verbose:
                        print(f"        SQL: {o['sql'][:200]}")
                elif o["kind"] == "refused":
                    if o["standalone"] and o["standalone"] != t["q"]:
                        print(f"        understood as: {o['standalone']}")
                    print(f"        {o['status']} {o['code']}: {o['detail'][:120]}")
                else:
                    print(f"        {o['error']}")
                if why:
                    print(f"        -> {why}")
        for (t, o), (ok, _) in zip(turns, verdicts):
            turn_ok.append(ok)
            if o["kind"] == "answered" and "rewrite" in o["timings"]:
                follow_up_seconds.append(o["seconds"])
                saved.append(o["timings"]["rewrite"] / 1000)

    print("\n=== summary (conversations that passed every turn)")
    for cat, oks in sorted(by_cat.items()):
        print(f"{cat:<12} {sum(oks)}/{len(oks)}")
    print(f"turns correct: {sum(turn_ok)}/{len(turn_ok)}")
    if follow_up_seconds:
        print(f"answered follow-ups: median {statistics.median(follow_up_seconds):.1f}s, of which the rewrite step median "
              f"{statistics.median(saved):.1f}s   (wall time for all: {wall:.0f}s)")
    (ROOT / "tests" / "last_run_followups.json").write_text(
        json.dumps([{"id": c["id"], "category": c["category"], "turns": [{"q": t["q"], **o} for t, o in ts]} for c, ts in results],
                   indent=1, default=str), encoding="utf-8")


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
