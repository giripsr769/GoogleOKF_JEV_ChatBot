"""FastAPI service. Two endpoints, as the chat UI needs: GET /health and POST /api/text-to-sql."""
from __future__ import annotations

from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from fastapi.middleware.cors import CORSMiddleware

from okf_chat.api.schemas import HealthResponse, QueryResponse, QuestionRequest
from okf_chat.config import Settings, get_settings
from okf_chat.core.pipeline import Refusal


def create_app(settings: Settings | None = None, pipeline=None) -> FastAPI:
    """Pass `pipeline` to use a ready-made one (tests); otherwise it is built at startup, which verifies the database role."""
    settings = settings or get_settings()

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        if pipeline is not None:
            app.state.pipeline = pipeline
        else:
            from okf_chat.factory import build_pipeline  # lazy: keeps CrewAI out of plain imports

            app.state.pipeline = build_pipeline(settings)  # raises UnsafeDatabaseRole on a bad DATABASE_URL: startup stops
        try:
            yield
        finally:
            await app.state.pipeline.aclose()

    app = FastAPI(title="OKF chat service", version="0.1.0", lifespan=lifespan)
    app.add_middleware(
        CORSMiddleware, allow_origins=settings.cors_origin_list, allow_methods=["*"], allow_headers=["*"],
    )

    @app.get("/health", response_model=HealthResponse)
    async def health() -> HealthResponse:
        # only reachable once startup (including the database role check) has succeeded
        return HealthResponse(status="ok", tables_indexed=len(app.state.pipeline.navigator.concepts))

    @app.post("/api/text-to-sql", response_model=QueryResponse)
    async def text_to_sql(body: QuestionRequest) -> dict:
        try:
            result = await app.state.pipeline.ask(body.question, body.session_id)
        except Refusal as r:
            raise HTTPException(status_code=r.status_code, detail=r.detail) from None
        return result.to_response()

    return app


def app_factory() -> FastAPI:
    """Entry point for `uvicorn okf_chat.api.main:app_factory --factory`."""
    return create_app()
