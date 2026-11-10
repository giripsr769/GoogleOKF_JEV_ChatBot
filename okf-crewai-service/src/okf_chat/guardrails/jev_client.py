"""A thin async wrapper around the TypeSafe SDK. Everything else talks to the `Judge` protocol, so tests can swap in a fake."""
from __future__ import annotations

from typing import Mapping, Protocol

from typesafe_sdk import AsyncTypeSafeClient, Noul, RetryPolicy, TypeSafeError


class JevUnavailable(Exception):
    """Jev could not be reached or returned something unusable. Guards decide whether to fail open or closed."""


class Judge(Protocol):
    async def noul(self, state, questions: Mapping[str, Noul]) -> dict[str, float]:
        """Ask yes/no questions about `state`. Returns {question id: probability of yes, 0..1}."""


class JevClient:
    def __init__(self, api_key: str, model: str = "jev-latest", timeout_s: float = 10.0, max_retries: int = 2):
        self._client = AsyncTypeSafeClient(
            api_key=api_key or None,  # None lets the SDK fall back to the TYPESAFE_API_KEY env var
            model=model,
            timeout=timeout_s,
            retry=RetryPolicy(max_retries=max_retries, timeout=timeout_s),  # 429 / 529 back off automatically
        )

    async def noul(self, state, questions: Mapping[str, Noul]) -> dict[str, float]:
        try:
            response = await self._client.system_one(state=state, questions=dict(questions))
            return {qid: float(response.answers[qid].noul) for qid in questions}
        except (TypeSafeError, KeyError, TypeError, ValueError, OSError) as exc:
            raise JevUnavailable(f"{type(exc).__name__}: {exc}") from exc

    async def aclose(self) -> None:
        await self._client.aclose()
