from pathlib import Path

import pytest
from bundle_helpers import SHOP, make_bundle, table_md, write

from okf_chat.core.navigator import NavPolicy, Navigator
from okf_chat.core.okf_loader import Bundle
from okf_chat.guardrails.jev_client import JevUnavailable

REAL_BUNDLE = Path(__file__).resolve().parent.parent / "okf_bundle"


class FakeJudge:
    """Scores each table question from a dict keyed by question id (default 0.0); records every request."""

    def __init__(self, scores=None, error=False):
        self.scores, self.error, self.requests, self.questions = scores or {}, error, [], {}

    async def noul(self, state, questions):
        self.requests.append((state, list(questions)))
        self.questions.update(questions)
        if self.error:
            raise JevUnavailable("down")
        return {q: self.scores.get(q, 0.0) for q in questions}


@pytest.fixture
def shop(tmp_path):
    return make_bundle(tmp_path, SHOP)


# ---------------------------------------------------------------- selection
async def test_selects_tables_above_the_bar_best_first(shop):
    nav = Navigator(shop, FakeJudge({"orders": 0.9, "customers": 0.7, "products": 0.2}))
    r = await nav.navigate("q")
    assert r.selected == ["orders", "customers"] and r.found and r.stages == 1
    assert r.scored["products"] == 0.2


async def test_every_table_is_scored_in_one_request(shop):
    judge = FakeJudge()
    await Navigator(shop, judge).navigate("Top customers?")
    assert len(judge.requests) == 1
    assert judge.requests[0][0] == "Top customers?"  # the user's message is the state
    assert set(judge.requests[0][1]) == set(SHOP)


async def test_caps_the_number_of_picked_tables(shop):
    scores = {t: 0.9 - i * 0.01 for i, t in enumerate(["orders", "customers", "products", "employees"])}
    r = await Navigator(shop, FakeJudge(scores), NavPolicy(max_tables=2, max_bridges=0)).navigate("q")
    assert r.selected == ["orders", "customers"]


async def test_falls_back_to_the_single_best_table_when_nothing_is_clear(shop):
    r = await Navigator(shop, FakeJudge({"orders": 0.4, "customers": 0.3})).navigate("q")
    assert r.selected == ["orders"]


async def test_nothing_found_when_everything_is_below_the_floor(shop):
    r = await Navigator(shop, FakeJudge({"orders": 0.1})).navigate("q")
    assert not r.found and r.tables == []


async def test_select_threshold_is_inclusive(shop):
    r = await Navigator(shop, FakeJudge({"orders": 0.5})).navigate("q")
    assert r.selected == ["orders"]


async def test_jev_unavailable_propagates(shop):
    with pytest.raises(JevUnavailable):
        await Navigator(shop, FakeJudge(error=True)).navigate("q")


# ---------------------------------------------------------------- joins
async def test_bridge_tables_connect_distant_tables(shop):
    r = await Navigator(shop, FakeJudge({"customers": 0.9, "products": 0.8})).navigate("q")
    assert r.selected == ["customers", "products"]
    assert r.bridges == ["orders", "order_items"] and r.dropped == []
    assert r.tables == ["customers", "products", "orders", "order_items"]


async def test_adjacent_tables_need_no_bridge(shop):
    r = await Navigator(shop, FakeJudge({"orders": 0.9, "customers": 0.8})).navigate("q")
    assert r.bridges == []


async def test_bridge_budget_is_respected(shop):
    r = await Navigator(shop, FakeJudge({"customers": 0.9, "products": 0.8}), NavPolicy(max_bridges=1)).navigate("q")
    assert r.bridges == [] and r.dropped == ["products"] and "products" not in r.tables


async def test_never_routes_through_a_sensitive_table(tmp_path):
    # the only link between customers and employees is the sensitive salaries table
    nav = Navigator(make_bundle(tmp_path, SHOP), FakeJudge({"customers": 0.9, "employees": 0.8}))
    r = await nav.navigate("q")
    assert "salaries" not in r.tables and r.dropped == ["employees"] and "employees" not in r.tables


