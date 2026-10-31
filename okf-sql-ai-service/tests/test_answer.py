"""Deterministic tests for src/answer_writer.py using a fake OpenAI client (no network).
Run inside the container: python tests/test_answer.py"""
import asyncio
import sys
from pathlib import Path
from types import SimpleNamespace

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from src import answer_writer as aw  # noqa: E402

fails = 0


def check(name, ok, extra=""):
    global fails
    fails += not ok
    print(f"{'PASS' if ok else 'FAIL'}  {name}{('  [' + str(extra) + ']') if extra else ''}")


class Fake:
    def __init__(self, reply="Asha Rao leads with 958.99.", exc=None, delay=0):
        self.reply, self.exc, self.delay, self.prompts = reply, exc, delay, []
        self.chat = SimpleNamespace(completions=SimpleNamespace(create=self.create))

    async def create(self, **kw):
        self.prompts.append(kw["messages"][1]["content"])
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.exc:
            raise self.exc
        return SimpleNamespace(choices=[SimpleNamespace(message=SimpleNamespace(content=self.reply))])


# ---- table detection
ASKED = ["Show me customers in a table", "List products as a table", "Give me a table of orders", "tabulate revenue by month",
         "Top customers in tabular format", "display it in a grid", "table view please", "show orders as a spreadsheet",
         "Put the results into a table"]
NOT_ASKED = ["Top 5 customers by total order value", "How many rows are in the orders table", "Which tables exist",
             "How many orders are in the table", "What is the tax rate in Germany", "Who sat at the table with the CEO",
             "List all customers", "Show customers in India"]
for q in ASKED:
    check(f"asks for table: {q}", aw.wants_table(q))
for q in NOT_ASKED:
    check(f"no table ask: {q}", not aw.wants_table(q))


async def main():
    cols, rows = ["id", "full_name", "total"], [{"id": i, "full_name": f"C{i}", "total": float(i)} for i in range(1, 51)]

    c = Fake()
    text, need = await aw.compose_answer(c, "Top customers", cols, rows[:3], False)
    check("normal: returns model text, table not needed", text == "Asha Rao leads with 958.99." and need is False, (text, need))
    check("normal: prompt carries question and data", "Top customers" in c.prompts[0] and '"full_name": "C1"' in c.prompts[0])
    check("normal: no 'table below' hint", "table of this data" not in c.prompts[0])

    c = Fake()
    await aw.compose_answer(c, "q", cols, rows[:3], True)
    check("table asked: prompt tells model to keep it brief", "full table" in c.prompts[0] or "A full table" in c.prompts[0])

    c = Fake()
    await aw.compose_answer(c, "q", cols, rows, False)
    sent = c.prompts[0]
    check(f"row cap: only {aw.MAX_ROWS} rows sent", sent.count('"full_name"') == aw.MAX_ROWS, sent.count('"full_name"'))
    check("row cap: model told the true total (50) and that it is partial", "50 rows in total" in sent and f"first {aw.MAX_ROWS}" in sent)

    c = Fake()
    long = [{"note": "x" * 1000}]
    await aw.compose_answer(c, "q", ["note"], long, False)
    check("long cells are clipped before sending", "x" * 300 not in c.prompts[0] and "…" in c.prompts[0])

    c = Fake()
    text, need = await aw.compose_answer(c, "q", ["error"], [{"error": "UNANSWERABLE"}], False)
    check("UNANSWERABLE: friendly message, no model call, no table", text == aw.UNANSWERABLE and need is False and not c.prompts)

    for label, fake in (("exception", Fake(exc=RuntimeError("boom"))), ("empty reply", Fake(reply="  "))):
        text, need = await aw.compose_answer(fake, "q", cols, rows[:4], False)
        check(f"{label}: falls back to plain sentence and asks UI to show the table", text == "I found 4 results." and need is True, (text, need))

    text, need = await aw.compose_answer(Fake(exc=RuntimeError("x")), "q", ["n"], [{"n": 7}], False)
    check("fallback single value", text == "The answer is 7." and need is True, text)
    text, need = await aw.compose_answer(Fake(exc=RuntimeError("x")), "q", cols, [], False)
    check("fallback zero rows", text == "I couldn't find any matching records." and need is True, text)

    aw.TIMEOUT_S = 0.05
    text, need = await aw.compose_answer(Fake(delay=1), "q", cols, rows[:2], False)
    check("slow model times out and falls back", need is True and text == "I found 2 results.", (text, need))
    aw.TIMEOUT_S = 10

    aw.ENABLED = False
    c = Fake()
    text, need = await aw.compose_answer(c, "q", cols, rows[:2], False)
    check("NATURAL_ANSWERS off: no model call, table shown, no text", text == "" and need is True and not c.prompts, (text, need))
    aw.ENABLED = True

    print(f"\n{'ALL PASS' if not fails else str(fails) + ' FAILED'}")
    sys.exit(1 if fails else 0)


asyncio.run(main())
