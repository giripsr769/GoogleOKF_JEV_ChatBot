"""Measure table selection on the question sets, using the real TypeSafe API (scores are cached on disk).

    python tools/eval_navigator.py                 # compare wordings x selection rules
    python tools/eval_navigator.py --refresh       # ignore the cache and call the API again
    python tools/eval_navigator.py -v VARIANT RULE # list the failing questions for one combination

Tuning set = tests/data/eval_questions.json, held-out set = tests/data/heldout_questions.json. Pick settings on the
tuning set, then look at the held-out numbers once to confirm they were not overfitted.
"""
import asyncio
import json
import sys
from dataclasses import replace
from pathlib import Path

from typesafe_sdk import Noul

from okf_chat.config import get_settings
from okf_chat.core.navigator import NavPolicy, Navigator, table_question
from okf_chat.core.okf_loader import Bundle
from okf_chat.guardrails.jev_client import JevClient

ROOT = Path(__file__).resolve().parent.parent
DATA = ROOT / "tests" / "data"


# ---------------------------------------------------------------- question wordings to compare
def v1_plain(name, c, group, max_columns):
    """No group context, original wording."""
    return table_question(name, c, None, max_columns)


def v2_group(name, c, group, max_columns):
    """With the group label: the wording shipped until 2026-11-07 (kept frozen here so it can still be compared)."""
    cols = c.column_names[:max_columns]
    more = f", and {len(c.column_names) - max_columns} more" if len(c.column_names) > max_columns else ""
    tags = f" Keywords: {', '.join(c.tags[:8])}." if c.tags else ""
    where = f" It belongs to the '{group}' group." if group else ""
    return Noul(
        instructions=f"Is the database table '{name}' needed to answer this message? {c.description}{where}{tags} Columns: {', '.join(cols)}{more}.",
        criteria={
            "true": "The message asks about, filters by, groups by or needs data stored in this table",
            "false": "This table holds nothing the message needs",
        },
    )


def v4_entity(name, c, group, max_columns):
    """The shipped default: a table is also needed when the message names a specific item stored in it."""
    return table_question(name, c, group, max_columns)


def v3_query(name, c, group, max_columns):
    """Asks whether a SQL query would have to read this table."""
    cols = ", ".join(c.column_names[:max_columns])
    where = f" Group: {group}." if group else ""
    return Noul(
        instructions=f"A SQL query will answer this message from a database. Would that query need to read the table '{name}'? {c.description}{where} Columns: {cols}.",
        criteria={
            "true": "The query would select, filter, join or group using columns of this table",
            "false": "The query would not touch this table",
        },
    )


VARIANTS = {"v1_plain": v1_plain, "v2_group": v2_group, "v4_entity": v4_entity}  # v3_query was noisier; its cached scores can be deleted

BASE = NavPolicy(drop_disconnected=False, neighbor_at=None)  # the original behaviour
HARD_DROP = replace(BASE, drop_disconnected=True, keep_unjoinable_at=None)
RULES = {
    "base": BASE,
    "hard-drop+nb.15": replace(HARD_DROP, neighbor_at=0.15),
    "drop.8": replace(BASE, drop_disconnected=True, keep_unjoinable_at=0.8),
    "drop.8+nb.15": replace(BASE, drop_disconnected=True, keep_unjoinable_at=0.8, neighbor_at=0.15),
    "drop.9+nb.15": replace(BASE, drop_disconnected=True, keep_unjoinable_at=0.9, neighbor_at=0.15),
    "drop.8+nb.15,sel.6": replace(BASE, drop_disconnected=True, keep_unjoinable_at=0.8, neighbor_at=0.15, select_at=0.6),
}


def load_cases(filename: str) -> list[dict]:
    """Navigation cases: questions with expected tables, plus the salary questions that must hit a sensitive table."""
    cases = []
    for x in json.loads((DATA / filename).read_text(encoding="utf-8")):
        if "tables" in x:
            cases.append({"q": x["q"], "need": set(x["tables"]), "sensitive": None})
        elif x.get("expect") == "denied" and "salar" in x["q"].lower():
            cases.append({"q": x["q"], "need": set(), "sensitive": "salaries"})
    return cases


