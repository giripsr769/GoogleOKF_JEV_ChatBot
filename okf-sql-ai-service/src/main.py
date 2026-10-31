"""FastAPI entrypoint: deterministic Text-to-SQL pipeline (Jev + OKF + OpenAI)."""
import asyncio
import os
import time
from contextlib import asynccontextmanager
from datetime import date, datetime
from decimal import Decimal

import psycopg2
import psycopg2.errors
import psycopg2.extras
from dotenv import load_dotenv
from fastapi import FastAPI, HTTPException
from fastapi.concurrency import run_in_threadpool
from fastapi.middleware.cors import CORSMiddleware
import openai
from openai import AsyncOpenAI
from pydantic import BaseModel, Field
from typesafe_sdk import TypeSafeAPITimeoutError

load_dotenv()

from .jev_guard import MAX_RISK, JevGuard, scope_of  # noqa: E402
from .answer_writer import compose_answer, wants_table  # noqa: E402
from .join_paths import expand as expand_join_paths  # noqa: E402
from .okf_loader import SchemaIndex  # noqa: E402
from .security import SQLValidationError  # noqa: E402
from .sql_generator import generate_validated  # noqa: E402

STATEMENT_TIMEOUT_MS = 3000
# Time budgets (seconds). The 3s limit above covers the database query only; these cover the AI calls and the whole request.
PIPELINE_TIMEOUT_S = float(os.getenv("PIPELINE_TIMEOUT_S", "30"))  # whole request, end to end
OPENAI_TIMEOUT_S = float(os.getenv("OPENAI_TIMEOUT_S", "20"))      # one OpenAI call (SQL, answer, embeddings)
JEV_TIMEOUT_S = float(os.getenv("JEV_TIMEOUT_S", "10"))            # one Jev call (normally well under 1s)


@asynccontextmanager
async def lifespan(app: FastAPI):
    openai_client = AsyncOpenAI(timeout=OPENAI_TIMEOUT_S, max_retries=1)
    app.state.openai = openai_client
    app.state.index = SchemaIndex(openai_client)
    await app.state.index.build_or_load()
    app.state.jev = JevGuard(scope=scope_of(app.state.index.tables), timeout=JEV_TIMEOUT_S)
    yield
    await app.state.jev.aclose()


app = FastAPI(title="OKF Text-to-SQL Service", version="1.0.0", lifespan=lifespan)
app.add_middleware(
    CORSMiddleware,
    allow_origins=os.getenv("CORS_ORIGINS", "http://localhost:4200").split(","),
    allow_methods=["POST", "GET"],
    allow_headers=["*"],
)


class QueryRequest(BaseModel):
    question: str = Field(min_length=3, max_length=500)


class QueryResponse(BaseModel):
    question: str
    sql: str
    tables_used: list[str]
    columns: list[str]
    rows: list[dict]
    row_count: int
    risk_score: float
    timings_ms: dict[str, int]
    answer: str = ""          # natural-language reply
    show_table: bool = True   # False = the UI should show only the reply, unless the user asked for a table


def _json_safe(v):
    if isinstance(v, Decimal):
        return float(v)
    if isinstance(v, (datetime, date)):
        return v.isoformat()
    return v


def _execute(sql: str) -> tuple[list[str], list[dict]]:
    conn = psycopg2.connect(os.getenv("DATABASE_URL", ""), options=f"-c statement_timeout={STATEMENT_TIMEOUT_MS}")
    try:
        conn.set_session(readonly=True, autocommit=False)
        with conn.cursor(cursor_factory=psycopg2.extras.RealDictCursor) as cur:
            cur.execute(sql)
            rows = [{k: _json_safe(v) for k, v in r.items()} for r in cur.fetchall()]
            cols = [d.name for d in cur.description]
        return cols, rows
    finally:
        conn.close()


@app.get("/health")
async def health():
    return {"status": "ok", "tables_indexed": len(app.state.index.tables)}


async def _pipeline(req: QueryRequest) -> QueryResponse:
    t: dict[str, int] = {}
    mark = time.perf_counter()

    def tick(name: str):
        nonlocal mark
        now = time.perf_counter()
        t[name] = int((now - mark) * 1000)
        mark = now

    # 1. Ingress gate (Jev Choice + Noul)
    gate = await app.state.jev.gate(req.question)
    tick("gate")
    if not gate.allowed:
        raise HTTPException(400, f"Request blocked: classified as '{gate.intent}'")

    # 2. OKF retrieval (FAISS), 3. Jev rerank
    candidates = await app.state.index.search(req.question)
    tick("retrieve")
    tables = await app.state.jev.rerank(req.question, candidates)
    tick("rerank")
    tables, _ = await expand_join_paths(app.state.jev, app.state.index, req.question, tables)
    tick("expand")

    # 4. SQL generation + 5a. sqlglot validation (one regeneration if the output does not parse)
    try:
        sql, _ = await generate_validated(app.state.openai, req.question, tables)
    except SQLValidationError as e:
        raise HTTPException(422, f"Generated SQL rejected: {e}")
    tick("generate")

    # 5b. Jev semantic risk score
    risk = await app.state.jev.risk(req.question, sql)
    tick("validate")
    if risk > MAX_RISK:
        raise HTTPException(422, f"Generated SQL rejected: semantic risk {risk:.2f}")

    # 6. Execute (read-only transaction, 3s timeout)
    try:
        cols, rows = await run_in_threadpool(_execute, sql)
    except psycopg2.errors.QueryCanceled:
        raise HTTPException(504, "Query exceeded the 3 second limit")
    except psycopg2.Error as e:
        raise HTTPException(422, f"Database error: {e.pgerror or e}")
    tick("execute")

    # 7. Human reply (table only if the user asked for one, or if no text could be produced)
    asked_for_table = wants_table(req.question)
    answer, table_needed = await compose_answer(app.state.openai, req.question, cols, rows, asked_for_table)
    tick("answer")

    return QueryResponse(
        question=req.question, sql=sql, tables_used=[x.table for x in tables],
        columns=cols, rows=rows, row_count=len(rows), risk_score=round(risk, 3), timings_ms=t,
        answer=answer, show_table=asked_for_table or table_needed,
    )


@app.post("/api/text-to-sql", response_model=QueryResponse)
async def text_to_sql(req: QueryRequest):
    """Runs the pipeline under one overall time budget so a stalled AI service can never hang the client."""
    try:
        return await asyncio.wait_for(_pipeline(req), timeout=PIPELINE_TIMEOUT_S)
    except (asyncio.TimeoutError, openai.APITimeoutError, TypeSafeAPITimeoutError):
        raise HTTPException(504, f"Request timed out: the service took longer than {PIPELINE_TIMEOUT_S:g} seconds")
