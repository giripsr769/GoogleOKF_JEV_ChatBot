"""Pick the tables a question needs, using the OKF bundle and Jev.

Only the tables chosen here are ever described to the SQL-writing model (zero schema leakage).

    1. Score: one Jev yes/no question per candidate table, asked in one request.
       Big bundles go two-stage: score the index.md sections first, then only the tables in the best sections.
    2. Select: keep the clearly relevant tables, or the single best one when nothing is clear.
    3. Connect: add the fewest bridge tables so the chosen tables can be joined, following OKF links and
       never routing through a sensitive table. A chosen table that cannot be joined is dropped, unless
       Jev is very sure it is needed.
    4. Neighbours: add a few linked tables that scored a little, because a missing table breaks the SQL
       while an extra one rarely does.
    5. Sensitive: when a sensitive table is clearly what the question is about, report it so the caller refuses.
"""
from __future__ import annotations

import asyncio
import re
from collections import deque
from dataclasses import dataclass, field
from typing import Callable

from typesafe_sdk import Noul

from okf_chat.core.okf_loader import Bundle, Concept
from okf_chat.guardrails.jev_client import Judge


@dataclass(frozen=True)
class NavPolicy:
    select_at: float = 0.5  # a table at or above this is "needed"
    floor: float = 0.25  # if nothing reaches select_at, take the best table only when it reaches this
    max_tables: int = 4  # most tables picked by relevance
    max_bridges: int = 2  # most extra tables added just to connect the picked ones
    drop_disconnected: bool = True  # a picked table with no short join path to the others is dropped...
    keep_unjoinable_at: float | None = 0.9  # ...unless Jev is this sure it is needed (e.g. two separate counts)
    neighbor_at: float | None = 0.15  # linked tables scoring at least this are added (None turns it off)
    max_neighbors: int = 2
    scan_limit: int = 100  # up to this many tables are scored in one stage; more goes two-stage
    batch_size: int = 100  # questions per Jev request
    max_columns_in_question: int = 25
    max_sections: int = 3  # two-stage only: sections kept after stage 1
    section_at: float = 0.3  # two-stage only: a section at or above this is kept


@dataclass
class NavResult:
    selected: list[str] = field(default_factory=list)  # chosen by relevance, best first
    bridges: list[str] = field(default_factory=list)  # added only to connect the chosen tables
    neighbors: list[str] = field(default_factory=list)  # linked tables added for recall
    dropped: list[str] = field(default_factory=list)  # chosen by relevance but unjoinable, so left out
    sensitive_hit: list[str] = field(default_factory=list)  # sensitive tables the question clearly targets
    scored: dict[str, float] = field(default_factory=dict)  # relevance of every table that was scored
    stages: int = 1

    @property
    def tables(self) -> list[str]:
        """Everything the SQL writer may see. Never sensitive."""
        return self.selected + self.neighbors + self.bridges

    @property
    def found(self) -> bool:
        return bool(self.selected)


QuestionBuilder = Callable[[str, Concept, "str | None", int], Noul]  # (table, concept, group, max_columns) -> question


def table_question(name: str, c: Concept, group: str | None, max_columns: int) -> Noul:
    cols = c.column_names[:max_columns]
    more = f", and {len(c.column_names) - max_columns} more" if len(c.column_names) > max_columns else ""
    tags = f" Keywords: {', '.join(c.tags[:8])}." if c.tags else ""
    where = f" It belongs to the '{group}' group." if group else ""
    # The last sentence matters: "average rating for Desk Lamp" needs `products` to find the item by name, but a table is
    # rarely scored as needed when the message only names one of its rows (measured: named-item recall 7/12 without it, 11/12 with it).
    return Noul(
        instructions=(
            f"Is the database table '{name}' needed to answer this message? {c.description}{where}{tags} Columns: {', '.join(cols)}{more}."
            " It is also needed when the message names a specific item that is stored as a row here (for example a product, person or place called by name)."
        ),
        criteria={
            "true": "The message asks about, filters by, groups by or needs data stored in this table, or it names a specific item that this table stores",
            "false": "This table holds nothing the message needs and the message names nothing stored in it",
        },
    )


def _section_question(title: str, members: list[tuple[str, Concept]]) -> Noul:
    lines = "; ".join(f"{n}: {' '.join(c.description.split())[:70]}" for n, c in members[:40])
    return Noul(
        instructions=f"Is any table in the '{title}' group needed to answer this message? Tables: {lines}.",
        criteria={"true": "At least one table in this group holds data the message needs", "false": "No table in this group is relevant"},
    )


