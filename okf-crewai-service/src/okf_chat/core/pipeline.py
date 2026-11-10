"""One question, start to finish.

    input guard -> navigate (pick tables) -> SQL writer -> validate -> SQL judge -> read-only run -> answer writer -> output guard

If the SQL is rejected, judged a mismatch, or fails in the database in a way the writer can fix, the complaint goes
back to the writer for another try (up to `max_retries`). The whole request has a time budget. Anything that stops
the answer raises `Refusal`, which carries an HTTP-style status and a `detail` string in the wording the existing chat UI
already understands, plus a safe message in plain English for other callers.

No agent framework is imported here: the SQL writer and the answer writer are passed in, so any object with the same
`write()` methods works (CrewAI today).
"""
from __future__ import annotations

import asyncio
import logging
import re
import time
from contextlib import contextmanager
from dataclasses import dataclass, field
from typing import Protocol

from okf_chat.core.errors import LlmError
from okf_chat.core.memory import ConversationMemory, Turn
from okf_chat.core.navigator import Navigator
from okf_chat.core.sql_executor import ExecResult, SqlExecutionError
from okf_chat.core.sql_validator import validate_sql
from okf_chat.guardrails.guards import GuardDecision, check_input, check_output, input_questions, topics_from
from okf_chat.guardrails.jev_client import JevUnavailable, Judge
from okf_chat.guardrails.policy import MESSAGES, GuardPolicy
from okf_chat.guardrails.sql_judge import check_sql

log = logging.getLogger("okf_chat.pipeline")

# input-guard code -> the intent name the UI recognises in "Request blocked: classified as '<intent>'"
_INTENT = {"injection": "prompt_injection", "modify_data": "data_modification", "off_topic": "off_topic"}
_RESTRICTED = "Request refused: permission denied, that data is restricted"

# A message that only asks to change how results are shown ("show me in table view", "as a table please"). With no earlier
# question there is nothing to show, so it is refused instead of guessed at. Deliberately narrow: "show the orders table" is a question.
_DISPLAY_ONLY = re.compile(
    r"^(?:(?:please|pls|can you|could you|now|ok|okay|and)\s+)*"
    r"(?:(?:show|display|give|put|present|see|view|make|turn)\s+)?(?:me\s+)?"
    r"(?:(?:it|that|them|this|those|the results?|the data|the same|the answer)\s+)?"
    r"(?:(?:in|as|into|on)\s+)?(?:(?:a|the)\s+)?(?:table|tabular|grid|spreadsheet)(?:\s+(?:view|format|form))?(?:\s+please)?$",
    re.I,
)


def is_display_only(text: str) -> bool:
    return bool(_DISPLAY_ONLY.match(" ".join(re.sub(r"[^\w\s]", " ", text).split())))


class SqlWriterLike(Protocol):
    async def write(self, question: str, context: str, feedback: str | None = None, previous_sql: str | None = None): ...


class RewriterLike(Protocol):
    async def rewrite(self, question: str, history: list[Turn]) -> str: ...


class AnswerWriterLike(Protocol):
    async def write(self, question: str, columns: list[str], rows: list[dict], row_count: int, truncated: bool = False): ...


class ExecutorLike(Protocol):
    async def execute(self, sql: str) -> ExecResult: ...


class Refusal(Exception):
    """The question was not answered. `detail` and `status_code` are what an HTTP API should return."""

    def __init__(self, status_code: int, detail: str, code: str, message: str, timings_ms: dict[str, int] | None = None, standalone: str = ""):
        super().__init__(detail)
        self.standalone = standalone  # the question as understood after a follow-up was rewritten (empty when not rewritten)
        self.status_code, self.detail, self.code, self.message = status_code, detail, code, message
        self.timings_ms = timings_ms or {}


@dataclass
class PipelineResult:
    question: str
    sql: str
    tables_used: list[str]
    columns: list[str]
    rows: list[dict]
    row_count: int
    risk_score: float
    timings_ms: dict[str, int]
    answer: str
    show_table: bool
    attempts: int = 1  # how many SQL drafts it took
    truncated: bool = False
    natural: bool = True  # False when the plain fallback answer was used
    standalone: str = ""  # the question as the pipeline understood it (differs from `question` for follow-ups)

    def to_response(self) -> dict:
        """The exact fields the chat UI's QueryResponse expects."""
        return {
            "question": self.question, "sql": self.sql, "tables_used": self.tables_used, "columns": self.columns,
            "rows": self.rows, "row_count": self.row_count, "risk_score": round(self.risk_score, 3),
            "timings_ms": self.timings_ms, "answer": self.answer, "show_table": self.show_table,
        }


