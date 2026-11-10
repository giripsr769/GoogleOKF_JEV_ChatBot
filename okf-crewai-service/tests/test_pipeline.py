import asyncio
from types import SimpleNamespace

import pytest
from bundle_helpers import SHOP, make_bundle

from okf_chat.core.errors import LlmError
from okf_chat.core.navigator import Navigator
from okf_chat.core.pipeline import Pipeline, Refusal
from okf_chat.core.sql_executor import ExecResult, SqlExecutionError
from okf_chat.guardrails.jev_client import JevUnavailable
from okf_chat.guardrails.policy import MESSAGES

GOOD_SQL = "SELECT c.id FROM customers c JOIN orders o ON o.customer_id = c.id"
UI_FIELDS = {"question", "sql", "tables_used", "columns", "rows", "row_count", "risk_score", "timings_ms", "answer", "show_table"}


class ScriptedJudge:
    """One fake Jev for every stage. A score can be a number, or a list used one call at a time (the last value repeats)."""

    DEFAULTS = {
        "injection": 0.02, "modify_data": 0.03, "sensitive": 0.03, "data_question": 0.98,
        "answers_question": 0.9, "exposes_personal_data": 0.03, "risky": 0.05,
        "leaked_sensitive": 0.02, "followed_injected_text": 0.05, "unsafe_reply": 0.02,
    }

    def __init__(self, scores=None, down=False):
        self.scores = {"customers": 0.95, "orders": 0.9, **(scores or {})}
        self.down, self.calls, self.questions = down, [], {}

    async def noul(self, state, questions):
        self.calls.append(set(questions))
        self.questions.update(questions)
        if self.down:
            raise JevUnavailable("down")
        out = {}
        for q in questions:
            v = self.scores.get(q, self.DEFAULTS.get(q, 0.0))
            if isinstance(v, list):
                v = v.pop(0) if len(v) > 1 else v[0]
            out[q] = v
        return out

    def ran(self, qid):
        return any(qid in c for c in self.calls)


class FakeWriter:
    def __init__(self, drafts=None, fn=None, delay=0.0):
        self.drafts, self.fn, self.delay, self.calls = list(drafts or []), fn, delay, []

    async def write(self, question, context, feedback=None, previous_sql=None):
        self.calls.append(SimpleNamespace(question=question, context=context, feedback=feedback, previous_sql=previous_sql))
        if self.delay:
            await asyncio.sleep(self.delay)
        if self.fn:
            return self.fn(question)
        item = self.drafts.pop(0) if len(self.drafts) > 1 else self.drafts[0]
        if isinstance(item, Exception):
            raise item
        return item


def draft(sql=GOOD_SQL, can_answer=True, reason=""):
    return SimpleNamespace(can_answer=can_answer, sql=sql, reason=reason)


class FakeAnswerer:
    def __init__(self, text="You have 2 customers with orders.", show_table=False, natural=True):
        self.answer, self.calls = SimpleNamespace(text=text, show_table=show_table, natural=natural), []

    async def write(self, question, columns, rows, row_count, truncated=False):
        self.calls.append((question, columns, rows, row_count, truncated))
        return self.answer


class FakeExecutor:
    def __init__(self, results=None):
        self.results, self.sql = list(results or [ok_result()]), []

    async def execute(self, sql):
        self.sql.append(sql)
        item = self.results.pop(0) if len(self.results) > 1 else self.results[0]
        if isinstance(item, Exception):
            raise item
        return item


def ok_result(rows=None, truncated=False):
    rows = rows if rows is not None else [{"id": 1}, {"id": 2}]
    return ExecResult(["id"], rows, len(rows), truncated, 4.0)


@pytest.fixture
def bundle(tmp_path):
    return make_bundle(tmp_path, SHOP)


def build(bundle, judge=None, writer=None, answerer=None, executor=None, **kw):
    judge = judge or ScriptedJudge()
    parts = SimpleNamespace(
        judge=judge, writer=writer or FakeWriter([draft()]), answerer=answerer or FakeAnswerer(), executor=executor or FakeExecutor(),
    )
    parts.pipeline = Pipeline(Navigator(bundle, judge), judge, parts.writer, parts.answerer, parts.executor, **kw)
    return parts


async def refusal(parts, question="How many customers have orders?") -> Refusal:
    with pytest.raises(Refusal) as info:
        await parts.pipeline.ask(question)
    return info.value


