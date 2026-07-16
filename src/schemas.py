from __future__ import annotations

from enum import Enum
from typing import Any, Literal, TypedDict

from pydantic import BaseModel, Field, field_validator


class RemotePreference(str, Enum):
    remote = "remote"
    hybrid = "hybrid"
    onsite = "onsite"
    any = "any"


class DesiredSeniority(str, Enum):
    internship = "internship"
    entry = "entry"
    mid = "mid"
    senior = "senior"
    post_mba = "post_mba"
    any = "any"


class SponsorshipTiming(str, Enum):
    now = "now"
    future = "future"
    not_needed = "not_needed"
    unknown = "unknown"


class SponsorshipRisk(str, Enum):
    sponsor_friendly = "Sponsor-Friendly"
    no_sponsorship = "No Sponsorship"
    high_risk = "High Risk"
    unclear = "Unclear"


class SearchStrategyType(str, Enum):
    target_role = "target_role"
    adjacent_role = "adjacent_role"
    broadened_repair = "broadened_repair"
    sponsorship_probe = "sponsorship_probe"


class ReviewLabel(str, Enum):
    apply = "Apply"
    maybe = "Maybe"
    reject = "Reject"
    wrong_role = "Wrong Role"
    sponsorship_issue = "Sponsorship Issue"
    too_senior = "Too Senior"
    bad_location = "Bad Location"
    duplicate = "Duplicate"


class ChatMessage(BaseModel):
    role: Literal["user", "assistant", "system"] = "user"
    content: str = ""


class CandidateProfile(BaseModel):
    name: str | None = None
    education: list[str] = Field(default_factory=list)
    current_status: str = ""
    target_functions: list[str] = Field(default_factory=list)
    skills: list[str] = Field(default_factory=list)
    tools: list[str] = Field(default_factory=list)
    industries: list[str] = Field(default_factory=list)
    experience_summary: str = ""
    seniority_level: str = ""
    notable_achievements: list[str] = Field(default_factory=list)
    strengths_for_search: list[str] = Field(default_factory=list)
    potential_gaps: list[str] = Field(default_factory=list)
    evidence_notes: list[str] = Field(default_factory=list)
    interview_insights: list[str] = Field(default_factory=list)
    positioning_notes: list[str] = Field(default_factory=list)


class UserPreferences(BaseModel):
    primary_goal: str = ""
    target_job_titles: list[str] = Field(default_factory=list)
    acceptable_adjacent_roles: list[str] = Field(default_factory=list)
    role_families_to_avoid: list[str] = Field(default_factory=list)
    preferred_locations: list[str] = Field(default_factory=list)
    excluded_locations: list[str] = Field(default_factory=list)
    remote_preference: RemotePreference = RemotePreference.any
    target_industries: list[str] = Field(default_factory=list)
    work_authorization_status: str = ""
    requires_sponsorship: bool = True
    sponsorship_timing: SponsorshipTiming = SponsorshipTiming.future
    desired_seniority: DesiredSeniority = DesiredSeniority.post_mba
    excluded_companies: list[str] = Field(default_factory=list)
    include_keywords: list[str] = Field(default_factory=list)
    exclude_keywords: list[str] = Field(default_factory=list)
    optimization_priority: str = "balanced fit"
    max_searches: int = Field(default=8, ge=1, le=8)


class SearchQuery(BaseModel):
    query: str
    location: str | None = None
    rationale: str = ""
    expected_tradeoff: str = ""
    priority: int = Field(default=1, ge=1)
    job_family: str = ""
    strategy_type: SearchStrategyType = SearchStrategyType.target_role
    confidence: float = Field(default=0.5, ge=0, le=1)


class SearchQueryPlan(BaseModel):
    queries: list[SearchQuery] = Field(default_factory=list)


class SearchStrategyPlan(BaseModel):
    strategy_summary: str = ""
    job_families: list[str] = Field(default_factory=list)
    queries: list[SearchQuery] = Field(default_factory=list)


class StrategyApproval(BaseModel):
    approved: bool = False
    edited_queries: list[SearchQuery] = Field(default_factory=list)
    reviewer_notes: str = ""


class QueryDiagnostic(BaseModel):
    query: str
    location: str | None = None
    result_count: int = 0
    repaired: bool = False
    repair_rationale: str = ""
    error: str = ""


class QueryRepairDecision(BaseModel):
    should_retry: bool = False
    replacement_query: str | None = None
    replacement_location: str | None = None
    repair_reason: str = ""
    expected_improvement: str = ""


class JobPosting(BaseModel):
    job_id: str
    title: str
    company: str
    location: str
    description: str = ""
    source: str = ""
    url: str | None = None
    date_posted: str | None = None
    search_query: str = ""
    raw_data: dict[str, Any] = Field(default_factory=dict)

    @field_validator("url", mode="before")
    @classmethod
    def blank_url_to_none(cls, value: Any) -> str | None:
        if value in ("", None):
            return None
        return str(value)


class SponsorshipAssessment(BaseModel):
    job_id: str
    sponsorship_risk: SponsorshipRisk = SponsorshipRisk.unclear
    evidence: str = ""
    reasoning_summary: str = ""


class SponsorshipAssessmentList(BaseModel):
    assessments: list[SponsorshipAssessment] = Field(default_factory=list)


