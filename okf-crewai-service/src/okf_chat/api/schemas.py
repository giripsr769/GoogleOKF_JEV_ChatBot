"""Request and response bodies. The response matches the chat UI's QueryResponse."""
from pydantic import BaseModel, Field


class QuestionRequest(BaseModel):
    question: str = Field(min_length=1, max_length=1000)
    # optional: requests with the same id are one conversation, so follow-ups like "and last month?" work
    session_id: str | None = Field(default=None, min_length=1, max_length=64, pattern=r"^[A-Za-z0-9_-]+$")


class HealthResponse(BaseModel):
    status: str
    tables_indexed: int


class QueryResponse(BaseModel):
    question: str
    sql: str
    tables_used: list[str]
    columns: list[str]
    rows: list[dict]
    row_count: int
    risk_score: float
    timings_ms: dict[str, int]
    answer: str
    show_table: bool