# ---------------------------------------------------------------- the happy path
async def test_a_good_question_runs_every_stage_and_returns_the_ui_fields(bundle):
    p = build(bundle)
    r = await p.pipeline.ask("  How many customers have orders?  ")
    assert r.question == "How many customers have orders?" and r.answer == "You have 2 customers with orders."
    assert r.rows == [{"id": 1}, {"id": 2}] and r.row_count == 2 and r.columns == ["id"]
    assert r.tables_used == ["customers", "orders"] and r.attempts == 1 and r.natural
    assert r.sql.endswith("LIMIT 100")  # the validator's rewritten SQL is what ran
    assert p.executor.sql == [r.sql]
    assert set(r.to_response()) == UI_FIELDS


async def test_timings_are_whole_milliseconds_for_every_stage_that_ran(bundle):
    r = await build(bundle).pipeline.ask("q")
    assert set(r.timings_ms) == {"guard_in", "navigate", "sql_write", "validate", "judge", "execute", "answer", "guard_out"}
    assert all(isinstance(v, int) and v >= 0 for v in r.timings_ms.values())


async def test_the_risk_score_comes_from_the_judge(bundle):
    r = await build(bundle, ScriptedJudge({"risky": 0.31})).pipeline.ask("q")
    assert r.risk_score == pytest.approx(0.31) and r.to_response()["risk_score"] == 0.31


async def test_the_writer_only_sees_the_chosen_tables_and_never_a_sensitive_one(bundle):
    p = build(bundle, ScriptedJudge({"salaries": 0.3, "employees": 0.2, "products": 0.1}))
    await p.pipeline.ask("q")
    context = p.writer.calls[0].context
    assert "## Table: customers" in context and "## Table: orders" in context
    assert "salaries" not in context.replace("sensitive", "") and "## Table: employees" not in context


async def test_show_table_and_truncation_flow_through(bundle):
    p = build(bundle, answerer=FakeAnswerer(show_table=True), executor=FakeExecutor([ok_result(truncated=True)]))
    r = await p.pipeline.ask("q")
    assert r.show_table and r.truncated and p.answerer.calls[0][4] is True


# ---------------------------------------------------------------- the input guard
@pytest.mark.parametrize("hazard, status, detail, code", [
    ("injection", 400, "Request blocked: classified as 'prompt_injection'", "injection"),
    ("modify_data", 400, "Request blocked: classified as 'data_modification'", "modify_data"),
    ("sensitive", 422, "permission denied", "restricted"),  # every sensitive-data refusal shares the code "restricted"
])
async def test_input_hazards_are_refused_in_the_wording_the_ui_understands(bundle, hazard, status, detail, code):
    p = build(bundle, ScriptedJudge({hazard: 0.99}))
    r = await refusal(p)
    assert r.status_code == status and detail in r.detail and r.code == code
    assert p.writer.calls == [] and p.executor.sql == []  # nothing downstream ran


async def test_off_topic_questions_are_refused_as_off_topic(bundle):
    r = await refusal(build(bundle, ScriptedJudge({"data_question": 0.02})))
    assert r.status_code == 400 and r.detail == "Request blocked: classified as 'off_topic'" and r.message == MESSAGES["off_topic"]


async def test_a_refused_request_reports_only_the_stages_that_ran(bundle):
    r = await refusal(build(bundle, ScriptedJudge({"injection": 0.99})))
    assert list(r.timings_ms) == ["guard_in"]


async def test_jev_down_at_the_start_is_a_503_and_nothing_else_runs(bundle):
    p = build(bundle, ScriptedJudge(down=True))
    r = await refusal(p)
    assert r.status_code == 503 and r.code == "unavailable" and p.writer.calls == []


async def test_the_input_guard_is_told_what_the_database_holds_but_never_the_sensitive_tables(bundle):
    p = build(bundle)
    await p.pipeline.ask("q")
    topics = p.judge.questions["data_question"].instructions
    assert "customers" in topics and "orders" in topics and "products" in topics
    assert "salaries" not in topics  # a restricted table is not offered as something one may ask about


# ---------------------------------------------------------------- the navigator
async def test_a_clearly_sensitive_target_is_refused_before_any_sql_is_written(bundle):
    p = build(bundle, ScriptedJudge({"salaries": 0.95, "employees": 0.9}))
    r = await refusal(p, "average salary by employee")
    assert r.status_code == 422 and "permission denied" in r.detail and r.code == "restricted"
    assert r.message == MESSAGES["restricted"] and p.writer.calls == []


async def test_no_relevant_table_is_a_422(bundle):
    p = build(bundle, ScriptedJudge({"customers": 0.0, "orders": 0.0}))
    r = await refusal(p)
    assert r.status_code == 422 and r.code == "no_data" and p.writer.calls == []


# ---------------------------------------------------------------- the SQL writer
async def test_the_writer_saying_it_cannot_answer_is_refused_with_its_reason(bundle):
    p = build(bundle, writer=FakeWriter([draft(sql="", can_answer=False, reason="No table has weather data.")]))
    r = await refusal(p)
    assert r.status_code == 422 and "No table has weather data." in r.detail and p.executor.sql == []


