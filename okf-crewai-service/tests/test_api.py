"""API contract tests with a fake pipeline, plus a startup test against the Docker database (skipped without it)."""
from types import SimpleNamespace

import httpx
import pytest
from test_sql_executor import ADMIN_URL, needs_admin  # noqa: F401

from okf_chat.api.main import create_app
from okf_chat.config import Settings
from okf_chat.core.pipeline import PipelineResult, Refusal
from okf_chat.core.sql_executor import UnsafeDatabaseRole

UI_FIELDS = {"question", "sql", "tables_used", "columns", "rows", "row_count", "risk_score", "timings_ms", "answer", "show_table"}


class FakePipeline:
    def __init__(self, outcome):
        self.outcome, self.closed, self.sessions = outcome, False, []
        self.navigator = SimpleNamespace(concepts={"customers": 1, "orders": 2, "products": 3})

    async def ask(self, question, session_id=None):
        self.sessions.append(session_id)
        if isinstance(self.outcome, Exception):
            raise self.outcome
        return self.outcome

    async def aclose(self):
        self.closed = True


def _result():
    return PipelineResult(
        question="q", sql="SELECT 1", tables_used=["customers"], columns=["n"], rows=[{"n": 1}], row_count=1,
        risk_score=0.0123456, timings_ms={"total": 5}, answer="One.", show_table=False,
    )


async def _client(pipeline, **settings):
    app = create_app(Settings(_env_file=None, **settings), pipeline=pipeline)
    return app, httpx.AsyncClient(transport=httpx.ASGITransport(app=app), base_url="http://test")


async def _post(pipeline, body=None, **kw):
    app, client = await _client(pipeline, **kw)
    async with app.router.lifespan_context(app), client:
        return await client.post("/api/text-to-sql", json=body if body is not None else {"question": "how many?"})


async def test_health_reports_table_count():
    app, client = await _client(FakePipeline(_result()))
    async with app.router.lifespan_context(app), client:
        r = await client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok", "tables_indexed": 3}


async def test_success_returns_exactly_the_ui_fields():
    r = await _post(FakePipeline(_result()))
    assert r.status_code == 200
    assert set(r.json()) == UI_FIELDS
    assert r.json()["risk_score"] == 0.012


@pytest.mark.parametrize("status,detail", [
    (400, "Request blocked: classified as 'prompt_injection'"),
    (422, "Query blocked: semantic risk 0.91"),
    (504, "Query exceeded the 3 second limit"),
    (504, "Request timed out: the service took longer than 30 seconds"),
])
async def test_refusals_keep_status_and_detail(status, detail):
    r = await _post(FakePipeline(Refusal(status, detail, "code", "message")))
    assert r.status_code == status and r.json() == {"detail": detail}


@pytest.mark.parametrize("body", [{}, {"question": ""}, {"question": "x" * 1001}])
async def test_bad_question_is_422(body):
    assert (await _post(FakePipeline(_result()), body)).status_code == 422


async def test_cors_allows_configured_origin_only():
    app, client = await _client(FakePipeline(_result()), cors_origins="http://localhost:4200")
    async with app.router.lifespan_context(app), client:
        ok = await client.options("/api/text-to-sql", headers={"Origin": "http://localhost:4200", "Access-Control-Request-Method": "POST"})
        bad = await client.options("/api/text-to-sql", headers={"Origin": "http://evil.example", "Access-Control-Request-Method": "POST"})
    assert ok.headers["access-control-allow-origin"] == "http://localhost:4200"
    assert "access-control-allow-origin" not in bad.headers


async def test_session_id_is_passed_through_and_validated():
    p = FakePipeline(_result())
    assert (await _post(p, {"question": "q", "session_id": "c1abc-XYZ_9"})).status_code == 200
    assert (await _post(p, {"question": "q"})).status_code == 200
    assert p.sessions == ["c1abc-XYZ_9", None]
    for bad in ("", "has space", "x" * 65, "a;b"):
        assert (await _post(FakePipeline(_result()), {"question": "q", "session_id": bad})).status_code == 422


async def test_pipeline_is_closed_on_shutdown():
    p = FakePipeline(_result())
    app, client = await _client(p)
    async with app.router.lifespan_context(app), client:
        assert not p.closed
    assert p.closed


@needs_admin
async def test_startup_fails_with_superuser_url():
    app = create_app(Settings(_env_file=None, database_url=ADMIN_URL))
    with pytest.raises(UnsafeDatabaseRole):
        async with app.router.lifespan_context(app):
            pass
