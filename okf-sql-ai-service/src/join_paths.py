"""Join-path expansion: add bridge tables so selected tables can actually be joined.

FAISS + rerank can keep customers and products yet miss orders/order_items, the tables that connect
them. This module finds candidate bridges in the OKF foreign-key graph; Jev then decides which are
needed (the graph alone is ambiguous: customers-reviews-products is shorter than the purchase path).
"""
import re
from collections import Counter, defaultdict
from typing import TYPE_CHECKING

if TYPE_CHECKING:
    from .okf_loader import OKFTable

MAX_HOPS = 3        # at most 2 intermediate tables between two selected tables
MAX_CANDIDATES = 8  # cap on bridge candidates sent to Jev
_REL = re.compile(r"^\s*(\w+)\.\w+\s*->\s*(\w+)\.\w+")


def build_graph(tables: "list[OKFTable]") -> dict[str, set[str]]:
    """Undirected table graph from OKF `a.col -> b.id` relationship lines."""
    g: dict[str, set[str]] = defaultdict(set)
    for t in tables:
        for rel in t.relationships:
            m = _REL.match(rel)
            if m and m[1] != m[2]:
                g[m[1]].add(m[2])
                g[m[2]].add(m[1])
    return g


def _components(selected: set[str], g: dict[str, set[str]]) -> list[set[str]]:
    """Groups of selected tables already directly joinable to each other."""
    seen: set[str] = set()
    comps: list[set[str]] = []
    for start in sorted(selected):
        if start in seen:
            continue
        comp, stack = set(), [start]
        while stack:
            n = stack.pop()
            if n in comp:
                continue
            comp.add(n)
            stack += [x for x in g[n] if x in selected and x not in comp]
        seen |= comp
        comps.append(comp)
    return comps


def bridge_candidates(selected: list[str], g: dict[str, set[str]]) -> list[str]:
    """Non-selected tables lying on short FK paths between disconnected groups of selected tables."""
    sel = set(selected)
    comps = _components(sel, g)
    if len(comps) < 2:
        return []
    comp_of = {n: i for i, c in enumerate(comps) for n in c}
    score: Counter[str] = Counter()
    for a in sorted(sel):
        stack = [(a, [a])]
        while stack:
            node, path = stack.pop()
            edges = len(path)  # edges after stepping to a neighbour
            for nb in sorted(g[node]):
                if nb in path:
                    continue
                if nb in sel:
                    if comp_of[nb] != comp_of[a]:
                        for mid in path[1:]:
                            score[mid] += 1
                elif edges < MAX_HOPS:
                    stack.append((nb, path + [nb]))
    return [t for t, _ in sorted(score.items(), key=lambda kv: (-kv[1], kv[0]))][:MAX_CANDIDATES]


async def expand(jev, index, question: str, selected: "list[OKFTable]") -> "tuple[list[OKFTable], list[str]]":
    """Return (selected + Jev-approved bridge tables, bridge names added)."""
    names = bridge_candidates([t.table for t in selected], index.graph)
    if not names:
        return selected, []
    by_name = {t.table: t for t in index.tables}
    bridges = await jev.select_bridges(question, selected, [by_name[n] for n in names if n in by_name])
    return selected + bridges, [t.table for t in bridges]