async def test_writer_errors_map_to_502_and_504(bundle):
    r = await refusal(build(bundle, writer=FakeWriter([LlmError("RateLimitError: slow down")])))
    assert r.status_code == 502 and "AI model error" in r.detail and r.message == MESSAGES["llm_error"]
    r = await refusal(build(bundle, writer=FakeWriter([LlmError("the language model did not answer within 20 seconds")])))
    assert r.status_code == 504 and r.detail.startswith("Request timed out")


# ---------------------------------------------------------------- retries: validator
async def test_a_rejected_draft_is_retried_with_the_validators_complaint(bundle):
    p = build(bundle, writer=FakeWriter([draft("DELETE FROM customers"), draft()]))
    r = await p.pipeline.ask("q")
    assert r.attempts == 2 and len(p.writer.calls) == 2
    assert p.writer.calls[0].feedback is None
    assert p.writer.calls[1].feedback and "SELECT" in p.writer.calls[1].feedback
    assert p.writer.calls[1].previous_sql == "DELETE FROM customers"
    assert p.executor.sql and "DELETE" not in p.executor.sql[0]  # the bad draft never reached the database


async def test_it_gives_up_after_the_retry_budget_and_never_runs_the_sql(bundle):
    p = build(bundle, writer=FakeWriter([draft("DROP TABLE customers")]), max_retries=2)
    r = await refusal(p)
    assert len(p.writer.calls) == 3 and r.status_code == 422 and r.detail.startswith("Generated SQL rejected:")
    assert r.message == MESSAGES["unsafe_sql"] and p.executor.sql == [] and not p.judge.ran("answers_question")


async def test_zero_retries_means_one_attempt(bundle):
    p = build(bundle, writer=FakeWriter([draft("DROP TABLE customers")]), max_retries=0)
    await refusal(p)
    assert len(p.writer.calls) == 1


async def test_a_sensitive_table_in_the_sql_is_refused_at_once_without_retrying(bundle):
    p = build(bundle, writer=FakeWriter([draft("SELECT * FROM salaries")]))
    r = await refusal(p)
    assert r.code == "restricted" and "permission denied" in r.detail and len(p.writer.calls) == 1


async def test_a_table_the_writer_was_not_shown_is_rejected_and_retried(bundle):
    p = build(bundle, writer=FakeWriter([draft("SELECT * FROM products"), draft()]))
    r = await p.pipeline.ask("q")
    assert r.attempts == 2 and "products" in p.writer.calls[1].feedback


# ---------------------------------------------------------------- retries: the SQL judge
async def test_a_risky_query_is_refused_with_a_ui_compatible_risk_detail(bundle):
    p = build(bundle, ScriptedJudge({"exposes_personal_data": 0.97}))
    r = await refusal(p, "Show all customer emails")
    assert r.status_code == 422 and r.detail == "Generated SQL rejected: semantic risk 0.97" and r.code == "personal_data"
    assert p.executor.sql == [] and len(p.writer.calls) == 1


async def test_a_mismatch_is_retried_and_can_recover(bundle):
    p = build(bundle, ScriptedJudge({"answers_question": [0.05, 0.9]}))
    r = await p.pipeline.ask("q")
    assert r.attempts == 2 and "does not seem to answer" in p.writer.calls[1].feedback
    assert len(p.executor.sql) == 1  # only the second draft was run


async def test_a_persistent_mismatch_is_refused(bundle):
    p = build(bundle, ScriptedJudge({"answers_question": 0.05}))
    r = await refusal(p)
    assert r.code == "mismatch" and r.message == MESSAGES["mismatch"] and p.executor.sql == [] and len(p.writer.calls) == 3


async def test_jev_down_at_the_judge_stage_is_a_503(bundle):
    class DiesAtJudge(ScriptedJudge):
        async def noul(self, state, questions):
            if "answers_question" in questions:
                raise JevUnavailable("down")
            return await super().noul(state, questions)

    r = await refusal(build(bundle, DiesAtJudge()))
    assert r.status_code == 503 and r.code == "unavailable"


# ---------------------------------------------------------------- retries: the database
async def test_a_fixable_database_error_is_retried_with_the_message(bundle):
    err = SqlExecutionError("sql_error", 'column "nope" does not exist', retryable=True)
    p = build(bundle, executor=FakeExecutor([err, ok_result()]))
    r = await p.pipeline.ask("q")
    assert r.attempts == 2 and 'column "nope" does not exist' in p.writer.calls[1].feedback


