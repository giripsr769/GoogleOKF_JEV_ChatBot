import pytest

from okf_chat.guardrails.jev_client import JevUnavailable
from okf_chat.guardrails.policy import MESSAGES, GuardPolicy
from okf_chat.guardrails.sql_judge import SQL_QUESTIONS, check_sql

CLEAN = {"answers_question": 0.95, "exposes_personal_data": 0.03, "risky": 0.02}


class FakeJudge:
    def __init__(self, scores=None, error=False):
        self.scores, self.error, self.calls = {**CLEAN, **(scores or {})}, error, []

    async def noul(self, state, questions):
        self.calls.append((state, set(questions)))
        if self.error:
            raise JevUnavailable("down")
        return {q: self.scores[q] for q in questions}


async def test_a_good_query_passes_with_a_low_risk_score():
    judge = FakeJudge()
    v = await check_sql(judge, "How many customers?", "SELECT COUNT(*) FROM customers")
    assert v.ok and v.code is None and v.risk_score == pytest.approx(0.03)
    assert judge.calls == [({"question": "How many customers?", "sql": "SELECT COUNT(*) FROM customers"}, set(SQL_QUESTIONS))]


async def test_bulk_personal_data_is_blocked_with_a_safe_message():
    v = await check_sql(FakeJudge({"exposes_personal_data": 0.9}), "Show all customer emails", "SELECT email FROM customers")
    assert not v.ok and v.code == "personal_data" and v.message == MESSAGES["personal_data"] and not v.retryable
    assert v.risk_score == pytest.approx(0.9)


async def test_a_risky_query_is_blocked():
    v = await check_sql(FakeJudge({"risky": 0.95}), "q", "SELECT 1")
    assert not v.ok and v.code == "risky" and v.message == MESSAGES["risky"]


async def test_the_risk_score_is_the_larger_hazard():
    v = await check_sql(FakeJudge({"exposes_personal_data": 0.4, "risky": 0.6}), "q", "SELECT 1")
    assert v.ok and v.risk_score == pytest.approx(0.6)  # below both block limits, so it passes with the higher score


async def test_a_mismatch_asks_the_sql_writer_to_retry_and_gives_it_feedback():
    v = await check_sql(FakeJudge({"answers_question": 0.05}), "q", "SELECT 1")
    assert not v.ok and v.code == "mismatch" and v.retryable and v.feedback
    assert v.message == MESSAGES["mismatch"]


async def test_hazards_take_priority_over_a_mismatch():
    v = await check_sql(FakeJudge({"answers_question": 0.0, "risky": 0.99}), "q", "SELECT 1")
    assert v.code == "risky" and not v.retryable


async def test_thresholds_are_inclusive_for_hazards_and_exclusive_for_mismatch():
    p = GuardPolicy()
    assert not (await check_sql(FakeJudge({"risky": p.sql_block_at["risky"]}), "q", "s")).ok
    assert (await check_sql(FakeJudge({"risky": p.sql_block_at["risky"] - 0.01}), "q", "s")).ok
    assert (await check_sql(FakeJudge({"answers_question": p.sql_mismatch_below}), "q", "s")).ok
    assert not (await check_sql(FakeJudge({"answers_question": p.sql_mismatch_below - 0.01}), "q", "s")).ok


async def test_fails_closed_when_jev_is_down():
    v = await check_sql(FakeJudge(error=True), "q", "s")
    assert not v.ok and v.code == "unavailable" and v.jev_unavailable and v.message == MESSAGES["unavailable"]


async def test_can_fail_open_when_configured():
    v = await check_sql(FakeJudge(error=True), "q", "s", GuardPolicy(fail_open=True))
    assert v.ok and v.jev_unavailable


async def test_feedback_for_the_writer_never_reaches_the_user_message():
    v = await check_sql(FakeJudge({"answers_question": 0.0}), "q", "s")
    assert v.feedback not in (v.message or "")
