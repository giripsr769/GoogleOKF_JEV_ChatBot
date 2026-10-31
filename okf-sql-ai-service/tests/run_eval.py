"""Pipeline evaluation: runs tests/eval_questions.json through every stage and reports metrics.

Run inside the container (needs the keys, FAISS index and database):
    docker compose exec api python tests/run_eval.py [--limit N] [--domain hr] [--concurrency 4]

Per positive question it measures:
  FAISS recall@k    every expected table is among the top-k vector hits
  rerank recall     every expected table survives the Jev rerank
  rerank noise      extra tables kept beyond the expected ones
  pipeline pass     outcome is OK and the generated SQL references every expected table
Attack questions must be blocked by the gate; restricted ones must never return data.
"""
import argparse
import asyncio
import json
import statistics
import sys
import time
from pathlib import Path

import psycopg2
import psycopg2.errors
import sqlglot
from openai import AsyncOpenAI
from sqlglot import exp

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from src.jev_guard import MAX_RISK, RERANK_THRESHOLD, JevGuard, scope_of  # noqa: E402
from src.join_paths import expand as expand_join_paths  # noqa: E402
from src.main import _execute  # noqa: E402
from src.okf_loader import SEARCH_K, SchemaIndex  # noqa: E402
from src.security import SQLValidationError  # noqa: E402
from src.sql_generator import generate_validated  # noqa: E402

KS = (4, 6, 8, 10, 12)  # recall@k reported for each; FAISS is queried once at max(KS)
HERE = Path(__file__).resolve().parent


def sql_tables(sql: str) -> set[str]:
    return {t.name.lower() for t in sqlglot.parse_one(sql, read="postgres").find_all(exp.Table)}


async def run_one(item: dict, oc, idx, jev) -> dict:
    r: dict = {"q": item["q"], "domain": item["domain"], "expect": item.get("expect", "answer"),
               "expected": item.get("tables", []), "note": item.get("note", "")}
    t0 = time.perf_counter()
    try:
        gate = await jev.gate(item["q"])
        r["intent"] = gate.intent
        if not gate.allowed:
            r["outcome"] = "gate_blocked"
            return r

        ranked = await idx.search(item["q"], k=max(KS))
        r["ranked"] = [t.table for t in ranked]
        candidates = ranked[:SEARCH_K]
        kept = await jev.rerank(item["q"], candidates)
        r["reranked"] = [t.table for t in kept]
        kept, r["bridges"] = await expand_join_paths(jev, idx, item["q"], kept)
        r["kept"] = [t.table for t in kept]

        try:
            sql, r["attempts"] = await generate_validated(oc, item["q"], kept)
        except SQLValidationError as e:
            r["outcome"], r["detail"] = "rejected_sql", str(e)[:120]
            return r
        r["sql"] = sql
        r["sql_tables"] = sorted(sql_tables(sql))
        r["risk"] = round(await jev.risk(item["q"], sql), 2)
        if r["risk"] > MAX_RISK:
            r["outcome"] = "rejected_risk"
            return r
        try:
            _, rows = await asyncio.to_thread(_execute, sql)
            r["outcome"], r["rows"] = "ok", len(rows)
        except psycopg2.errors.InsufficientPrivilege:
            r["outcome"] = "denied"
        except psycopg2.errors.QueryCanceled:
            r["outcome"] = "timeout"
        except psycopg2.Error as e:
            r["outcome"], r["detail"] = "db_error", str(e).strip()[:120]
    except Exception as e:  # noqa: BLE001 - report, never abort the run
        r["outcome"], r["detail"] = "error", f"{type(e).__name__}: {e}"[:160]
    finally:
        r["ms"] = int((time.perf_counter() - t0) * 1000)
    return r


def judge(r: dict) -> bool:
    if r["expect"] == "blocked":
        return r["outcome"] == "gate_blocked"
    if r["expect"] == "denied":
        return r["outcome"] != "ok"
    return r["outcome"] == "ok" and set(r["expected"]) <= set(r.get("sql_tables", []))


def pct(n: int, d: int) -> str:
    return f"{n}/{d} ({100 * n / d:.0f}%)" if d else "n/a"


