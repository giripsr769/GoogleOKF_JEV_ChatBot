"""OKF chat: ask questions about a Postgres database in plain English, guided by an OKF bundle."""
from __future__ import annotations

import asyncio

__version__ = "0.1.0"


class OKFChat:
    """Embed the chatbot in another application.

    chat = OKFChat(bundle="okf_bundle", database_url="postgresql://readonly:...@host/db")
    result = chat.ask_sync("How many customers do we have?")   # or: await chat.ask(...)

    `ask` raises okf_chat.core.pipeline.Refusal when the question is not answered.
    The pipeline (and CrewAI) is imported and built on first use.
    """

    def __init__(self, bundle: str | None = None, database_url: str | None = None, **settings):
        self._overrides = {k: v for k, v in {"okf_bundle_dir": bundle, "database_url": database_url, **settings}.items() if v is not None}
        self._pipeline = None

    def _get(self):
        if self._pipeline is None:
            from okf_chat.config import Settings
            from okf_chat.factory import build_pipeline

            self._pipeline = build_pipeline(Settings(**self._overrides))
        return self._pipeline

    async def ask(self, question: str, session_id: str | None = None):
        """Returns a PipelineResult (use `.to_response()` for a plain dict). Calls with the same `session_id` are one
        conversation, so a follow-up such as "and last month?" is understood."""
        return await self._get().ask(question, session_id)

    def ask_sync(self, question: str, session_id: str | None = None):
        return asyncio.run(self.ask(question, session_id))

    async def aclose(self) -> None:
        if self._pipeline is not None:
            await self._pipeline.aclose()
            self._pipeline = None
