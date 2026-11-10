"""The only place that talks to CrewAI. Everything else sees `run_agent`, so the framework is swappable."""
from __future__ import annotations

import asyncio
import json
import re
from typing import Awaitable, Callable, TypeVar

from okf_chat.agents import runtime  # (must run before crewai is imported)
from pydantic import BaseModel, ValidationError

from crewai import Agent, LLM

from okf_chat.config import Settings
from okf_chat.core.errors import LlmError  # noqa: F401  (re-exported: agents and tests import it from here)

T = TypeVar("T", bound=BaseModel)

# (role, goal, backstory, prompt, output model) -> parsed output. Tests replace this with a fake.
Runner = Callable[[str, str, str, str, type], Awaitable[BaseModel]]


def untrusted(text: str) -> str:
    """User text goes between <question> tags in a prompt; remove any tag the user typed so they cannot close it early."""
    return re.sub(r"</?\s*question\s*>", "", text, flags=re.I).strip()


_GRACE_S = 5  # wait this much longer than the LLM's own timeout before giving up on the whole agent call


def build_llm(settings: Settings) -> LLM:
    model = settings.openai_model
    return LLM(
        model=model if "/" in model else f"openai/{model}",
        api_key=settings.openai_api_key or None,
        timeout=settings.openai_timeout_s,
        # no temperature: some models (gpt-6-luna) accept only their default and reject 0
    )


def crewai_runner(llm: LLM, timeout_s: float) -> Runner:
    """A runner that executes one CrewAI agent per call (stateless, so concurrent requests cannot interfere)."""

    async def run(role: str, goal: str, backstory: str, prompt: str, output: type[T]) -> T:
        runtime.suppress_console()  # the switch is per-context, and each request runs in its own task
        agent = Agent(role=role, goal=goal, backstory=backstory, llm=llm, verbose=False, allow_delegation=False)
        try:
            result = await asyncio.wait_for(agent.kickoff_async(prompt, response_format=output), timeout=timeout_s + _GRACE_S)
        except asyncio.TimeoutError:
            raise LlmError(f"the language model did not answer within {timeout_s:g} seconds") from None
        except Exception as exc:  # openai / network / provider errors
            raise LlmError(f"{type(exc).__name__}: {str(exc).splitlines()[0][:200]}") from exc
        return parse_output(result, output)

    return run


def parse_output(result, output: type[T]) -> T:
    """CrewAI gives a parsed model in `.pydantic`; if that is missing, recover from the raw text."""
    parsed = getattr(result, "pydantic", None)
    if isinstance(parsed, output):
        return parsed
    raw = str(getattr(result, "raw", "") or "").strip()
    raw = re.sub(r"^```(?:json)?\s*|\s*```$", "", raw)  # a fenced code block around the JSON
    try:
        return output.model_validate(json.loads(raw))
    except (json.JSONDecodeError, ValidationError, TypeError, ValueError):
        raise LlmError("the language model's reply was not in the expected format") from None
