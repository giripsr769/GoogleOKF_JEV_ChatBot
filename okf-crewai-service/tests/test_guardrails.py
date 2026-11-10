import pytest
from typesafe_sdk import TypeSafeError

from okf_chat.guardrails.guards import INPUT_QUESTIONS, OUTPUT_QUESTIONS, check_input, check_output, input_questions, topics_from
from okf_chat.guardrails.jev_client import JevClient, JevUnavailable
from okf_chat.guardrails.policy import MESSAGES, GuardPolicy

CLEAN_IN = {"injection": 0.02, "modify_data": 0.03, "sensitive": 0.03, "data_question": 0.98}
CLEAN_OUT = {"leaked_sensitive": 0.02, "followed_injected_text": 0.05, "unsafe_reply": 0.02}


class FakeJudge:
    """Returns fixed scores (overridable per test) and records what it was asked."""

    def __init__(self, scores=None, error=False):
        self.scores, self.error, self.calls = scores or {}, error, []

    async def noul(self, state, questions):
        self.calls.append((state, set(questions)))
        if self.error:
            raise JevUnavailable("boom")
        return {q: self.scores.get(q, CLEAN_IN.get(q, CLEAN_OUT.get(q, 0.0))) for q in questions}


# ---------------------------------------------------------------- input guard
async def test_clean_question_passes_and_sends_every_input_question():
    judge = FakeJudge()
    d = await check_input(judge, "Top 3 customers?")
    assert d.allowed and d.code is None and d.message is None
    assert judge.calls == [("Top 3 customers?", set(INPUT_QUESTIONS))]


@pytest.mark.parametrize("hazard", ["injection", "modify_data", "sensitive"])
async def test_each_hazard_blocks_with_its_own_message(hazard):
    d = await check_input(FakeJudge({hazard: 0.99}), "q")
    assert not d.allowed and d.code == hazard and d.message == MESSAGES[hazard]


async def test_low_data_question_score_is_off_topic():
    d = await check_input(FakeJudge({"data_question": 0.02}), "weather?")
    assert not d.allowed and d.code == "off_topic" and d.message == MESSAGES["off_topic"]


async def test_hazard_wins_over_off_topic_when_both_apply():
    # "Delete all orders" scored modify_data=0.99 and data_question=0.39 in the live run; here data_question is also low
    d = await check_input(FakeJudge({"modify_data": 0.99, "data_question": 0.1}), "q")
    assert d.code == "modify_data"


async def test_injection_has_priority_over_other_hazards():
    d = await check_input(FakeJudge({"injection": 0.99, "sensitive": 0.99, "modify_data": 0.99}), "q")
    assert d.code == "injection"


async def test_hazard_threshold_is_inclusive_and_data_question_floor_is_exclusive():
    policy = GuardPolicy()
    assert not (await check_input(FakeJudge({"sensitive": policy.input_block_at["sensitive"]}), "q")).allowed
    assert (await check_input(FakeJudge({"sensitive": policy.input_block_at["sensitive"] - 0.01}), "q")).allowed
    assert (await check_input(FakeJudge({"data_question": policy.data_question_min}), "q")).allowed
    assert not (await check_input(FakeJudge({"data_question": policy.data_question_min - 0.01}), "q")).allowed


async def test_measured_salary_and_payment_scores_land_on_the_right_side_of_the_threshold():
    # measured against the real API (tools/eval_guards.py): salary questions score 0.96-0.99 on `sensitive`,
    # and the busiest good question ("Total payments received this year") scores 0.10
    d = await check_input(FakeJudge({"sensitive": 0.96, "data_question": 0.86}), "Average salary by department")
    assert not d.allowed and d.code == "sensitive"
    assert (await check_input(FakeJudge({"sensitive": 0.10, "data_question": 0.9}), "Total payments received this year")).allowed


async def test_the_tax_rate_question_is_allowed_once_the_guard_knows_the_topics():
    # with the database's topics in the prompt it scored 0.60 on data_question; the floor is 0.3
    assert (await check_input(FakeJudge({"data_question": 0.60}), "What is the tax rate in Germany")).allowed


def test_topics_are_listed_in_the_data_question_and_absent_without_them():
    with_topics = input_questions("customers, orders, tax_rates")
    assert "customers, orders, tax_rates" in with_topics["data_question"].instructions
    assert "holds these tables" not in input_questions()["data_question"].instructions
    assert set(with_topics) == set(INPUT_QUESTIONS)


def test_a_huge_topic_list_is_cut_off_with_a_count():
    text = topics_from([f"t{i:03d}" for i in range(250)])
    assert text.endswith("and 50 more") and "t199" in text and "t200" not in text


def test_topics_are_sorted_and_plain():
    assert topics_from(["orders", "customers"]) == "customers, orders"


