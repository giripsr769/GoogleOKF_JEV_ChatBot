"""Live check of the two agents inside the whole chain, using real OpenAI, TypeSafe and the Docker database:
navigator -> SQL writer -> validator -> read-only executor -> answer writer.

    python tools/smoke_agents.py            # the default question set
    python tools/smoke_agents.py "your question here"

This is a preview of the pipeline (Step 9 adds guards, retries and a time budget). DATABASE_URL comes from
SMOKE_DATABASE_URL, never from .env.
"""
import asyncio
import os
import sys
import time

from okf_chat.agents.answer_writer import AnswerWriter
from okf_chat.agents.llm import LlmError, build_llm, crewai_runner
from okf_chat.agents.sql_writer import SqlWriter
from okf_chat.config import get_settings
from okf_chat.core.navigator import NavPolicy, Navigator
from okf_chat.core.okf_loader import Bundle
from okf_chat.core.sql_executor import ReadOnlyExecutor, SqlExecutionError
from okf_chat.core.sql_validator import validate_sql
from okf_chat.guardrails.jev_client import JevClient

URL = os.getenv("SMOKE_DATABASE_URL", "postgresql://okf_readonly:okf_readonly@localhost:5433/shop")

QUESTIONS = [
    "Top 3 customers by total order value",
    "How many employees do we have?",
    "Which products are below their reorder level?",
    "What is our total revenue excluding cancelled orders?",
    "How many open tickets do customers in India have?",
    "List the products each customer has bought",
    "Show me the top 3 customers in a table",
    "Which suppliers supply the Laptop?",
    "What was the weather in Chennai yesterday?",
]


async def main(questions: list[str]) -> None:
    s = get_settings()
    bundle = Bundle.load(s.okf_bundle_dir)
    jev = JevClient(s.typesafe_api_key, s.jev_model, s.jev_timeout_s)
    nav = Navigator(bundle, jev, NavPolicy(max_tables=s.navigator_max_tables))
    runner = crewai_runner(build_llm(s), s.openai_timeout_s)
    writer, answerer = SqlWriter(runner, s.max_result_rows), AnswerWriter(runner, s.answer_max_rows, s.natural_answers)
    executor = ReadOnlyExecutor(URL, s.statement_timeout_ms, s.max_result_rows)
    executor.verify()
    sensitive = bundle.sensitive_tables()
    try:
        for q in questions:
            print(f"\nQ: {q}")
            t = {}
            t0 = time.perf_counter()
            nr = await nav.navigate(q)
            t["navigate"] = time.perf_counter() - t0
            if not nr.found:
                print("   navigator found no table")
                continue
            print(f"   tables: {nr.tables}")
            try:
                t0 = time.perf_counter()
                draft = await writer.write(q, nav.render_context(nr.tables))
                t["sql"] = time.perf_counter() - t0
                if not draft.can_answer:
                    print(f"   writer: cannot answer: {draft.reason}")
                    continue
                check = validate_sql(draft.sql, nr.tables, sensitive, s.max_result_rows)
                print(f"   sql: {check.sql if check.ok else draft.sql}")
                if not check.ok:
                    print(f"   validator: BLOCKED {check.code}: {check.reasons[0]}")
                    continue
                t0 = time.perf_counter()
                result = await executor.execute(check.sql)
                t["db"] = time.perf_counter() - t0
                t0 = time.perf_counter()
                ans = await answerer.write(q, result.columns, result.rows, result.row_count, result.truncated)
                t["answer"] = time.perf_counter() - t0
                print(f"   rows: {result.row_count}   show_table={ans.show_table}   natural={ans.natural}")
                print(f"   A: {ans.text}")
            except (LlmError, SqlExecutionError) as e:
                print(f"   FAILED: {getattr(e, 'code', 'llm')}: {getattr(e, 'message', e)}")
            print("   timings: " + "  ".join(f"{k}={v:.1f}s" for k, v in t.items()) + f"  total={sum(t.values()):.1f}s")
    finally:
        await jev.aclose()


if __name__ == "__main__":
    asyncio.run(main(sys.argv[1:] or QUESTIONS))
