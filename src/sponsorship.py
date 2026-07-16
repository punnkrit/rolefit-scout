from __future__ import annotations

import re

from .schemas import JobPosting, SponsorshipAssessment, SponsorshipRisk


SPONSOR_POSITIVE = [
    r"visa sponsorship (is )?available",
    r"sponsorship available",
    r"open to sponsor",
    r"open to sponsoring",
    r"will sponsor",
    r"h-?1b sponsorship",
]

NO_SPONSORSHIP = [
    r"without sponsorship",
    r"will not sponsor",
    r"no sponsorship",
    r"sponsorship is not available",
    r"unable to sponsor",
    r"must be authorized to work .* without .* sponsorship",
]

HIGH_RISK = [
    r"u\.?s\.? citizenship required",
    r"us citizenship required",
    r"security clearance required",
    r"clearance required",
    r"citizen(?:ship)? required",
]


def assess_sponsorship_deterministic(job: JobPosting) -> SponsorshipAssessment:
    text = " ".join([job.title, job.company, job.location, job.description]).lower()
    for pattern in HIGH_RISK:
        evidence = _first_match_context(text, pattern)
        if evidence:
            return SponsorshipAssessment(
                job_id=job.job_id,
                sponsorship_risk=SponsorshipRisk.high_risk,
                evidence=evidence,
                reasoning_summary="The posting contains citizenship or clearance language that is high risk for sponsorship-sensitive candidates.",
            )
    for pattern in NO_SPONSORSHIP:
        evidence = _first_match_context(text, pattern)
        if evidence:
            return SponsorshipAssessment(
                job_id=job.job_id,
                sponsorship_risk=SponsorshipRisk.no_sponsorship,
                evidence=evidence,
                reasoning_summary="The posting explicitly says candidates must not need sponsorship or that sponsorship is unavailable.",
            )
    for pattern in SPONSOR_POSITIVE:
        evidence = _first_match_context(text, pattern)
        if evidence:
            return SponsorshipAssessment(
                job_id=job.job_id,
                sponsorship_risk=SponsorshipRisk.sponsor_friendly,
                evidence=evidence,
                reasoning_summary="The posting explicitly includes sponsorship-positive wording.",
            )
    return SponsorshipAssessment(
        job_id=job.job_id,
        sponsorship_risk=SponsorshipRisk.unclear,
        evidence="No explicit sponsorship statement found.",
        reasoning_summary="The posting does not provide enough evidence to claim sponsorship availability.",
    )


def _first_match_context(text: str, pattern: str, window: int = 90) -> str:
    match = re.search(pattern, text, re.IGNORECASE)
    if not match:
        return ""
    start = max(0, match.start() - window)
    end = min(len(text), match.end() + window)
    return text[start:end].strip()