class Navigator:
    def __init__(self, bundle: Bundle, judge: Judge, policy: NavPolicy | None = None, question_builder: QuestionBuilder | None = None):
        self.bundle, self.judge, self.policy = bundle, judge, policy or NavPolicy()
        self.build_question = question_builder or table_question
        self.concepts = bundle.tables()
        self.sensitive = bundle.sensitive_tables()
        by_path = {c.path: n for n, c in self.concepts.items()}
        self.graph: dict[str, set[str]] = {n: set() for n in self.concepts}  # undirected join graph from OKF links
        for n, c in self.concepts.items():
            for target in c.links:
                other = by_path.get(target)
                if other and other != n:
                    self.graph[n].add(other)
                    self.graph[other].add(n)
        self.group_of: dict[str, str] = {}
        self.sections = self._sections(by_path)

    # ---------------------------------------------------------------- public
    async def navigate(self, question: str) -> NavResult:
        """Raises JevUnavailable when Jev cannot be reached."""
        candidates, stages = list(self.concepts), 1
        if len(candidates) > self.policy.scan_limit and self.sections:
            candidates, stages = await self._narrow_by_section(question), 2
        scored = await self._score(question, {
            n: self.build_question(n, self.concepts[n], self.group_of.get(n), self.policy.max_columns_in_question) for n in candidates
        })
        return self.decide(scored, stages)

    def decide(self, scored: dict[str, float], stages: int = 1) -> NavResult:
        """Turn relevance scores into a table list. Pure: no network, so it can be replayed on saved scores."""
        p = self.policy
        r = NavResult(scored=scored, stages=stages)
        ranked = sorted(scored, key=scored.get, reverse=True)
        r.sensitive_hit = [t for t in ranked if t in self.sensitive and scored[t] >= p.select_at]
        usable = [t for t in ranked if t not in self.sensitive]
        picked = [t for t in usable if scored[t] >= p.select_at][: p.max_tables]
        if not picked and usable and scored[usable[0]] >= p.floor and not r.sensitive_hit:
            picked = [usable[0]]
        r.selected = picked
        self._connect(r)
        self._add_neighbors(r)
        return r

    def render_context(self, tables: list[str]) -> str:
        """The OKF text of exactly these tables, compact, for the SQL-writing model. Links become plain names."""
        parts = []
        for name in tables:
            body = re.sub(r"\[([^\]]+)\]\([^)]*\)", r"\1", self.concepts[name].body).strip()
            parts.append(f"## Table: {name}\n{body}")
        return "\n\n".join(parts)

    # ---------------------------------------------------------------- scoring
    async def _score(self, question: str, questions: dict[str, Noul]) -> dict[str, float]:
        size = self.policy.batch_size
        items = list(questions.items())
        chunks = [dict(items[i : i + size]) for i in range(0, len(items), size)]
        results = await asyncio.gather(*(self.judge.noul(question, chunk) for chunk in chunks))
        scores: dict[str, float] = {}
        for r in results:
            scores.update(r)
        return scores

    async def _narrow_by_section(self, question: str) -> list[str]:
        scores = await self._score(question, {t: _section_question(t, m) for t, m in self.sections.items()})
        ranked = sorted(scores, key=scores.get, reverse=True)
        keep = [s for s in ranked if scores[s] >= self.policy.section_at][: self.policy.max_sections] or ranked[:1]
        return [n for s in keep for n, _ in self.sections[s]]

    def _sections(self, by_path: dict[str, str]) -> dict[str, list[tuple[str, Concept]]]:
        """index.md sections of /tables as {section title: [(table, concept)]}; tables not listed go to 'Other'.
        Also fills group_of. Returns {} when there is only one section (nothing to narrow by)."""
        sections: dict[str, list[tuple[str, Concept]]] = {}
        for e in self.bundle.index_entries("/tables"):
            n = by_path.get(e.url)
            if n and n not in self.group_of:
                sections.setdefault(e.section or "Other", []).append((n, self.concepts[n]))
                self.group_of[n] = e.section or "Other"
        rest = [(n, c) for n, c in self.concepts.items() if n not in self.group_of]
        if rest:
            sections.setdefault("Other", []).extend(rest)
            self.group_of.update({n: "Other" for n, _ in rest})
        if len(sections) <= 1:
            self.group_of = {}  # a single group says nothing useful
            return {}
        return sections

    # ---------------------------------------------------------------- joining
    def _connect(self, r: NavResult) -> None:
        """Grow a connected set from the best table; add the fewest bridge tables to reach each other chosen table."""
        if len(r.selected) < 2:
            return
        p = self.policy
        connected, unreachable = {r.selected[0]}, []
        for target in r.selected[1:]:
            path = self._shortest_path(connected, target)
            interior = path[1:-1] if path else None
            new = [b for b in (interior or []) if b not in r.bridges and b not in r.selected]
            if interior is None or len(r.bridges) + len(new) > p.max_bridges:
                unreachable.append(target)
                continue
            r.bridges += new
            connected.update(interior)
            connected.add(target)
        if p.drop_disconnected:
            sure = p.keep_unjoinable_at if p.keep_unjoinable_at is not None else 2.0  # 2.0: never keep
            r.dropped = [t for t in unreachable if r.scored.get(t, 0.0) < sure]
            r.selected = [t for t in r.selected if t not in r.dropped]

    def _shortest_path(self, sources: set[str], target: str) -> list[str] | None:
        """Shortest link path from any source table to the target, never through a sensitive table."""
        limit = self.policy.max_bridges + 1  # most hops that stay within the bridge budget
        queue = deque((s, [s]) for s in sorted(sources))
        seen = set(sources)
        while queue:
            node, path = queue.popleft()
            if node == target:
                return path
            if len(path) - 1 >= limit:
                continue
            for nxt in sorted(self.graph.get(node, ())):
                if nxt not in seen and nxt not in self.sensitive:
                    seen.add(nxt)
                    queue.append((nxt, path + [nxt]))
        return None

    def _add_neighbors(self, r: NavResult) -> None:
        p = self.policy
        if p.neighbor_at is None or not r.selected:
            return
        have = set(r.tables)
        found: dict[str, float] = {}
        for t in r.selected:
            for n in self.graph[t]:
                s = r.scored.get(n, 0.0)
                if n not in have and n not in self.sensitive and s >= p.neighbor_at:
                    found[n] = s
        r.neighbors = sorted(found, key=found.get, reverse=True)[: p.max_neighbors]
