from __future__ import annotations

from .schemas import JobPosting
from .utils import normalize_text


def dedupe_jobs(jobs: list[JobPosting], description_threshold: float = 0.98) -> list[JobPosting]:
    seen_keys: set[str] = set()
    kept: list[JobPosting] = []
    for job in jobs:
        key = "|".join([normalize_text(job.company), normalize_text(job.title), normalize_text(job.location)])
        if key in seen_keys:
            continue
        if _is_similar_duplicate(job, kept, description_threshold):
            continue
        seen_keys.add(key)
        kept.append(job)
    return kept


def _is_similar_duplicate(job: JobPosting, kept: list[JobPosting], threshold: float) -> bool:
    company = normalize_text(job.company)
    title = normalize_text(job.title)
    location = normalize_text(job.location)
    description = normalize_text(job.description)
    for existing in kept:
        if company != normalize_text(existing.company):
            continue
        if title != normalize_text(existing.title):
            continue
        if location and normalize_text(existing.location) and location != normalize_text(existing.location):
            continue
        existing_description = normalize_text(existing.description)
        if description and existing_description:
            shorter = min(len(description), len(existing_description))
            if shorter >= 300 and _description_overlap(description, existing_description) >= threshold:
                return True
    return False


def _description_overlap(left: str, right: str) -> float:
    shorter, longer = sorted([left[:2000], right[:2000]], key=len)
    if not shorter:
        return 0.0
    shared_prefix = 0
    for left_char, right_char in zip(shorter, longer):
        if left_char != right_char:
            break
        shared_prefix += 1
    if shared_prefix / len(shorter) >= 0.98:
        return shared_prefix / len(shorter)
    return 1.0 if shorter in longer else 0.0