def report(results: list[dict]) -> None:
    pos = [r for r in results if r["expect"] == "answer"]
    gated = [r for r in pos if r["outcome"] != "gate_blocked"]
    ranked = [r for r in gated if "ranked" in r]
    print("\n" + "=" * 70)
    print(f"GATE        answerable allowed: {pct(len(gated), len(pos))}")
    att = [r for r in results if r["expect"] == "blocked"]
    print(f"            attacks blocked:    {pct(sum(r['outcome'] == 'gate_blocked' for r in att), len(att))}")
    print("FAISS       recall@k (all expected tables in top-k):")
    for k in KS:
        hit = sum(set(r["expected"]) <= set(r["ranked"][:k]) for r in ranked)
        print(f"            k={k:<3} {pct(hit, len(ranked))}{'   <- configured SEARCH_K' if k == SEARCH_K else ''}")
    kept_all = [r for r in ranked if set(r["expected"]) <= set(r["kept"])]
    pre_all = [r for r in ranked if set(r["expected"]) <= set(r["reranked"])]
    noise = [len(set(r["kept"]) - set(r["expected"])) for r in ranked]
    bridged = [r for r in ranked if r["bridges"]]
    print(f"RERANK      expected tables kept: {pct(len(pre_all), len(ranked))}   (threshold {RERANK_THRESHOLD})")
    print(f"JOIN PATHS  after bridge expansion: {pct(len(kept_all), len(ranked))}   (bridges added on {len(bridged)} questions: "
          f"{[(r['q'][:30], r['bridges']) for r in bridged]})")
    if noise:
        print(f"            avg tables kept {statistics.mean(len(r['kept']) for r in ranked):.1f}, avg extra {statistics.mean(noise):.1f} (of {SEARCH_K} candidates)")
    outcomes: dict[str, int] = {}
    for r in pos:
        outcomes[r["outcome"]] = outcomes.get(r["outcome"], 0) + 1
    print(f"PIPELINE    answerable outcomes: {outcomes}")
    retried = [r for r in pos if r.get("attempts", 1) > 1]
    if retried:
        print(f"            regenerated after unparseable SQL: {len(retried)} ({[r['q'][:34] for r in retried]})")
    ok_pass = [r for r in pos if judge(r)]
    print(f"            correct (ok + SQL uses expected tables): {pct(len(ok_pass), len(pos))}")
    rest = [r for r in results if r["expect"] == "denied"]
    print(f"RESTRICTED  never returned data: {pct(sum(judge(r) for r in rest), len(rest))}")
    ms = sorted(r["ms"] for r in results if "ms" in r)
    if ms:
        print(f"LATENCY     avg {statistics.mean(ms):.0f} ms, p95 {ms[int(0.95 * (len(ms) - 1))]} ms")
    print(f"OVERALL     {pct(sum(judge(r) for r in results), len(results))}")

    by_dom: dict[str, list[bool]] = {}
    for r in results:
        by_dom.setdefault(r["domain"], []).append(judge(r))
    print("BY DOMAIN   " + ", ".join(f"{d} {sum(v)}/{len(v)}" for d, v in by_dom.items()))

    fails = [r for r in results if not judge(r)]
    if fails:
        print("\nFAILURES")
        for r in fails:
            print(f"- [{r['domain']}] {r['q']}\n    outcome={r['outcome']} {r.get('detail', '')}")
            if r["expect"] == "answer":
                print(f"    expected={r['expected']} ranked_top={r.get('ranked', [])[:SEARCH_K]} reranked={r.get('reranked')} bridges={r.get('bridges')} kept={r.get('kept')} sql_tables={r.get('sql_tables')} risk={r.get('risk')}")
            if r.get("sql"):
                print(f"    sql={r['sql'][:200]}")


async def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--limit", type=int)
    ap.add_argument("--domain")
    ap.add_argument("--file", default="eval_questions.json", help="question file in tests/ (e.g. heldout_questions.json)")
    ap.add_argument("--concurrency", type=int, default=4)
    args = ap.parse_args()

    items = json.loads((HERE / args.file).read_text(encoding="utf-8"))
    if args.domain:
        items = [i for i in items if i["domain"] == args.domain]
    if args.limit:
        items = items[: args.limit]

    oc = AsyncOpenAI()
    idx = SchemaIndex(oc)
    await idx.build_or_load()
    jev = JevGuard(scope=scope_of(idx.tables))
    print(f"{len(items)} questions | {len(idx.tables)} tables indexed | SEARCH_K={SEARCH_K} | RERANK_THRESHOLD={RERANK_THRESHOLD} | MAX_RISK={MAX_RISK}")

    sem = asyncio.Semaphore(args.concurrency)

    async def guarded(item):
        async with sem:
            r = await run_one(item, oc, idx, jev)
            print(f"  {'PASS' if judge(r) else 'FAIL'} {r['outcome']:<14} {r['q'][:62]}", flush=True)
            return r

    results = await asyncio.gather(*(guarded(i) for i in items))
    await jev.aclose()
    report(results)
    (HERE / f"last_run_{Path(args.file).stem}.json").write_text(json.dumps(results, indent=2), encoding="utf-8")
    print(f"\nfull results: tests/last_run_{Path(args.file).stem}.json")


if __name__ == "__main__":
    asyncio.run(main())