async def test_prefers_a_non_sensitive_route_when_one_exists(tmp_path):
    spec = {**SHOP, "orders": {"links": ["customers", "employees"]}}  # orders now also reaches employees
    r = await Navigator(make_bundle(tmp_path, spec), FakeJudge({"customers": 0.9, "employees": 0.8})).navigate("q")
    assert r.bridges == ["orders"] and "salaries" not in r.tables


# ---------------------------------------------------------------- sensitive
async def test_sensitive_table_is_reported_and_never_returned(shop):
    r = await Navigator(shop, FakeJudge({"salaries": 0.95, "employees": 0.8})).navigate("average salary")
    assert r.sensitive_hit == ["salaries"] and "salaries" not in r.tables
    assert r.selected == ["employees"]


async def test_no_fallback_pick_when_the_target_is_sensitive(shop):
    r = await Navigator(shop, FakeJudge({"salaries": 0.95, "orders": 0.3})).navigate("q")
    assert r.sensitive_hit == ["salaries"] and not r.found


async def test_weak_sensitive_score_is_not_a_hit(shop):
    r = await Navigator(shop, FakeJudge({"salaries": 0.3, "employees": 0.9})).navigate("q")
    assert r.sensitive_hit == []


# ---------------------------------------------------------------- scale
async def test_batches_large_requests(shop):
    judge = FakeJudge()
    await Navigator(shop, judge, NavPolicy(batch_size=4)).navigate("q")
    assert [len(ids) for _, ids in judge.requests] == [4, 2]


def big_bundle(tmp_path, per_section=50, sections=("sales", "hr", "finance")) -> Bundle:
    names = {s: [f"{s}_{i}" for i in range(per_section)] for s in sections}
    for s, ns in names.items():
        for n in ns:
            write(tmp_path, f"tables/{s}/{n}.md", table_md(n).replace(f"/tables/{n}.md", f"/tables/{s}/{n}.md"))
        entries = "\n".join(f"* [{n}](/tables/{s}/{n}.md) - The {n} table." for n in ns)
        write(tmp_path, f"tables/{s}/index.md", f"# {s}\n\n{entries}\n")
    body = "\n".join(f"# {s}\n\n" + "\n".join(f"* [{n}](/tables/{s}/{n}.md) - The {n} table." for n in ns) + "\n" for s, ns in names.items())
    write(tmp_path, "tables/index.md", "# Tables\n\n" + body)
    write(tmp_path, "index.md", '---\nokf_version: "0.2"\n---\n# x\n')
    return Bundle.load(tmp_path)


async def test_big_bundle_goes_two_stage_and_scores_only_the_best_sections(tmp_path):
    bundle = big_bundle(tmp_path)  # 150 tables, scan_limit 100
    judge = FakeJudge({"hr": 0.9, "hr_3": 0.95, "hr_7": 0.6})
    r = await Navigator(bundle, judge).navigate("q")
    assert r.stages == 2
    assert set(judge.requests[0][1]) == {"sales", "hr", "finance"}  # stage 1 asks about the sections
    stage2 = {t for _, ids in judge.requests[1:] for t in ids}
    assert stage2 == {f"hr_{i}" for i in range(50)}  # stage 2 scores only the winning section
    assert r.selected == ["hr_3"] and r.dropped == ["hr_7"]  # the synthetic tables are not linked, so hr_7 cannot be joined


async def test_small_bundle_stays_one_stage(shop):
    assert (await Navigator(shop, FakeJudge()).navigate("q")).stages == 1


# ---------------------------------------------------------------- context for the SQL writer
def test_render_context_has_only_the_requested_tables_without_links(shop):
    ctx = Navigator(shop, FakeJudge()).render_context(["orders", "customers"])
    assert "## Table: orders" in ctx and "## Table: customers" in ctx
    assert "## Table: products" not in ctx and "## Table: salaries" not in ctx
    assert "](" not in ctx and "references customers" in ctx  # links flattened to plain names


