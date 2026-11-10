"""Live check of the navigator against the real TypeSafe API and the generated OKF bundle.

    python tools/smoke_navigator.py            # compact table
    python tools/smoke_navigator.py -v         # also show the top scores for every question
"""
import asyncio
import sys
import time

from okf_chat.config import get_settings
from okf_chat.core.navigator import Navigator, NavPolicy
from okf_chat.core.okf_loader import Bundle
from okf_chat.guardrails.jev_client import JevClient

# (question, tables the SQL needs, sensitive table expected to be reported)
CASES = [
    ("Top 3 customers by total order value", {"customers", "orders"}, None),
    ("How many employees do we have?", {"employees"}, None),
    ("Which products are below their reorder level?", {"products", "inventory"}, None),
    ("Show total payments by method", {"payments"}, None),
    ("Average product rating by category", {"reviews", "products"}, None),
    ("Which suppliers supply the Laptop?", {"suppliers", "product_suppliers", "products"}, None),
    ("How many tickets does each support agent have?", {"tickets", "support_agents"}, None),
    ("Total revenue per customer country", {"orders", "customers"}, None),
    ("How many open tickets do customers in India have?", {"tickets", "customers"}, None),
    ("List the products each customer has bought", {"customers", "orders", "order_items", "products"}, None),
    ("Which department has the most employees?", {"departments", "employees"}, None),
    ("Total expenses by category", {"expenses"}, None),
    ("What is the average salary?", set(), "salaries"),
    ("Which employees earn the most?", set(), "salaries"),
]


async def main(verbose: bool) -> None:
    s = get_settings()
    jev = JevClient(s.typesafe_api_key, s.jev_model, s.jev_timeout_s)
    nav = Navigator(Bundle.load(s.okf_bundle_dir), jev, NavPolicy(max_tables=s.navigator_max_tables))
    hits = total = 0
    try:
        for question, needed, sensitive in CASES:
            t0 = time.perf_counter()
            r = await nav.navigate(question)
            ms = (time.perf_counter() - t0) * 1000
            got = set(r.tables)
            missing, extra = needed - got, got - needed
            ok = (not missing) if not sensitive else (sensitive in r.sensitive_hit)
            hits += ok
            total += 1
            print(f"{'ok ' if ok else '?? '}{ms:4.0f}ms  {question}")
            print(f"        picked={r.selected} neighbors={r.neighbors} bridges={r.bridges} sensitive_hit={r.sensitive_hit}"
                  + (f" dropped={r.dropped}" if r.dropped else "")
                  + (f"  MISSING={sorted(missing)}" if missing and not sensitive else "")
                  + (f"  extra={sorted(extra)}" if extra and not sensitive else ""))
            if verbose or not ok:
                top = sorted(r.scored.items(), key=lambda kv: -kv[1])[:8]
                print("        top: " + ", ".join(f"{k}={v:.2f}" for k, v in top))
                for t in sorted(needed - set(r.selected)):
                    print(f"        (needed but not picked) {t}={r.scored.get(t, 0):.2f}")
    finally:
        await jev.aclose()
    print(f"\n{hits}/{total} questions got every table they needed (or the right sensitive hit)")


if __name__ == "__main__":
    asyncio.run(main("-v" in sys.argv))
