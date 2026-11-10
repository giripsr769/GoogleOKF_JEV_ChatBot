"""All settings come from environment variables (or a .env file), so the service needs no code changes per application."""
from functools import lru_cache

from pydantic_settings import BaseSettings, SettingsConfigDict


class Settings(BaseSettings):
    model_config = SettingsConfigDict(env_file=".env", extra="ignore")

    openai_api_key: str = ""
    typesafe_api_key: str = ""
    openai_model: str = "gpt-6-luna"
    jev_model: str = "jev-latest"

    database_url: str = "postgresql://okf_readonly:okf_readonly@localhost:5433/shop"
    okf_bundle_dir: str = "okf_bundle"

    cors_origins: str = "http://localhost:4200"
    pipeline_timeout_s: float = 30
    openai_timeout_s: float = 20
    jev_timeout_s: float = 10
    jev_fail_open: bool = False  # False: if Jev is unreachable, refuse to answer

    natural_answers: bool = True
    answer_max_rows: int = 30
    max_result_rows: int = 100
    statement_timeout_ms: int = 3000
    sql_max_retries: int = 2
    navigator_max_tables: int = 4

    memory_turns: int = 4  # earlier turns remembered per chat session; 0 turns memory off
    memory_ttl_s: float = 1800  # a session is forgotten after this many idle seconds
    memory_max_sessions: int = 500

    @property
    def cors_origin_list(self) -> list[str]:
        return [o.strip() for o in self.cors_origins.split(",") if o.strip()]


@lru_cache
def get_settings() -> Settings:
    return Settings()
