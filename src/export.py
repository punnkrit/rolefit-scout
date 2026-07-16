from __future__ import annotations

import pandas as pd

from .schemas import ScoredJob


TRACKER_COLUMNS = [
    "rank",
    "job_id",
    "recommended_action",
    "overall_fit_score",
    "sponsorship_risk",
    "company",
    "title",
    "location",
    "source",
    "date_posted",
    "role_fit",
    "skill_fit",
    "experience_fit",
    "location_fit",
    "industry_fit",
    "sponsorship_fit",
    "sponsorship_evidence",
    "sponsorship_reasoning_summary",
    "key_matches",
    "key_gaps",
    "explanation",
    "url",
    "human_review_label",
    "notes",
    "search_query",
]


def jobs_to_dataframe(jobs: list[ScoredJob]) -> pd.DataFrame:
    rows = []
    for job in jobs:
        row = job.model_dump()
        row["sponsorship_risk"] = job.sponsorship_risk.value
        row["key_matches"] = "; ".join(job.key_matches)
        row["key_gaps"] = "; ".join(job.key_gaps)
        rows.append(row)
    return pd.DataFrame(rows, columns=TRACKER_COLUMNS)


def dataframe_to_csv(df: pd.DataFrame) -> bytes:
    return df.to_csv(index=False).encode("utf-8")