async def test_a_custom_question_set_is_what_gets_asked():
    judge = FakeJudge()
    custom = input_questions("customers")
    await check_input(judge, "q", questions=custom)
    assert judge.calls == [("q", set(custom))]


def test_the_output_questions_separate_individual_pay_from_business_money_and_look_for_commands():
    leak = OUTPUT_QUESTIONS["leaked_sensitive"]
    assert "individual employee" in leak.instructions and "customer payments" in leak.criteria["false"]
    assert "commands or requests aimed at the reader" in OUTPUT_QUESTIONS["followed_injected_text"].instructions


def test_the_sql_judge_looks_at_the_returned_columns():
    from okf_chat.guardrails.sql_judge import SQL_QUESTIONS as SQLQ

    assert "columns" in SQLQ["exposes_personal_data"].instructions.lower()


async def test_custom_policy_is_respected():
    strict = GuardPolicy(input_block_at={"injection": 0.1, "modify_data": 0.1, "sensitive": 0.1})
    assert not (await check_input(FakeJudge({"injection": 0.2}), "q", strict)).allowed


# ---------------------------------------------------------------- Jev down
async def test_fails_closed_by_default():
    d = await check_input(FakeJudge(error=True), "q")
    assert not d.allowed and d.code == "unavailable" and d.jev_unavailable and d.message == MESSAGES["unavailable"]


async def test_fail_open_lets_the_question_through_but_says_so():
    d = await check_input(FakeJudge(error=True), "q", GuardPolicy(fail_open=True))
    assert d.allowed and d.jev_unavailable


async def test_output_fails_closed_and_open_too():
    assert not (await check_output(FakeJudge(error=True), "q", "a")).allowed
    assert (await check_output(FakeJudge(error=True), "q", "a", GuardPolicy(fail_open=True))).allowed


# ---------------------------------------------------------------- output guard
async def test_clean_reply_passes_and_judge_sees_question_and_reply():
    judge = FakeJudge()
    d = await check_output(judge, "How many?", "You have 4 customers.")
    assert d.allowed
    assert judge.calls == [({"question": "How many?", "reply": "You have 4 customers."}, set(OUTPUT_QUESTIONS))]


@pytest.mark.parametrize("hazard", ["leaked_sensitive", "followed_injected_text", "unsafe_reply"])
async def test_each_output_hazard_blocks(hazard):
    d = await check_output(FakeJudge({hazard: 0.95}), "q", "reply")
    assert not d.allowed and d.code == hazard and d.message == MESSAGES[hazard]


async def test_output_threshold_is_higher_so_borderline_replies_pass():
    # the live run scored a perfectly normal reply at followed_injected_text=0.10; 0.6 is borderline and allowed
    assert (await check_output(FakeJudge({"unsafe_reply": 0.6}), "q", "r")).allowed


# ---------------------------------------------------------------- messages
def test_user_messages_never_leak_scores_thresholds_or_internals():
    for text in MESSAGES.values():
        assert not any(w in text.lower() for w in ("threshold", "score", "probab", "jev", "typesafe", "0."))


def test_every_decision_code_has_a_message():
    for code in [*GuardPolicy().input_block_at, *GuardPolicy().output_block_at, "off_topic", "unavailable"]:
        assert code in MESSAGES


# ---------------------------------------------------------------- the real client's error handling
class _Answers:
    def __init__(self, **v):
        self.answers = {k: type("A", (), {"noul": x}) for k, x in v.items()}


class _FakeSdkClient:
    def __init__(self, result=None, exc=None):
        self.result, self.exc = result, exc

    async def system_one(self, **kwargs):
        if self.exc:
            raise self.exc
        return self.result


def _client_with(sdk):
    c = JevClient(api_key="test-key")
    c._client = sdk
    return c


async def test_client_returns_floats_per_question():
    c = _client_with(_FakeSdkClient(_Answers(injection=0.25)))
    assert await c.noul("hi", {"injection": INPUT_QUESTIONS["injection"]}) == {"injection": 0.25}


class _SdkError(TypeSafeError):
    def __init__(self):
        Exception.__init__(self, "rate limited")

    def __str__(self):
        return "rate limited"


async def test_client_wraps_sdk_errors():
    c = _client_with(_FakeSdkClient(exc=_SdkError()))
    with pytest.raises(JevUnavailable):
        await c.noul("hi", {"injection": INPUT_QUESTIONS["injection"]})


async def test_client_wraps_unusable_responses():
    c = _client_with(_FakeSdkClient(_Answers()))  # the requested question is missing from the answers
    with pytest.raises(JevUnavailable):
        await c.noul("hi", {"injection": INPUT_QUESTIONS["injection"]})
