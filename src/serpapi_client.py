from __future__ import annotations

import json
from dataclasses import dataclass
from pathlib import Path
from time import perf_counter
from typing import Any, Callable

import requests

from .config import AppConfig
from .schemas import SearchQuery


class SerpApiError(RuntimeError):
    pass


@dataclass
class SerpApiSearchResult:
    rows: list[tuple[SearchQuery, dict[str, Any]]]
    messages: list[str]
    searches_with_results: int = 0


@dataclass
class GoogleJobsPage:
    jobs: list[dict[str, Any]]
    next_page_token: str | None = None


def search_google_jobs_page(query: SearchQuery, config: AppConfig, next_page_token: str | None = None) -> GoogleJobsPage:
    if not config.serpapi_api_key:
        raise SerpApiError("SERPAPI_API_KEY is missing.")
    params = {
        "engine": "google_jobs",
        "q": query.query,
        "google_domain": "google.com",
        "gl": "us",
        "hl": "en",
        "api_key": config.serpapi_api_key,
    }
    if query.location:
        params["location"] = query.location
    if next_page_token:
        params["next_page_token"] = next_page_token
    response = requests.get("https://serpapi.com/search.json", params=params, timeout=30)
    if response.status_code in {401, 403, 429}:
        raise SerpApiError(f"SerpApi quota or authentication issue: HTTP {response.status_code}")
    if response.status_code >= 400:
        detail = _response_error_detail(response)
        raise SerpApiError(f"SerpApi request failed: HTTP {response.status_code}{detail}")
    data = response.json()
    if "error" in data:
        message = str(data["error"])
        if "hasn't returned any results" in message.lower() or "no results" in message.lower():
            return GoogleJobsPage(jobs=[])
        raise SerpApiError(message)
    return GoogleJobsPage(
        jobs=data.get("jobs_results", []) or [],
        next_page_token=(data.get("serpapi_pagination") or {}).get("next_page_token"),
    )


def search_google_jobs(query: SearchQuery, config: AppConfig) -> list[dict[str, Any]]:
    return search_google_jobs_page(query, config).jobs


def search_google_jobs_paginated(
    query: SearchQuery,
    config: AppConfig,
    max_results: int = 50,
    max_pages: int = 5,
    trace_callback: Callable[[str, int, dict[str, Any]], None] | None = None,
) -> list[dict[str, Any]]:
    jobs: list[dict[str, Any]] = []
    next_page_token: str | None = None
    for page_index in range(1, max_pages + 1):
        start = perf_counter()
        page = search_google_jobs_page(query, config, next_page_token=next_page_token)
        if trace_callback:
            trace_callback(
                "search.serpapi_page",
                round((perf_counter() - start) * 1000),
                {
                    "query": query.query,
                    "location": query.location,
                    "page": page_index,
                    "result_count": len(page.jobs),
                    "has_next_page": bool(page.next_page_token),
                },
            )
        jobs.extend(page.jobs)
        if len(jobs) >= max_results or not page.next_page_token:
            break
        next_page_token = page.next_page_token
    return jobs[:max_results]


def search_many(queries: list[SearchQuery], config: AppConfig) -> list[tuple[SearchQuery, dict[str, Any]]]:
    rows: list[tuple[SearchQuery, dict[str, Any]]] = []
    for query in queries:
        for raw in search_google_jobs(query, config):
            rows.append((query, raw))
    return rows


def search_many_tolerant(queries: list[SearchQuery], config: AppConfig) -> SerpApiSearchResult:
    rows: list[tuple[SearchQuery, dict[str, Any]]] = []
    messages: list[str] = []
    searches_with_results = 0
    for query in queries:
        try:
            results = search_google_jobs(query, config)
        except SerpApiError as exc:
            messages.append(f"SerpApi query failed for '{query.query}': {exc}")
            continue
        if not results:
            messages.append(f"SerpApi returned no jobs for '{query.query}'.")
            continue
        searches_with_results += 1
        rows.extend((query, raw) for raw in results)
    if rows:
        messages.append(f"Using {len(rows)} live SerpApi job results from successful queries.")
    return SerpApiSearchResult(rows=rows, messages=messages, searches_with_results=searches_with_results)


def _response_error_detail(response: requests.Response) -> str:
    try:
        data = response.json()
    except ValueError:
        return ""
    message = data.get("error") or data.get("message")
    return f": {message}" if message else ""


def load_sample_jobs(path: str | Path = "tests/sample_jobs.json") -> list[tuple[SearchQuery, dict[str, Any]]]:
    data = json.loads(Path(path).read_text(encoding="utf-8"))
    rows: list[tuple[SearchQuery, dict[str, Any]]] = []
    for item in data:
        query = SearchQuery(query=item.get("_search_query", "demo query"), location=item.get("location_detected"), priority=1)
        rows.append((query, item))
    return rows
