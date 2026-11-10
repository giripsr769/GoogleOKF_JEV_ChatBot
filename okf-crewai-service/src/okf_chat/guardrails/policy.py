"""Thresholds and user-facing messages for the guardrails. Defaults are starting points: tune them on the evaluation questions."""
from __future__ import annotations

from dataclasses import dataclass, field


@dataclass(frozen=True)
class GuardPolicy:
    # input: block when a hazard's probability reaches this value. Measured on 58 good and 15 bad questions
    # (tools/eval_guards.py): good questions score at most 0.11 on every hazard, bad ones at least 0.96, so 0.5 sits mid-gap.
    input_block_at: dict[str, float] = field(default_factory=lambda: {"injection": 0.5, "modify_data": 0.5, "sensitive": 0.5})
    # input: block when the "is this a data question" probability falls BELOW this value
    data_question_min: float = 0.3
    # output: block when a hazard's probability reaches this value (higher, because blocking a good answer is costly)
    output_block_at: dict[str, float] = field(default_factory=lambda: {"leaked_sensitive": 0.7, "followed_injected_text": 0.7, "unsafe_reply": 0.7})
    # SQL judge: block when a hazard's probability reaches this value
    sql_block_at: dict[str, float] = field(default_factory=lambda: {"exposes_personal_data": 0.7, "risky": 0.7})
    # SQL judge: "does this query answer the question" below this value means the SQL writer should try again
    sql_mismatch_below: float = 0.2
    # what to do when Jev cannot be reached: False means refuse (safe), True means let it through
    fail_open: bool = False


# hazard code -> what the user is told. Deliberately vague: it must not teach anyone how to get around a check.
MESSAGES = {
    "injection": "I can only answer questions about your company data, so I can't act on that request.",
    "modify_data": "I can only read data, never change it. Try asking a question about your data instead.",
    "sensitive": "That information is private, so I can't share it.",
    "off_topic": "I can answer questions about your company data, such as customers, orders, products or staff counts. Try asking one of those.",
    "leaked_sensitive": "I found an answer but it contains private information, so I can't show it.",
    "followed_injected_text": "I couldn't produce a trustworthy answer to that question.",
    "unsafe_reply": "I couldn't produce a suitable answer to that question.",
    "personal_data": "That would list private personal details in bulk, so I can't run it.",
    "risky": "That query looked unsafe to run, so I didn't.",
    "mismatch": "I wasn't able to build a reliable query for that question. Try rephrasing it.",
    "restricted": "I'm not allowed to look at that data.",
    "no_context": "I don't know what to show yet. Ask a complete question first, then I can show it as a table.",
    "no_data": "I couldn't find data that answers that. Try asking about your customers, orders, products or staff.",
    "unsafe_sql": "I couldn't turn that into a safe lookup. Could you rephrase it?",
    "db_timeout": "That lookup took too long, so I stopped it. Try narrowing the question.",
    "db_unavailable": "I can't reach the database right now. Please try again in a moment.",
    "slow": "This is taking too long, so I stopped waiting. Please try again in a moment.",
    "llm_error": "The AI service had a problem. Please try again in a moment.",
    "unavailable": "I couldn't run my safety check just now, so I didn't answer. Please try again in a moment.",
}