# ---------------------------------------------------------------- the real bundle's join graph
@pytest.mark.skipif(not REAL_BUNDLE.is_dir(), reason="run `okf-chat build` first")
def test_real_bundle_join_graph():
    nav = Navigator(Bundle.load(REAL_BUNDLE), FakeJudge())
    assert {"customers", "order_items", "payments"} <= nav.graph["orders"]
    # Hop count alone is a blunt tool: customers -> products is shortest through `reviews`, not through the
    # orders path a "what did customers buy" question needs. Relevance scores (neighbour expansion) cover that.
    assert nav._shortest_path({"customers"}, "products") == ["customers", "reviews", "products"]
    assert nav._shortest_path({"customers"}, "order_items") == ["customers", "orders", "order_items"]
    assert "salaries" in nav.sensitive and nav.graph["salaries"] == {"employees"}  # linked, but never used as a bridge
    assert all("salaries" not in (nav._shortest_path({"employees"}, t) or []) for t in nav.concepts)


# ---------------------------------------------------------------- dropping, neighbours and group labels
async def test_unjoinable_tables_are_kept_when_dropping_is_off(shop):
    policy = NavPolicy(max_bridges=0, drop_disconnected=False, neighbor_at=None)
    r = await Navigator(shop, FakeJudge({"customers": 0.9, "products": 0.8}), policy).navigate("q")
    assert r.selected == ["customers", "products"] and r.dropped == []


async def test_an_unjoinable_table_is_kept_when_jev_is_very_sure(shop):
    # "How many customers versus how many employees": both clearly needed, nothing links them
    r = await Navigator(shop, FakeJudge({"customers": 0.93, "employees": 0.92})).navigate("q")
    assert r.selected == ["customers", "employees"] and r.dropped == []


async def test_an_unjoinable_table_is_dropped_when_the_score_is_only_middling(shop):
    r = await Navigator(shop, FakeJudge({"customers": 0.93, "employees": 0.7})).navigate("q")
    assert r.selected == ["customers"] and r.dropped == ["employees"]


async def test_the_keep_rule_can_be_switched_off(shop):
    r = await Navigator(shop, FakeJudge({"customers": 0.99, "employees": 0.99}), NavPolicy(keep_unjoinable_at=None)).navigate("q")
    assert r.dropped == ["employees"]


async def test_linked_tables_with_a_little_relevance_are_added_as_neighbours(shop):
    # products scored only 0.2 but is linked to the picked order_items: a missing table breaks SQL, an extra one rarely does
    r = await Navigator(shop, FakeJudge({"order_items": 0.9, "products": 0.2, "employees": 0.2})).navigate("q")
    assert r.selected == ["order_items"] and r.neighbors == ["products"]  # employees is not linked to anything picked
    assert r.tables == ["order_items", "products"]


async def test_neighbours_need_the_minimum_score_and_can_be_switched_off(shop):
    scores = {"order_items": 0.9, "products": 0.1}
    assert (await Navigator(shop, FakeJudge(scores)).navigate("q")).neighbors == []
    scores["products"] = 0.2
    assert (await Navigator(shop, FakeJudge(scores), NavPolicy(neighbor_at=None)).navigate("q")).neighbors == []


async def test_neighbours_are_capped_and_best_first(shop):
    scores = {"orders": 0.9, "customers": 0.2, "order_items": 0.3}  # both are linked to orders
    r = await Navigator(shop, FakeJudge(scores), NavPolicy(max_neighbors=1)).navigate("q")
    assert r.neighbors == ["order_items"]


async def test_a_sensitive_table_is_never_added_as_a_neighbour(shop):
    r = await Navigator(shop, FakeJudge({"employees": 0.9, "salaries": 0.4})).navigate("q")
    assert "salaries" not in r.tables and r.sensitive_hit == []


async def test_no_neighbours_when_nothing_was_picked(shop):
    assert (await Navigator(shop, FakeJudge({"orders": 0.2})).navigate("q")).neighbors == []


async def test_table_questions_carry_the_group_label_only_when_there_are_groups(tmp_path, shop):
    judge = FakeJudge()
    await Navigator(shop, judge).navigate("q")
    assert "group" not in judge.questions["orders"].instructions  # flat bundle: no group context

    judge = FakeJudge({"hr": 0.9})
    await Navigator(big_bundle(tmp_path / "big"), judge).navigate("q")
    assert "'hr' group" in judge.questions["hr_3"].instructions
