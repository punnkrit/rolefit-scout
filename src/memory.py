from __future__ import annotations

from pathlib import Path

from .cache import MEMORY_PATH, read_json, write_json
from .schemas import FeedbackRecord, ReviewLabel, SearchMemory


def load_memory(path: Path = MEMORY_PATH) -> SearchMemory:
    if not path.exists():
        return SearchMemory()
    return SearchMemory.model_validate(read_json(path))


def save_memory(memory: SearchMemory, path: Path = MEMORY_PATH) -> None:
    write_json(path.parent, path.name, memory)


def update_memory_from_feedback(memory: SearchMemory, feedback: list[FeedbackRecord]) -> SearchMemory:
    preferred = set(memory.preferred_role_families)
    rejected = set(memory.rejected_role_families)
    avoid = set(memory.companies_or_industries_to_avoid)
    useful_queries = set(memory.useful_query_patterns)
    poor_queries = set(memory.poor_query_patterns)
    seniority_flags = []

    for item in feedback:
        label = item.label.value if isinstance(item.label, ReviewLabel) else str(item.label)
        if label in {ReviewLabel.apply.value, ReviewLabel.maybe.value}:
            if item.role_family:
                preferred.add(item.role_family)
            if item.query:
                useful_queries.add(item.query)
        if label in {ReviewLabel.reject.value, ReviewLabel.wrong_role.value}:
            if item.role_family:
                rejected.add(item.role_family)
            if item.query:
                poor_queries.add(item.query)
        if label in {ReviewLabel.sponsorship_issue.value}:
            memory.sponsorship_risk_sensitivity = "high"
            if item.query:
                poor_queries.add(item.query)
        if label in {ReviewLabel.too_senior.value}:
            seniority_flags.append("avoid senior roles unless explicitly post-MBA appropriate")
        if label in {ReviewLabel.bad_location.value} and item.company:
            avoid.add(item.company)

    return SearchMemory(
        preferred_role_families=sorted(preferred),
        rejected_role_families=sorted(rejected),
        companies_or_industries_to_avoid=sorted(avoid),
        sponsorship_risk_sensitivity=memory.sponsorship_risk_sensitivity,
        seniority_calibration="; ".join(sorted(set(seniority_flags))) or memory.seniority_calibration,
        useful_query_patterns=sorted(useful_queries),
        poor_query_patterns=sorted(poor_queries),
    )
