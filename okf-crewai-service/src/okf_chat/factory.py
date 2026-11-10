"""Wire the real components together from settings. This is the only module that knows about every layer."""
from __future__ import annotations

from okf_chat.agents.answer_writer import AnswerWriter
from okf_chat.agents.llm import build_llm, crewai_runner
from okf_chat.agents.rewriter import QuestionRewriter
from okf_chat.agents.sql_writer import SqlWriter
from okf_chat.config import Settings
from okf_chat.core.memory import ConversationMemory
from okf_chat.core.navigator import NavPolicy, Navigator
from okf_chat.core.okf_loader import Bundle
from okf_chat.core.pipeline import Pipeline
from okf_chat.core.sql_executor import ReadOnlyExecutor
from okf_chat.guardrails.jev_client import JevClient
from okf_chat.guardrails.policy import GuardPolicy


def build_pipeline(settings: Settings, database_url: str | None = None, verify_role: bool = True) -> Pipeline:
    """Build the whole chain. Raises UnsafeDatabaseRole when the database login can do more than read."""
    bundle = Bundle.load(settings.okf_bundle_dir)
    jev = JevClient(settings.typesafe_api_key, settings.jev_model, settings.jev_timeout_s)
    executor = ReadOnlyExecutor(database_url or settings.database_url, settings.statement_timeout_ms, settings.max_result_rows)
    if verify_role:
        executor.verify()
    runner = crewai_runner(build_llm(settings), settings.openai_timeout_s)
    return Pipeline(
        navigator=Navigator(bundle, jev, NavPolicy(max_tables=settings.navigator_max_tables)),
        judge=jev,
        writer=SqlWriter(runner, settings.max_result_rows),
        answerer=AnswerWriter(runner, settings.answer_max_rows, settings.natural_answers),
        executor=executor,
        policy=GuardPolicy(fail_open=settings.jev_fail_open),
        max_retries=settings.sql_max_retries,
        budget_s=settings.pipeline_timeout_s,
        max_rows=settings.max_result_rows,
        statement_timeout_ms=settings.statement_timeout_ms,
        rewriter=QuestionRewriter(runner),
        memory=ConversationMemory(settings.memory_turns, settings.memory_ttl_s, settings.memory_max_sessions),
    )