async def score_variant(nav: Navigator, variant: str, questions: list[str], refresh: bool) -> dict[str, dict[str, float]]:
    cache = ROOT / "tests" / f"last_run_nav_{variant}.json"  # git-ignored (tests/last_run*.json)
    saved = {} if refresh or not cache.exists() else json.loads(cache.read_text(encoding="utf-8"))
    todo = [q for q in questions if q not in saved]
    sem = asyncio.Semaphore(6)

    async def one(q):
        async with sem:
            qs = {n: nav.build_question(n, nav.concepts[n], nav.group_of.get(n), nav.policy.max_columns_in_question) for n in nav.concepts}
            saved[q] = await nav._score(q, qs)

    await asyncio.gather(*(one(q) for q in todo))
    cache.write_text(json.dumps(saved), encoding="utf-8")
    return saved


def evaluate(bundle: Bundle, policy: NavPolicy, cases: list[dict], scores: dict[str, dict[str, float]]):
    nav = Navigator(bundle, None, policy)
    ok = total_tables = extras = 0
    failures = []
    for case in cases:
        r = nav.decide(scores[case["q"]])
        if case["sensitive"]:
            good = case["sensitive"] in r.sensitive_hit
        else:
            good = case["need"] <= set(r.tables)
            total_tables += len(r.tables)
            extras += len(set(r.tables) - case["need"])
        ok += good
        if not good:
            failures.append((case, r))
    plain = [c for c in cases if not c["sensitive"]]
    return ok, len(cases), total_tables / max(len(plain), 1), extras / max(len(plain), 1), failures


async def main(argv: list[str]) -> None:
    refresh = "--refresh" in argv
    s = get_settings()
    bundle = Bundle.load(s.okf_bundle_dir)
    tune, held, named = load_cases("eval_questions.json"), load_cases("heldout_questions.json"), load_cases("entity_questions.json")
    questions = [c["q"] for c in tune + held + named]
    jev = JevClient(s.typesafe_api_key, s.jev_model, s.jev_timeout_s)
    all_scores = {}
    try:
        for name, builder in VARIANTS.items():
            nav = Navigator(bundle, jev, BASE, builder)
            all_scores[name] = await score_variant(nav, name, questions, refresh)
    finally:
        await jev.aclose()

    if "-v" in argv:
        variant, rule = argv[argv.index("-v") + 1 : argv.index("-v") + 3]
        for label, cases in (("TUNING", tune), ("HELD-OUT", held), ("NAMED ITEMS", named)):
            *_, failures = evaluate(bundle, RULES[rule], cases, all_scores[variant])
            print(f"--- {label} failures for {variant} / {rule}")
            for case, r in failures:
                top = sorted(r.scored.items(), key=lambda kv: -kv[1])[:6]
                print(f"  {case['q']}\n     need={sorted(case['need']) or case['sensitive']} got={r.tables} hit={r.sensitive_hit}")
                print("     top: " + ", ".join(f"{k}={v:.2f}" for k, v in top))
        return

    print(f"{len(tune)} tuning questions, {len(held)} held-out, {len(named)} named-item\n")
    print(f"{'wording':<10} {'selection rule':<18} | {'TUNING recall':>13} {'tables':>6} {'extra':>5} | {'HELD-OUT recall':>15} {'tables':>6} {'extra':>5} | {'NAMED recall':>12} {'tables':>6} {'extra':>5}")
    for vname in VARIANTS:
        for rname, policy in RULES.items():
            a = evaluate(bundle, policy, tune, all_scores[vname])
            b = evaluate(bundle, policy, held, all_scores[vname])
            d = evaluate(bundle, policy, named, all_scores[vname])
            print(f"{vname:<10} {rname:<18} | {a[0]:>6}/{a[1]:<3} {a[2]:>8.1f} {a[3]:>5.1f} | {b[0]:>8}/{b[1]:<3} {b[2]:>8.1f} {b[3]:>5.1f} | {d[0]:>6}/{d[1]:<3} {d[2]:>8.1f} {d[3]:>5.1f}")
        print()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:]))
