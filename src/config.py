from __future__ import annotations

import os
from dataclasses import dataclass

from dotenv import load_dotenv


DEFAULT_MODEL = "gpt-5.4-nano-2026-03-17"


@dataclass(frozen=True)
class AppConfig:
    openai_api_key: str | None
    serpapi_api_key: str | None
    openai_model: str = DEFAULT_MODEL
    max_searches_per_run: int = 8
    max_jobs_to_score: int = 25

    @property
    def has_openai_key(self) -> bool:
        return bool(self.openai_api_key)

    @property
    def has_serpapi_key(self) -> bool:
        return bool(self.serpapi_api_key)


def _int_env(name: str, default: int) -> int:
    try:
        return int(os.getenv(name, default))
    except (TypeError, ValueError):
        return default


def load_config() -> AppConfig:
    load_dotenv()
    return AppConfig(
        openai_api_key=os.getenv("OPENAI_API_KEY"),
        serpapi_api_key=os.getenv("SERPAPI_API_KEY"),
        openai_model=os.getenv("OPENAI_MODEL", DEFAULT_MODEL),
        max_searches_per_run=max(1, min(8, _int_env("MAX_SEARCHES_PER_RUN", 8))),
        max_jobs_to_score=max(1, _int_env("MAX_JOBS_TO_SCORE", 25)),
    )
