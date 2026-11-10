"""Jev's opinion on a SQL query that already passed the hard validator: does it answer the question, and is it risky?

This layer is advisory and semantic. The validator and the database role are the hard locks; Jev catches what rules
cannot, such as a harmless-looking query that dumps everyone's email address, or SQL that answers a different question.
"""
from __future__ import annotations

from dataclasses import dataclass, field

from typesafe_sdk import Noul

from okf_chat.guardrails.jev_client import Judge, JevUnavailable
from okf_chat.guardrails.policy import MESSAGES, GuardPolicy

SQL_QUESTIONS = {
    "answers_question": Noul(
        instructions="Does this SQL query compute what the user's question asks for?",
        criteria={
            "true": "The query selects the data, filters, groupings and ordering the question asks for",
            "false": "The query answers a different question, or misses a filter or grouping the question needs",
        },
    ),
    # Judges the returned COLUMNS. A wording about "personal details" in general scored plain name lists 0.7-0.9 and blocked
    # 9 of 47 good questions; this wording scores them at most 0.17 and contact-detail queries at least 0.99.
    "exposes_personal_data": Noul(
        instructions="Look at the columns this SQL query returns. Do they include private contact or identity details of people, such as email, phone, street address, date of birth or a government or financial id?",
        criteria={
            "true": "The returned columns include an email, phone number, street address, birth date or private id",
            "false": "The returned columns are only names, ids, counts, totals, dates of business events or other business figures",
        },
    ),
    "risky": Noul(
        instructions="Could running this SQL query be harmful, extremely expensive, or reveal how the system is built?",
        criteria={
            "true": "The query is destructive, probes system internals, or would scan or multiply huge amounts of data",
            "false": "The query is an ordinary, bounded read of business data",
        },
    ),
}


@dataclass
class SqlVerdict:
    ok: bool
    code: str | None = None  # personal_data, risky, mismatch or unavailable
    message: str | None = None  # safe text for the user
    feedback: str | None = None  # for the SQL writer when the query should be retried; never shown to the user
    risk_score: float = 0.0  # the UI's risk_score: the larger of the two hazards, 0..1
    scores: dict[str, float] = field(default_factory=dict)
    retryable: bool = False  # True only for a mismatch
    jev_unavailable: bool = False


async def check_sql(judge: Judge, question: str, sql: str, policy: GuardPolicy | None = None) -> SqlVerdict:
    policy = policy or GuardPolicy()
    try:
        scores = await judge.noul({"question": question, "sql": sql}, SQL_QUESTIONS)
    except JevUnavailable:
        if policy.fail_open:
            return SqlVerdict(True, jev_unavailable=True)
        return SqlVerdict(False, "unavailable", MESSAGES["unavailable"], jev_unavailable=True)

    risk = max(scores.get("exposes_personal_data", 0.0), scores.get("risky", 0.0))
    for hazard, limit in policy.sql_block_at.items():
        if scores.get(hazard, 0.0) >= limit:
            code = "personal_data" if hazard == "exposes_personal_data" else hazard
            return SqlVerdict(False, code, MESSAGES[code], risk_score=risk, scores=scores)
    if scores.get("answers_question", 1.0) < policy.sql_mismatch_below:
        return SqlVerdict(
            False, "mismatch", MESSAGES["mismatch"], risk_score=risk, scores=scores, retryable=True,
            feedback="That query does not seem to answer the question. Re-read the question and check the filters, groupings and tables.",
        )
    return SqlVerdict(True, risk_score=risk, scores=scores)