class _Run:
    """Per-request scratch space: stage timings in milliseconds (a stage that runs twice adds up)."""

    def __init__(self) -> None:
        self.timings: dict[str, float] = {}
        self.standalone = ""

    @contextmanager
    def lap(self, name: str):
        start = time.perf_counter()
        try:
            yield
        finally:
            self.timings[name] = self.timings.get(name, 0.0) + (time.perf_counter() - start) * 1000

    @property
    def ms(self) -> dict[str, int]:
        return {k: int(round(v)) for k, v in self.timings.items()}


class Pipeline:
    def __init__(
        self,
        navigator: Navigator,
        judge: Judge,
        writer: SqlWriterLike,
        answerer: AnswerWriterLike,
        executor: ExecutorLike,
        policy: GuardPolicy | None = None,
        *,
        max_retries: int = 2,
        budget_s: float = 30.0,
        max_rows: int = 100,
        statement_timeout_ms: int = 3000,
        rewriter: RewriterLike | None = None,
        memory: ConversationMemory | None = None,
    ):
        self.navigator, self.judge, self.writer, self.answerer, self.executor = navigator, judge, writer, answerer, executor
        self.policy = policy or GuardPolicy()
        self.max_retries, self.budget_s, self.max_rows, self.statement_timeout_ms = max_retries, budget_s, max_rows, statement_timeout_ms
        self.rewriter, self.memory = rewriter, memory
        self.sensitive = navigator.sensitive
        # tell the input guard what the database holds, so questions about it are not mistaken for general knowledge
        self.input_questions = input_questions(topics_from([t for t in navigator.concepts if t not in navigator.sensitive]))

    async def aclose(self) -> None:
        close = getattr(self.judge, "aclose", None)
        if close:
            await close()

    # ---------------------------------------------------------------- public
    async def ask(self, question: str, session_id: str | None = None) -> PipelineResult:
        """Answer one question or raise Refusal. With a `session_id`, earlier turns of that session resolve follow-ups.
        Safe to call concurrently: nothing is shared between calls except the session memory."""
        run = _Run()
        try:
            result = await asyncio.wait_for(self._run(question, run, session_id), timeout=self.budget_s)
        except asyncio.TimeoutError:
            raise self._refuse(run, 504, f"Request timed out: the service took longer than {self.budget_s:g} seconds", "timeout", "slow") from None
        except Refusal as r:
            log.info("refused code=%s status=%s timings=%s", r.code, r.status_code, r.timings_ms)
            raise
        log.info("answered rows=%s attempts=%s timings=%s", result.row_count, result.attempts, result.timings_ms)
        return result

    # ---------------------------------------------------------------- the steps
    async def _run(self, question: str, run: _Run, session_id: str | None = None) -> PipelineResult:
        original = question.strip()
        q = original
        history = self.memory.history(session_id) if self.memory and self.rewriter else []

        if history:
            # A follow-up becomes a standalone question. The guards then see the raw text (attacks only: a bare
            # "and last month?" is rightly not a data question on its own) and the rewritten question (everything).
            with run.lap("rewrite"):
                q = await self.rewriter.rewrite(original, history)
            run.standalone = q
            if q != original:
                with run.lap("guard_in"):
                    raw = await check_input(self.judge, original, self.policy, self.input_questions)
                if not raw.allowed and raw.code != "off_topic":
                    raise self._input_refusal(run, raw)

        if not history and is_display_only(original):
            raise self._refuse(run, 422, "Generated SQL rejected: there is no earlier question to show in that form", "no_context", "no_context")

        with run.lap("guard_in"):
            gate = await check_input(self.judge, q, self.policy, self.input_questions)
        if not gate.allowed:
            raise self._input_refusal(run, gate)

        with run.lap("navigate"):
            try:
                nav = await self.navigator.navigate(q)
            except JevUnavailable:
                raise self._refuse(run, 503, "Safety check unavailable", "unavailable", "unavailable") from None
        if nav.sensitive_hit:
            raise self._refuse(run, 422, _RESTRICTED, "restricted", "restricted")
        if not nav.found:
            raise self._refuse(run, 422, "Generated SQL rejected: no table can answer this question", "no_data", "no_data")
        context = self.navigator.render_context(nav.tables)

        feedback: str | None = None
        previous_sql: str | None = None
        for attempt in range(1, self.max_retries + 2):
            try:
                with run.lap("sql_write"):
                    draft = await self.writer.write(q, context, feedback, previous_sql)
            except LlmError as exc:
                raise self._llm_refusal(run, exc) from None
            if not draft.can_answer:
                raise self._refuse(run, 422, f"Generated SQL rejected: {draft.reason or 'the data cannot answer this'}", "cannot_answer", "no_data")

            with run.lap("validate"):
                check = validate_sql(draft.sql, nav.tables, self.sensitive, self.max_rows)
            if not check.ok:
                if check.code == "sensitive_table":
                    raise self._refuse(run, 422, _RESTRICTED, "restricted", "restricted")
                problem, kind = check.reasons[0], "sql_rejected"
            else:
                with run.lap("judge"):
                    verdict = await check_sql(self.judge, q, check.sql, self.policy)
                if not verdict.ok and not verdict.retryable:
                    if verdict.code == "unavailable":
                        raise self._refuse(run, 503, "Safety check unavailable", "unavailable", "unavailable")
                    raise self._refuse(run, 422, f"Generated SQL rejected: semantic risk {verdict.risk_score:.2f}", verdict.code, verdict.code)
                if not verdict.ok:
                    problem, kind = verdict.feedback or "The query does not answer the question.", "mismatch"
                else:
                    try:
                        with run.lap("execute"):
                            result = await self.executor.execute(check.sql)
                    except SqlExecutionError as exc:
                        if not exc.retryable:
                            raise self._db_refusal(run, exc) from None
                        problem, kind = f"The database rejected the query: {exc.message}", "db_error"
                    else:
                        return await self._finish(run, q, original, session_id, check, verdict.risk_score, result, attempt)

            if attempt > self.max_retries:  # out of tries
                code = "mismatch" if kind == "mismatch" else "unsafe_sql"
                raise self._refuse(run, 422, f"Generated SQL rejected: {problem}", code, code)
            feedback, previous_sql = problem, draft.sql
        raise AssertionError("unreachable")  # the loop always returns or raises

    async def _finish(self, run: _Run, question: str, original: str, session_id: str | None, check, risk: float, result: ExecResult, attempts: int) -> PipelineResult:
        with run.lap("answer"):
            answer = await self.answerer.write(question, result.columns, result.rows, result.row_count, result.truncated)
        with run.lap("guard_out"):
            out = await check_output(self.judge, question, answer.text, self.policy)
        if not out.allowed:
            if out.code == "unavailable":
                raise self._refuse(run, 503, "Safety check unavailable", "unavailable", "unavailable")
            if out.code == "leaked_sensitive":
                raise self._refuse(run, 422, _RESTRICTED, "restricted", "restricted")
            raise self._refuse(run, 422, f"Generated answer rejected: {out.code}", out.code, out.code)
        if self.memory and self.rewriter:
            self.memory.add(session_id, Turn(question, answer.text))  # only answered questions are remembered
        return PipelineResult(
            question=original, standalone=question, sql=check.sql, tables_used=check.tables, columns=result.columns, rows=result.rows,
            row_count=result.row_count, risk_score=risk, timings_ms=run.ms, answer=answer.text, show_table=answer.show_table,
            attempts=attempts, truncated=result.truncated, natural=answer.natural,
        )

    # ---------------------------------------------------------------- refusals
    def _refuse(self, run: _Run, status: int, detail: str, code: str, message_key: str) -> Refusal:
        return Refusal(status, detail, code, MESSAGES.get(message_key, MESSAGES["unsafe_sql"]), run.ms, run.standalone)

    def _input_refusal(self, run: _Run, gate: GuardDecision) -> Refusal:
        if gate.code in _INTENT:
            return self._refuse(run, 400, f"Request blocked: classified as '{_INTENT[gate.code]}'", gate.code, gate.code)
        if gate.code == "sensitive":
            return self._refuse(run, 422, _RESTRICTED, "restricted", "restricted")
        if gate.code == "unavailable":
            return self._refuse(run, 503, "Safety check unavailable", "unavailable", "unavailable")
        return self._refuse(run, 400, f"Request blocked: classified as '{gate.code}'", gate.code or "blocked", "injection")

    def _llm_refusal(self, run: _Run, exc: LlmError) -> Refusal:
        if "did not answer" in str(exc):
            return self._refuse(run, 504, "Request timed out: the AI model did not answer in time", "llm_timeout", "slow")
        return self._refuse(run, 502, f"AI model error: {exc}", "llm_error", "llm_error")

    def _db_refusal(self, run: _Run, exc: SqlExecutionError) -> Refusal:
        if exc.code == "timeout":
            return self._refuse(run, 504, f"Query exceeded the {self.statement_timeout_ms / 1000:g} second limit", "db_timeout", "db_timeout")
        if exc.code == "permission_denied":
            return self._refuse(run, 422, f"Database error: {exc.message}", "restricted", "restricted")
        if exc.code == "unavailable":
            return self._refuse(run, 503, "Database unavailable", "db_unavailable", "db_unavailable")
        return self._refuse(run, 422, f"Database error: {exc.message}", exc.code, "unsafe_sql")
