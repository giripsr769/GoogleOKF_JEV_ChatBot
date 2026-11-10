"""Short conversation memory, kept per session id in this process.

It stores only what already reached the user: the standalone question and the reply text that passed the output guard.
Rows, SQL and refused questions are never stored. Entries expire after `ttl_s`, and the number of sessions is capped.
A server restart forgets everything (by design: nothing is written to disk).
"""
from __future__ import annotations

import time
from collections import OrderedDict, deque
from dataclasses import dataclass


@dataclass(frozen=True)
class Turn:
    question: str  # the standalone form of what the user asked
    answer: str


class ConversationMemory:
    def __init__(self, max_turns: int = 4, ttl_s: float = 1800, max_sessions: int = 500, clock=time.monotonic):
        self.max_turns, self.ttl_s, self.max_sessions, self._clock = max_turns, ttl_s, max_sessions, clock
        self._sessions: OrderedDict[str, tuple[float, deque[Turn]]] = OrderedDict()

    @property
    def enabled(self) -> bool:
        return self.max_turns > 0

    def history(self, session_id: str | None) -> list[Turn]:
        if not self.enabled or not session_id:
            return []
        entry = self._sessions.get(session_id)
        if entry is None:
            return []
        if self._clock() - entry[0] > self.ttl_s:
            del self._sessions[session_id]
            return []
        return list(entry[1])

    def add(self, session_id: str | None, turn: Turn) -> None:
        if not self.enabled or not session_id:
            return
        turns = deque(self.history(session_id), maxlen=self.max_turns)
        turns.append(turn)
        self._sessions[session_id] = (self._clock(), turns)
        self._sessions.move_to_end(session_id)
        self._evict()

    def clear(self, session_id: str) -> None:
        self._sessions.pop(session_id, None)

    def _evict(self) -> None:
        now = self._clock()
        for sid in [s for s, (t, _) in self._sessions.items() if now - t > self.ttl_s]:
            del self._sessions[sid]
        while len(self._sessions) > self.max_sessions:
            self._sessions.popitem(last=False)  # least recently used