async def test_a_timeout_is_a_504_in_the_ui_wording_and_is_not_retried(bundle):
    p = build(bundle, executor=FakeExecutor([SqlExecutionError("timeout", "too slow")]))
    r = await refusal(p)
    assert r.status_code == 504 and r.detail == "Query exceeded the 3 second limit" and len(p.writer.calls) == 1


async def test_the_timeout_wording_follows_the_configured_limit(bundle):
    p = build(bundle, executor=FakeExecutor([SqlExecutionError("timeout", "x")]), statement_timeout_ms=1500)
    assert (await refusal(p)).detail == "Query exceeded the 1.5 second limit"


async def test_permission_denied_from_the_database_matches_the_ui_pattern(bundle):
    p = build(bundle, executor=FakeExecutor([SqlExecutionError("permission_denied", "permission denied for table salaries")]))
    r = await refusal(p)
    assert r.status_code == 422 and "permission denied" in r.detail and r.code == "restricted"


async def test_an_unreachable_database_is_a_503(bundle):
    r = await refusal(build(bundle, executor=FakeExecutor([SqlExecutionError("unavailable", "no route")])))
    assert r.status_code == 503 and r.code == "db_unavailable"


async def test_a_non_retryable_database_error_is_refused(bundle):
    r = await refusal(build(bundle, executor=FakeExecutor([SqlExecutionError("read_only", "cannot execute DELETE in a read-only transaction")])))
    assert r.status_code == 422 and r.detail.startswith("Database error:")


# ---------------------------------------------------------------- the output guard
async def test_an_answer_that_fails_the_output_guard_is_withheld_with_its_rows(bundle):
    p = build(bundle, ScriptedJudge({"followed_injected_text": 0.98}))
    r = await refusal(p)
    assert r.status_code == 422 and r.detail == "Generated answer rejected: followed_injected_text"
    assert not hasattr(r, "rows")  # nothing from the result is attached to a refusal


async def test_a_leaked_secret_in_the_answer_is_refused_as_restricted(bundle):
    r = await refusal(build(bundle, ScriptedJudge({"leaked_sensitive": 0.99})))
    assert r.code == "restricted" and "permission denied" in r.detail


async def test_the_output_guard_sees_the_final_answer_text(bundle):
    p = build(bundle, answerer=FakeAnswerer("The answer is 42."))
    await p.pipeline.ask("q")
    assert p.judge.ran("leaked_sensitive")


async def test_jev_down_at_the_output_guard_is_a_503(bundle):
    class DiesAtOutput(ScriptedJudge):
        async def noul(self, state, questions):
            if "leaked_sensitive" in questions:
                raise JevUnavailable("down")
            return await super().noul(state, questions)

    r = await refusal(build(bundle, DiesAtOutput()))
    assert r.status_code == 503


# ---------------------------------------------------------------- the time budget and concurrency
async def test_the_whole_request_has_a_time_budget(bundle):
    p = build(bundle, writer=FakeWriter([draft()], delay=2), budget_s=0.1)
    r = await refusal(p)
    assert r.status_code == 504 and r.detail == "Request timed out: the service took longer than 0.1 seconds" and r.code == "timeout"
    assert r.message == MESSAGES["slow"] and p.executor.sql == []


async def test_concurrent_questions_do_not_interfere(bundle):
    p = build(bundle, writer=FakeWriter(fn=lambda q: draft(f"SELECT c.id, '{q[-1]}' AS tag FROM customers c JOIN orders o ON o.customer_id = c.id")),
              answerer=FakeAnswerer("ok"))
    results = await asyncio.gather(*(p.pipeline.ask(f"question {i}") for i in range(8)))
    assert [r.question for r in results] == [f"question {i}" for i in range(8)]
    assert [r.sql.split("'")[1] for r in results] == [str(i) for i in range(8)]  # each got its own SQL back
    assert len({id(r.timings_ms) for r in results}) == 8


async def test_a_refusal_in_one_request_does_not_affect_another(bundle):
    judge = ScriptedJudge({"injection": [0.99, 0.02]})  # the first call is hostile, the second is fine
    p = build(bundle, judge)
    first = await asyncio.gather(p.pipeline.ask("bad"), p.pipeline.ask("good"), return_exceptions=True)
    assert sum(isinstance(x, Refusal) for x in first) == 1 and sum(not isinstance(x, Exception) for x in first) == 1


async def test_refusals_carry_a_safe_message_and_never_leak_internals(bundle):
    for judge in (ScriptedJudge({"injection": 0.99}), ScriptedJudge({"risky": 0.99}), ScriptedJudge({"leaked_sensitive": 0.99})):
        r = await refusal(build(bundle, judge))
        assert not any(w in r.message.lower() for w in ("jev", "typesafe", "score", "threshold", "select", "salaries"))
