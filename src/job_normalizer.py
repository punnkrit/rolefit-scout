from __future__ import annotations

from typing import Any

from .schemas import JobPosting, SearchQuery
from .utils import stable_id


def normalize_serpapi_job(query: SearchQuery, raw: dict[str, Any]) -> JobPosting:
    title = raw.get("title") or ""
    company = raw.get("company_name") or raw.get("company") or ""
    location = raw.get("location") or raw.get("detected_extensions", {}).get("location") or ""
    description = raw.get("description") or ""
    url, apply_source = _best_url_and_source(raw)
    source = apply_source or raw.get("via") or raw.get("source") or ""
    date_posted = raw.get("detected_extensions", {}).get("posted_at") or raw.get("date_posted")
    job_id = raw.get("job_id") or stable_id([company, title, location, description[:500]])
    return JobPosting(
        job_id=job_id,
        title=title,
        company=company,
        location=location,
        description=description,
        source=source,
        url=url,
        date_posted=date_posted,
        search_query=query.query,
        raw_data=raw,
    )


def normalize_jobs(rows: list[tuple[SearchQuery, dict[str, Any]]]) -> list[JobPosting]:
    return [normalize_serpapi_job(query, raw) for query, raw in rows]


def _best_url(raw: dict[str, Any]) -> str | None:
    url, _ = _best_url_and_source(raw)
    return url


def _best_url_and_source(raw: dict[str, Any]) -> tuple[str | None, str | None]:
    apply_options = raw.get("apply_options") or []
    if apply_options and isinstance(apply_options, list):
        for option in apply_options:
            link = option.get("link")
            if link and "google.com/search" not in link:
                return link, option.get("title")
        if apply_options[0].get("link"):
            return apply_options[0].get("link"), apply_options[0].get("title")
    if raw.get("link"):
        return raw["link"], raw.get("source")
    if raw.get("share_link"):
        return raw["share_link"], raw.get("via")
    return None, None