class TriageSelection(BaseModel):
    job_id: str
    keep: bool = True
    priority: int = Field(default=1, ge=1)
    reason: str = ""


class TriageSelectionList(BaseModel):
    selections: list[TriageSelection] = Field(default_factory=list)


class JobScore(BaseModel):
    job_id: str
    role_fit: int = Field(ge=0, le=5)
    skill_fit: int = Field(ge=0, le=5)
    experience_fit: int = Field(ge=0, le=5)
    location_fit: int = Field(ge=0, le=5)
    industry_fit: int = Field(ge=0, le=5)
    sponsorship_fit: int = Field(ge=0, le=5)
    sponsorship_risk: SponsorshipRisk = SponsorshipRisk.unclear
    sponsorship_evidence: str = ""
    sponsorship_reasoning_summary: str = ""
    key_matches: list[str] = Field(default_factory=list)
    key_gaps: list[str] = Field(default_factory=list)
    recommended_action: Literal["Apply", "Maybe", "Skip"]
    explanation: str = ""
    role_summary: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)
    company_insights: list[str] = Field(default_factory=list)


class ScoredJob(BaseModel):
    rank: int = 0
    job_id: str
    company: str
    title: str
    location: str
    overall_fit_score: int = Field(ge=0, le=100)
    role_fit: int = Field(ge=0, le=5)
    skill_fit: int = Field(ge=0, le=5)
    experience_fit: int = Field(ge=0, le=5)
    location_fit: int = Field(ge=0, le=5)
    industry_fit: int = Field(ge=0, le=5)
    sponsorship_fit: int = Field(ge=0, le=5)
    sponsorship_risk: SponsorshipRisk = SponsorshipRisk.unclear
    sponsorship_evidence: str = ""
    sponsorship_reasoning_summary: str = ""
    key_matches: list[str] = Field(default_factory=list)
    key_gaps: list[str] = Field(default_factory=list)
    recommended_action: Literal["Apply", "Maybe", "Skip"]
    explanation: str = ""
    job_description: str = ""
    role_summary: str = ""
    responsibilities: list[str] = Field(default_factory=list)
    qualifications: list[str] = Field(default_factory=list)
    company_insights: list[str] = Field(default_factory=list)
    source: str = ""
    date_posted: str | None = None
    url: str | None = None
    search_query: str = ""
    human_review_label: str | None = None
    notes: str | None = None


class ScoredJobList(BaseModel):
    jobs: list[JobScore] = Field(default_factory=list)


class FeedbackRecord(BaseModel):
    job_id: str
    label: ReviewLabel | str
    notes: str = ""
    role_family: str = ""
    company: str = ""
    query: str = ""


class SearchMemory(BaseModel):
    preferred_role_families: list[str] = Field(default_factory=list)
    rejected_role_families: list[str] = Field(default_factory=list)
    companies_or_industries_to_avoid: list[str] = Field(default_factory=list)
    sponsorship_risk_sensitivity: str = "medium"
    seniority_calibration: str = ""
    useful_query_patterns: list[str] = Field(default_factory=list)
    poor_query_patterns: list[str] = Field(default_factory=list)


class CoachTurn(BaseModel):
    reply: str = ""
    open_questions: list[str] = Field(default_factory=list)
    interview_complete: bool = False


class CareerBrief(BaseModel):
    positioning: str = ""
    target_role_lanes: list[str] = Field(default_factory=list)
    adjacent_role_lanes: list[str] = Field(default_factory=list)
    excluded_lanes: list[str] = Field(default_factory=list)
    target_industries: list[str] = Field(default_factory=list)
    company_stage_preferences: list[str] = Field(default_factory=list)
    location_scope: list[str] = Field(default_factory=list)
    remote_preference: RemotePreference = RemotePreference.any
    sponsorship_stance: str = ""
    seniority_calibration: str = ""
    resume_evidence: list[str] = Field(default_factory=list)
    user_evidence: list[str] = Field(default_factory=list)
    search_thesis: str = ""
    scoring_guidance: str = ""
    unresolved_questions: list[str] = Field(default_factory=list)
    readiness: Literal["needs_more_info", "ready_to_search"] = "needs_more_info"
    confidence: float = Field(default=0.5, ge=0, le=1)


class GraphState(TypedDict, total=False):
    resume_text: str
    candidate_profile: dict[str, Any]
    messages: list[dict[str, str]]
    inferred_preferences: dict[str, Any]
    career_brief: dict[str, Any]
    open_questions: list[str]
    search_strategy: dict[str, Any]
    approved_strategy: dict[str, Any]
    serpapi_results: list[dict[str, Any]]
    normalized_jobs: list[dict[str, Any]]
    deduped_jobs: list[dict[str, Any]]
    sponsorship_assessments: dict[str, dict[str, Any]]
    triage_decisions: list[dict[str, Any]]
    scored_jobs: list[dict[str, Any]]
    coach_summary: str
    user_feedback: list[dict[str, Any]]
    search_memory: dict[str, Any]
    query_diagnostics: list[dict[str, Any]]
    run_trace: list[dict[str, Any]]
    cache_run_path: str | None
    demo_mode: bool
    live_search_enabled: bool
    conversation_updated: bool
    interview_complete: bool
    errors: list[str]
