from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor, as_completed
from datetime import datetime, timezone
from pathlib import Path
from time import perf_counter
from typing import Any

from langgraph.graph import END, StateGraph

from .cache import save_graph_state
from .config import AppConfig
from .deduper import dedupe_jobs
from .job_normalizer import normalize_jobs
from .llm_client import LLMError, structured_response
from .memory import load_memory, save_memory, update_memory_from_feedback
from .schemas import (
    CandidateProfile,
    CareerBrief,
    ChatMessage,
    CoachTurn,
    DesiredSeniority,
    FeedbackRecord,
    GraphState,
    JobPosting,
    JobScore,
    QueryDiagnostic,
    QueryRepairDecision,
    RemotePreference,
    ReviewLabel,
    ScoredJob,
    ScoredJobList,
    SearchMemory,
    SearchQuery,
    SearchStrategyPlan,
    SearchStrategyType,
    SponsorshipRisk,
    SponsorshipTiming,
    UserPreferences,
)
from .serpapi_client import SerpApiError, load_sample_jobs, search_google_jobs, search_google_jobs_paginated
from .sponsorship import assess_sponsorship_deterministic
from .utils import normalize_text, split_csvish, truncate


SCORING_BATCH_SIZE = 5
SCORING_MAX_WORKERS = 5

PROFILE_PROMPT = """You are a pragmatic MBA career coach. Extract a structured candidate profile from the resume.
Ground claims in resume evidence. Return only valid JSON for the requested schema."""

REFINE_PROFILE_PROMPT = """You are the career coach updating a candidate profile after an interview turn.
Preserve resume-grounded facts, add interview-derived facts to interview_insights, and update target functions, strengths, gaps, and positioning notes where the user clarified goals or constraints.
Do not invent experience the user did not claim. Return JSON only."""

PREFERENCES_PROMPT = """Convert the resume and conversation into structured job-search preferences for an MBA career-search agent.
Use conservative defaults when the user has not answered a field. Return only valid JSON."""

CAREER_BRIEF_PROMPT = """You are the career coach agent. Create or update the user's career-search brief from resume evidence, chat, preferences, memory, and feedback.
This brief is the source of truth for search strategy, triage, scoring, and coaching. Be opinionated but evidence-grounded.
Set readiness='ready_to_search' only when role lanes, constraints, sponsorship stance, and target environment are clear enough to search.
If not ready, list only the highest-value unresolved questions. Return JSON only."""

STRATEGY_PROMPT = """Propose practical Google Jobs search lanes for an MBA or early-career candidate.
Use broad, job-title-like q values only. Do not use Boolean OR, long keyword strings, sponsorship terms, or city names in q.
Put geography only in the location field. Each location must be one valid Google Jobs location, such as "Austin, TX", "California, United States", or "United States".
Never combine multiple cities/states into one parenthetical location like "United States (California, Oregon, Seattle)".
Prefer retrieving a broader pool and letting ranking/scoring trim noise."""

SCORING_PROMPT = """Score each job against the candidate profile, career coach brief, and preferences using evidence from the resume, user conversation, and posting.
Be strict and use the full 0-5 range. Do not give 5s for title overlap alone.
Rubric:
- role_fit 5 only when title/responsibilities clearly match the coach target lane; 3 for adjacent; 1-2 for weak/title-only or wrong lane.
- skill_fit 5 only when the posting explicitly requires multiple candidate-specific skills/tools or product/AI evaluation evidence; 3 for partial overlap; 1-2 for generic product wording.
- experience_fit 5 only when seniority and scope fit the candidate; penalize senior/principal/director/head roles and pure internships.
- location_fit 5 only for preferred/remote-compatible locations; 3 for US-wide/unclear; lower for mismatches.
- industry_fit 5 only for target industries or AI/product environments; 3 for neutral; lower for unrelated/blocked industries.
- sponsorship_fit must be judged from the posting text. Use deterministic sponsorship hints only as hints; inspect the description yourself because sponsorship wording varies.
- sponsorship_risk must be Sponsor-Friendly only with explicit positive evidence, No Sponsorship for explicit blocker language, High Risk for citizenship/clearance or similar constraints, otherwise Unclear.
- sponsorship_evidence should quote or paraphrase the shortest relevant posting evidence, or say no explicit statement was found.
- role_summary, responsibilities, qualifications, and company_insights must be extracted only from the job posting text. Do not invent generic company facts or likely responsibilities. Leave fields empty when the posting does not say enough.
Return a score object for every job_id provided."""

COACH_TURN_PROMPT = """You are a pragmatic MBA career coach. Respond to the user's latest answer.
Be direct and useful, reflect what you learned, challenge weak constraints gently, and ask only the next high-signal questions.
Do not be generic. If the user has provided enough to search, set interview_complete=true, clear open_questions, and tell them to review the strategy/run search.
This product executes Google Jobs searches through SerpApi itself. Never ask the user what search tool they are using. Never ask them to reply "run" as the only way to execute search; the UI has a Run approved search button.
Keep the reply under 180 words."""

INITIAL_COACH_PROMPT = """You are a pragmatic MBA career coach reviewing a freshly parsed resume.
Start with a concise read on the candidate's strongest search narrative and ask only 2-3 high-signal questions needed before search.
Do not ask a generic checklist. Do not repeat every missing preference field. This product executes Google Jobs searches through SerpApi itself, so never ask which search tool the user is using. Return JSON only."""


def build_graph(config: AppConfig):
    graph = StateGraph(GraphState)
    graph.add_node("parse_resume", parse_resume)
    graph.add_node("extract_candidate_profile", lambda state: extract_candidate_profile(state, config))
    graph.add_node("coach_interview", lambda state: coach_interview(state, config))
    graph.add_node("refine_candidate_profile", lambda state: refine_candidate_profile(state, config))
    graph.add_node("update_preferences", lambda state: update_preferences(state, config))
    graph.add_node("update_career_brief", lambda state: update_career_brief(state, config))
    graph.add_node("propose_search_strategy", lambda state: propose_search_strategy(state, config))
    graph.add_node("strategy_review", strategy_review)
    graph.add_node("execute_search", lambda state: execute_search(state, config))
    graph.add_node("repair_queries", lambda state: repair_queries(state, config))
    graph.add_node("normalize_and_dedupe", normalize_and_dedupe)
    graph.add_node("assess_sponsorship", lambda state: assess_sponsorship(state, config))
    graph.add_node("score_jobs", lambda state: score_jobs(state, config))
    graph.add_node("coach_summary", coach_summary)
    graph.add_node("capture_feedback", capture_feedback)
    graph.add_node("update_search_memory", update_search_memory)

    graph.set_entry_point("parse_resume")
    graph.add_edge("parse_resume", "extract_candidate_profile")
    graph.add_edge("extract_candidate_profile", "coach_interview")
    graph.add_edge("coach_interview", "refine_candidate_profile")
    graph.add_edge("refine_candidate_profile", "update_preferences")
    graph.add_edge("update_preferences", "update_career_brief")
    graph.add_edge("update_career_brief", "propose_search_strategy")
    graph.add_edge("propose_search_strategy", "strategy_review")
    graph.add_conditional_edges(
        "strategy_review",
        _after_strategy_review,
        {"execute_search": "execute_search", "coach_summary": "coach_summary"},
    )
    graph.add_edge("execute_search", "repair_queries")
    graph.add_edge("repair_queries", "normalize_and_dedupe")
    graph.add_edge("normalize_and_dedupe", "assess_sponsorship")
    graph.add_edge("assess_sponsorship", "score_jobs")
    graph.add_edge("score_jobs", "coach_summary")
    graph.add_edge("coach_summary", "capture_feedback")
    graph.add_edge("capture_feedback", "update_search_memory")
    graph.add_edge("update_search_memory", END)
    return graph.compile()


def run_graph(state: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    compiled = build_graph(config)
    result = compiled.invoke(_default_state(state))
    return _save_result(result)


def run_resume_profile(state: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    """Run only resume parsing and candidate profile extraction."""
    result: GraphState = _default_state(state)
    for step in (
        parse_resume,
        lambda current: extract_candidate_profile(current, config),
    ):
        update = step(result)
        result.update(update)
    return _save_result(result)


def run_coach_brief(state: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    """Run preference/coach-brief generation without strategy or search."""
    result: GraphState = _default_state(state)
    result["force_career_brief"] = True
    for step in (
        parse_resume,
        lambda current: extract_candidate_profile(current, config),
        lambda current: coach_interview(current, config),
        lambda current: refine_candidate_profile(current, config),
        lambda current: update_preferences(current, config),
        lambda current: update_career_brief(current, config),
    ):
        update = step(result)
        result.update(update)
    result.pop("force_career_brief", None)
    result["conversation_updated"] = False
    return _save_result(result)


def run_search_strategy(state: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    """Run only strategy generation/review without search execution."""
    result: GraphState = _default_state(state)
    result["force_search_strategy"] = True
    for step in (
        parse_resume,
        lambda current: extract_candidate_profile(current, config),
        lambda current: update_preferences(current, config),
        lambda current: update_career_brief(current, config),
        lambda current: propose_search_strategy(current, config),
        strategy_review,
        coach_summary,
    ):
        update = step(result)
        result.update(update)
    result.pop("force_search_strategy", None)
    result["approved_strategy"] = {"approved": False, "edited_queries": []}
    result["conversation_updated"] = False
    return _save_result(result)


def run_approved_search(state: dict[str, Any], config: AppConfig) -> dict[str, Any]:
    """Run only the approved search and scoring path.

    This intentionally skips resume/profile/coaching/preference/strategy agents. The
    caller must pass an existing graph state with approved search queries.
    """
    result: GraphState = _default_state(state)
    result["run_trace"] = []
    overall_start = perf_counter()
    _append_trace(
        result,
        "approved_search.start",
        details={
            "max_searches_per_run": config.max_searches_per_run,
            "max_jobs_to_score": config.max_jobs_to_score,
            "demo_mode": bool(result.get("demo_mode")),
            "live_search_enabled": bool(result.get("live_search_enabled")),
        },
    )
    for name, step in (
        ("strategy_review", strategy_review),
        ("execute_search", lambda current: execute_search(current, config)),
        ("repair_queries", lambda current: repair_queries(current, config)),
        ("normalize_and_dedupe", normalize_and_dedupe),
        ("assess_sponsorship", lambda current: assess_sponsorship(current, config)),
        ("score_jobs", lambda current: score_jobs(current, config)),
        ("coach_summary", coach_summary),
    ):
        start = perf_counter()
        update = step(result)
        result.update(update)
        _append_trace(
            result,
            f"approved_search.step.{name}",
            duration_ms=_elapsed_ms(start),
            details={
                "serpapi_results": len(result.get("serpapi_results", [])),
                "deduped_jobs": len(result.get("deduped_jobs", [])),
                "scored_jobs": len(result.get("scored_jobs", [])),
                "errors": len(result.get("errors", [])),
            },
        )
    result["conversation_updated"] = False
    _append_trace(
        result,
        "approved_search.finish",
        duration_ms=_elapsed_ms(overall_start),
        details={
            "query_diagnostics": len(result.get("query_diagnostics", [])),
            "deduped_jobs": len(result.get("deduped_jobs", [])),
            "scored_jobs": len(result.get("scored_jobs", [])),
        },
    )
    return _save_result(result)


def parse_resume(state: GraphState) -> GraphState:
    resume_text = (state.get("resume_text") or "").strip()
    if not resume_text:
        return {"errors": [*state.get("errors", []), "Resume text is required."]}
    return {"resume_text": resume_text}


def extract_candidate_profile(state: GraphState, config: AppConfig) -> GraphState:
    if state.get("candidate_profile"):
        return {}
    resume_text = state.get("resume_text", "")
    if config.has_openai_key and not state.get("demo_mode"):
        try:
            profile = structured_response(
                config,
                CandidateProfile,
                PROFILE_PROMPT,
                f"Resume:\n{resume_text[:12000]}",
            )
            return {"candidate_profile": profile.model_dump(mode="json")}
        except LLMError as exc:
            errors = [*state.get("errors", []), f"Profile LLM fallback used: {exc}"]
            return {"candidate_profile": _heuristic_profile(resume_text).model_dump(mode="json"), "errors": errors}
    return {"candidate_profile": _heuristic_profile(resume_text).model_dump(mode="json")}


def coach_interview(state: GraphState, config: AppConfig) -> GraphState:
    messages = [ChatMessage.model_validate(item) for item in state.get("messages", [])]
    profile = CandidateProfile.model_validate(state.get("candidate_profile") or {})
    latest_user = _latest_user_message(messages)
    if latest_user and state.get("conversation_updated"):
        turn = _coach_reply(state, profile, latest_user)
        return {
            "open_questions": turn.open_questions,
            "interview_complete": turn.interview_complete,
            "messages": [*[message.model_dump() for message in messages], ChatMessage(role="assistant", content=turn.reply).model_dump()],
        }
    if state.get("open_questions") or state.get("interview_complete"):
        return {}
    turn = _initial_coach_turn(state, profile, config)
    assistant_message = ChatMessage(role="assistant", content=turn.reply)
    return {
        "open_questions": turn.open_questions,
        "interview_complete": turn.interview_complete,
        "messages": [* [message.model_dump() for message in messages], assistant_message.model_dump()],
    }


def refine_candidate_profile(state: GraphState, config: AppConfig) -> GraphState:
    if not state.get("conversation_updated"):
        return {}
    profile = CandidateProfile.model_validate(state.get("candidate_profile") or {})
    conversation = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in state.get("messages", []))
    if config.has_openai_key and not state.get("demo_mode"):
        try:
            refined = structured_response(
                config,
                CandidateProfile,
                REFINE_PROFILE_PROMPT,
                (
                    f"Resume text:\n{state.get('resume_text', '')[:9000]}\n\n"
                    f"Current profile:\n{profile.model_dump_json()}\n\n"
                    f"Conversation:\n{conversation[:6000]}"
                ),
            )
            return {"candidate_profile": refined.model_dump(mode="json")}
        except LLMError as exc:
            errors = [*state.get("errors", []), f"Profile refinement fallback used: {exc}"]
            return {"candidate_profile": _heuristic_refine_profile(profile, conversation).model_dump(mode="json"), "errors": errors}
    return {"candidate_profile": _heuristic_refine_profile(profile, conversation).model_dump(mode="json")}


def update_preferences(state: GraphState, config: AppConfig) -> GraphState:
    if state.get("inferred_preferences") and not state.get("conversation_updated"):
        prefs = UserPreferences.model_validate(state["inferred_preferences"])
        return {"inferred_preferences": _clamp_preferences(prefs, config).model_dump(mode="json")}

    resume_text = state.get("resume_text", "")
    conversation = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in state.get("messages", []))
    existing = state.get("inferred_preferences") or {}
    if config.has_openai_key and not state.get("demo_mode"):
        try:
            prefs = structured_response(
                config,
                UserPreferences,
                PREFERENCES_PROMPT,
                f"Existing preferences:\n{existing}\n\nResume:\n{resume_text[:8000]}\n\nConversation:\n{conversation[:4000]}",
            )
            return {"inferred_preferences": _clamp_preferences(prefs, config).model_dump(mode="json")}
        except LLMError as exc:
            errors = [*state.get("errors", []), f"Preference LLM fallback used: {exc}"]
            return {"inferred_preferences": _heuristic_preferences(resume_text, conversation, config).model_dump(mode="json"), "errors": errors}
    return {"inferred_preferences": _heuristic_preferences(resume_text, conversation, config).model_dump(mode="json")}


def update_career_brief(state: GraphState, config: AppConfig) -> GraphState:
    if state.get("career_brief") and not state.get("conversation_updated") and not state.get("user_feedback") and not state.get("force_career_brief"):
        brief = CareerBrief.model_validate(state["career_brief"])
        return {"interview_complete": brief.readiness == "ready_to_search", "open_questions": brief.unresolved_questions}

    profile = CandidateProfile.model_validate(state.get("candidate_profile") or {})
    prefs = UserPreferences.model_validate(state.get("inferred_preferences") or {})
    memory = SearchMemory.model_validate(state.get("search_memory") or load_memory().model_dump())
    conversation = "\n".join(f"{m.get('role')}: {m.get('content')}" for m in state.get("messages", []))
    existing = state.get("career_brief") or {}
    if config.has_openai_key and not state.get("demo_mode"):
        try:
            brief = structured_response(
                config,
                CareerBrief,
                CAREER_BRIEF_PROMPT,
                (
                    f"Existing brief:\n{existing}\n\n"
                    f"Candidate profile:\n{profile.model_dump_json()}\n\n"
                    f"Preferences:\n{prefs.model_dump_json()}\n\n"
                    f"Memory:\n{memory.model_dump_json()}\n\n"
                    f"Feedback:\n{state.get('user_feedback', [])}\n\n"
                    f"Conversation:\n{conversation[:6000]}"
                ),
            )
        except LLMError as exc:
            errors = [*state.get("errors", []), f"Career brief LLM fallback used: {exc}"]
            brief = _heuristic_career_brief(profile, prefs, conversation, memory)
            return {
                "career_brief": brief.model_dump(mode="json"),
                "interview_complete": brief.readiness == "ready_to_search",
                "open_questions": brief.unresolved_questions,
                "errors": errors,
            }
    else:
        brief = _heuristic_career_brief(profile, prefs, conversation, memory)
    return {
        "career_brief": brief.model_dump(mode="json"),
        "interview_complete": brief.readiness == "ready_to_search",
        "open_questions": brief.unresolved_questions,
    }


def propose_search_strategy(state: GraphState, config: AppConfig) -> GraphState:
    if state.get("search_strategy") and not state.get("conversation_updated") and not state.get("force_search_strategy"):
        return {}
    profile = CandidateProfile.model_validate(state.get("candidate_profile") or {})
    prefs = UserPreferences.model_validate(state.get("inferred_preferences") or {})
    brief = CareerBrief.model_validate(state.get("career_brief") or {})
    memory = SearchMemory.model_validate(state.get("search_memory") or load_memory().model_dump())

    if config.has_openai_key and not state.get("demo_mode"):
        try:
            strategy = structured_response(
                config,
                SearchStrategyPlan,
                STRATEGY_PROMPT,
                f"Profile:\n{profile.model_dump_json()}\n\nCareer brief:\n{brief.model_dump_json()}\n\nPreferences:\n{prefs.model_dump_json()}\n\nMemory:\n{memory.model_dump_json()}",
            )
            strategy.queries = _sanitize_strategy_queries(strategy.queries, prefs)[: prefs.max_searches]
            return {"search_strategy": strategy.model_dump(mode="json")}
        except LLMError as exc:
            errors = [*state.get("errors", []), f"Strategy LLM fallback used: {exc}"]
            return {"search_strategy": _heuristic_strategy(profile, prefs, memory, brief).model_dump(mode="json"), "errors": errors}
    strategy = _heuristic_strategy(profile, prefs, memory, brief)
    strategy.queries = _sanitize_strategy_queries(strategy.queries, prefs)
    return {"search_strategy": strategy.model_dump(mode="json")}


def strategy_review(state: GraphState) -> GraphState:
    approval = state.get("approved_strategy") or {}
    if approval.get("approved") and not approval.get("edited_queries"):
        approval["edited_queries"] = state.get("search_strategy", {}).get("queries", [])
    return {"approved_strategy": approval}


def execute_search(state: GraphState, config: AppConfig) -> GraphState:
    approved = state.get("approved_strategy") or {}
    if not approved.get("approved"):
        return {}
    queries = [SearchQuery.model_validate(item) for item in approved.get("edited_queries") or state.get("search_strategy", {}).get("queries", [])]
    prefs = UserPreferences.model_validate(state.get("inferred_preferences") or {})
    queries = _sanitize_strategy_queries(queries, prefs)[: min(config.max_searches_per_run, prefs.max_searches)]
    target_results = max(1, config.max_jobs_to_score)
    per_query_target = max(10, min(30, (target_results // max(1, len(queries))) + 10))
    _append_trace(
        state,
        "search.config",
        details={
            "queries": len(queries),
            "target_results": target_results,
            "per_query_target": per_query_target,
            "live": bool(state.get("live_search_enabled") and config.has_serpapi_key and not state.get("demo_mode")),
        },
    )

    if state.get("demo_mode") or not state.get("live_search_enabled") or not config.has_serpapi_key:
        start = perf_counter()
        rows = load_sample_jobs()
        diagnostics = [
            QueryDiagnostic(query=query.query, location=query.location, result_count=sum(1 for q, _ in rows if q.query == query.query)).model_dump()
            for query in queries
        ]
        _append_trace(
            state,
            "search.sample_jobs",
            duration_ms=_elapsed_ms(start),
            details={"rows": len(rows), "diagnostics": len(diagnostics)},
        )
        return {"serpapi_results": _serialize_rows(rows), "query_diagnostics": diagnostics}

    serialized = []
    diagnostics = []
    errors = list(state.get("errors", []))
    for index, query in enumerate(queries, start=1):
        query_start = perf_counter()
        try:
            results = search_google_jobs_paginated(
                query,
                config,
                max_results=per_query_target,
                max_pages=3,
                trace_callback=lambda event, duration_ms, details: _append_trace(
                    state,
                    event,
                    duration_ms=duration_ms,
                    details=details,
                ),
            )
        except SerpApiError as exc:
            diagnostics.append(QueryDiagnostic(query=query.query, location=query.location, error=str(exc)).model_dump())
            errors.append(f"SerpApi query failed for '{query.query}': {exc}")
            _append_trace(
                state,
                "search.serpapi_query",
                duration_ms=_elapsed_ms(query_start),
                details={
                    "index": index,
                    "query": query.query,
                    "location": query.location,
                    "error": str(exc),
                    "serialized_so_far": len(serialized),
                },
            )
            continue
        diagnostics.append(QueryDiagnostic(query=query.query, location=query.location, result_count=len(results)).model_dump())
        serialized.extend({"query": query.model_dump(mode="json"), "raw": raw} for raw in results)
        _append_trace(
            state,
            "search.serpapi_query",
            duration_ms=_elapsed_ms(query_start),
            details={
                "index": index,
                "query": query.query,
                "location": query.location,
                "result_count": len(results),
                "serialized_so_far": len(serialized),
            },
        )
        if len(serialized) >= target_results:
            break
    return {"serpapi_results": serialized, "query_diagnostics": diagnostics, "errors": errors}


def repair_queries(state: GraphState, config: AppConfig) -> GraphState:
    approved = state.get("approved_strategy") or {}
    if not approved.get("approved") or state.get("demo_mode") or not state.get("live_search_enabled") or not config.has_serpapi_key:
        return {}
    diagnostics = [QueryDiagnostic.model_validate(item) for item in state.get("query_diagnostics", [])]
    attempted = {item.query for item in diagnostics}
    remaining_budget = config.max_searches_per_run - len(attempted)
    if remaining_budget <= 0:
        return {}

    profile = CandidateProfile.model_validate(state.get("candidate_profile") or {})
    prefs = UserPreferences.model_validate(state.get("inferred_preferences") or {})
    rows = list(state.get("serpapi_results", []))
    new_diagnostics = list(state.get("query_diagnostics", []))
    errors = list(state.get("errors", []))

    for diagnostic in diagnostics:
        if remaining_budget <= 0 or diagnostic.result_count > 0 or diagnostic.error:
            continue
        repair = _repair_query(diagnostic, profile, prefs)
        if not repair.should_retry or not repair.replacement_query:
            continue
        query = SearchQuery(
            query=repair.replacement_query,
            location=repair.replacement_location,
            rationale=repair.repair_reason,
            expected_tradeoff=repair.expected_improvement,
            job_family=diagnostic.query,
            strategy_type=SearchStrategyType.broadened_repair,
            confidence=0.5,
        )
        try:
            results = search_google_jobs(query, config)
        except SerpApiError as exc:
            errors.append(f"SerpApi repair failed for '{query.query}': {exc}")
            new_diagnostics.append(QueryDiagnostic(query=query.query, location=query.location, repaired=True, repair_rationale=repair.repair_reason, error=str(exc)).model_dump())
            remaining_budget -= 1
            continue
        rows.extend({"query": query.model_dump(mode="json"), "raw": raw} for raw in results)
        new_diagnostics.append(
            QueryDiagnostic(
                query=query.query,
                location=query.location,
                result_count=len(results),
                repaired=True,
                repair_rationale=repair.repair_reason,
            ).model_dump()
        )
        remaining_budget -= 1
    return {"serpapi_results": rows, "query_diagnostics": new_diagnostics, "errors": errors}


def normalize_and_dedupe(state: GraphState) -> GraphState:
    rows = _deserialize_rows(state.get("serpapi_results", []))
    normalized = normalize_jobs(rows)
    deduped = dedupe_jobs(normalized)
    return {
        "normalized_jobs": [job.model_dump(mode="json") for job in normalized],
        "deduped_jobs": [job.model_dump(mode="json") for job in deduped],
    }


def assess_sponsorship(state: GraphState, config: AppConfig) -> GraphState:
    jobs = [JobPosting.model_validate(item) for item in state.get("deduped_jobs", [])]
    assessments = {job.job_id: assess_sponsorship_deterministic(job) for job in jobs}
    return {"sponsorship_assessments": {key: value.model_dump(mode="json") for key, value in assessments.items()}}


def score_jobs(state: GraphState, config: AppConfig) -> GraphState:
    selection_start = perf_counter()
    jobs = [JobPosting.model_validate(item) for item in state.get("deduped_jobs", [])]
    ranked_jobs = sorted(jobs, key=lambda job: _job_keyword_score(job, state), reverse=True)
    jobs_to_score = ranked_jobs[: config.max_jobs_to_score]
    assessments = state.get("sponsorship_assessments", {})
    scores: dict[str, JobScore] = {}
    errors = list(state.get("errors", []))
    _append_trace(
        state,
        "scoring.selection",
        duration_ms=_elapsed_ms(selection_start),
        details={
            "deduped_jobs": len(jobs),
            "jobs_to_score": len(jobs_to_score),
            "max_jobs_to_score": config.max_jobs_to_score,
            "batch_size": SCORING_BATCH_SIZE,
        },
    )

    if not jobs_to_score:
        return {"scored_jobs": []}
    if not config.has_openai_key or state.get("demo_mode"):
        errors.append("LLM scoring was not run because OpenAI is unavailable or demo mode is enabled. No heuristic scores were generated.")
        return {"scored_jobs": [], "errors": errors}

    scores, scoring_errors = _score_jobs_with_llm_batches(state, config, jobs_to_score, assessments)
    errors.extend(scoring_errors)
    if not scores:
        errors.append("LLM scoring returned no valid scores. No heuristic scores were generated.")
        return {"scored_jobs": [], "errors": errors}

    missing_ids = [job.job_id for job in jobs_to_score if job.job_id not in scores]
    if missing_ids:
        errors.append(f"LLM scoring omitted {len(missing_ids)} job(s): {', '.join(missing_ids[:5])}. No heuristic scores were generated for omitted jobs.")

    scored = []
    for job in jobs_to_score:
        score = scores.get(job.job_id)
        if score is None:
            continue
        assessment = assessments.get(job.job_id, {})
        sponsorship_risk = score.sponsorship_risk or assessment.get("sponsorship_risk", SponsorshipRisk.unclear)
        sponsorship_evidence = score.sponsorship_evidence or assessment.get("evidence", "")
        sponsorship_summary = score.sponsorship_reasoning_summary or assessment.get("reasoning_summary", "")
        overall = round(
            ((score.role_fit + score.skill_fit + score.experience_fit + score.location_fit + score.industry_fit + score.sponsorship_fit) / 30) * 100
        )
        scored.append(
            ScoredJob(
                rank=0,
                job_id=job.job_id,
                company=job.company,
                title=job.title,
                location=job.location,
                overall_fit_score=overall,
                role_fit=score.role_fit,
                skill_fit=score.skill_fit,
                experience_fit=score.experience_fit,
                location_fit=score.location_fit,
                industry_fit=score.industry_fit,
                sponsorship_fit=score.sponsorship_fit,
                sponsorship_risk=sponsorship_risk,
                sponsorship_evidence=sponsorship_evidence,
                sponsorship_reasoning_summary=sponsorship_summary,
                key_matches=score.key_matches,
                key_gaps=score.key_gaps,
                recommended_action=score.recommended_action,
                explanation=score.explanation,
                job_description=job.description,
                role_summary=score.role_summary,
                responsibilities=score.responsibilities,
                qualifications=score.qualifications,
                company_insights=score.company_insights,
                source=job.source,
                date_posted=job.date_posted,
                url=job.url,
                search_query=job.search_query,
            )
        )
    scored.sort(key=lambda item: item.overall_fit_score, reverse=True)
    for index, item in enumerate(scored, start=1):
        item.rank = index
    return {"scored_jobs": [item.model_dump(mode="json") for item in scored]}


def _score_jobs_with_llm_batches(
    state: GraphState,
    config: AppConfig,
    jobs: list[JobPosting],
    assessments: dict[str, dict[str, Any]],
) -> tuple[dict[str, JobScore], list[str]]:
    scores: dict[str, JobScore] = {}
    errors: list[str] = []
    scoring_jobs = [(job, f"job_{index:03d}") for index, job in enumerate(jobs, start=1)]
    batches = [
        scoring_jobs[start : start + SCORING_BATCH_SIZE]
        for start in range(0, len(scoring_jobs), SCORING_BATCH_SIZE)
    ]
    max_workers = min(SCORING_MAX_WORKERS, len(batches)) or 1

    with ThreadPoolExecutor(max_workers=max_workers) as executor:
        futures = {}
        for batch_index, batch in enumerate(batches, start=1):
            _append_trace(
                state,
                "scoring.batch.start",
                details={
                    "batch_index": batch_index,
                    "batch_size": len(batch),
                    "job_ids": [scoring_id for _, scoring_id in batch],
                    "worker_count": max_workers,
                },
            )
            future = executor.submit(_score_job_batch, state, config, batch, assessments, SCORING_BATCH_SIZE)
            futures[future] = batch_index

        for future in as_completed(futures):
            batch_scores, batch_errors = future.result()
            scores.update(batch_scores)
            errors.extend(batch_errors)
    return scores, errors


def _score_job_batch(
    state: GraphState,
    config: AppConfig,
    jobs: list[tuple[JobPosting, str]],
    assessments: dict[str, dict[str, Any]],
    batch_size: int,
) -> tuple[dict[str, JobScore], list[str]]:
    if not jobs:
        return {}, []
    batch_payload = [_scoring_job_payload(job, scoring_id) for job, scoring_id in jobs]
    batch_assessments = {scoring_id: assessments.get(job.job_id, {}) for job, scoring_id in jobs}
    scoring_to_original = {scoring_id: job.job_id for job, scoring_id in jobs}
    prompt_text = (
        f"Profile:\n{_compact_candidate_profile(state.get('candidate_profile') or {})}\n"
        f"Career brief:\n{state.get('career_brief')}\n"
        f"Preferences:\n{state.get('inferred_preferences')}\n"
        f"Sponsorship:\n{batch_assessments}\n"
        f"Jobs:\n{batch_payload}"
    )
    llm_start = perf_counter()
    try:
        response = structured_response(
            config,
            ScoredJobList,
            SCORING_PROMPT,
            prompt_text,
        )
    except LLMError as exc:
        _append_trace(
            state,
            "scoring.llm_batch.error",
            duration_ms=_elapsed_ms(llm_start),
            details={
                "batch_size": len(jobs),
                "job_ids": [scoring_id for _, scoring_id in jobs],
                "prompt_chars": len(prompt_text),
                "error": str(exc),
            },
        )
        if len(jobs) > 1:
            midpoint = max(1, len(jobs) // 2)
            left_scores, left_errors = _score_job_batch(state, config, jobs[:midpoint], assessments, batch_size=midpoint)
            right_scores, right_errors = _score_job_batch(state, config, jobs[midpoint:], assessments, batch_size=len(jobs) - midpoint)
            merged = {**left_scores, **right_scores}
            return merged, [*left_errors, *right_errors]
        job, _ = jobs[0]
        return {}, [f"LLM scoring failed for {job.company} | {job.title}. No heuristic score was generated: {exc}"]

    scores_by_scoring_id = {score.job_id: score for score in response.jobs}
    missing_ids = [scoring_id for _, scoring_id in jobs if scoring_id not in scores_by_scoring_id]
    _append_trace(
        state,
        "scoring.llm_batch.finish",
        duration_ms=_elapsed_ms(llm_start),
        details={
            "batch_size": len(jobs),
            "job_ids": [scoring_id for _, scoring_id in jobs],
            "prompt_chars": len(prompt_text),
            "scores_returned": len(scores_by_scoring_id),
            "missing_ids": missing_ids,
        },
    )
    scores: dict[str, JobScore] = {}
    for scoring_id, score in scores_by_scoring_id.items():
        original_id = scoring_to_original.get(scoring_id)
        if not original_id:
            continue
        scores[original_id] = score.model_copy(update={"job_id": original_id})

    errors = []
    if missing_ids:
        missing_set = set(missing_ids)
        labels = ", ".join(_job_label(job) for job, scoring_id in jobs if scoring_id in missing_set)
        errors.append(f"LLM scoring omitted {len(missing_ids)} job(s) in a {batch_size}-job batch: {labels}. No heuristic scores were generated for omitted jobs.")
    return scores, errors


def _scoring_job_payload(job: JobPosting, scoring_id: str) -> dict[str, Any]:
    return {
        "job_id": scoring_id,
        "title": job.title,
        "company": job.company,
        "location": job.location,
        "description": job.description or "",
    }


def _compact_candidate_profile(profile: dict[str, Any]) -> dict[str, Any]:
    return {
        "name": profile.get("name"),
        "experience_summary": truncate(profile.get("experience_summary", ""), 1000),
        "strengths_for_search": profile.get("strengths_for_search", [])[:10],
        "target_functions": profile.get("target_functions", [])[:10],
        "potential_gaps": profile.get("potential_gaps", [])[:8],
        "interview_insights": profile.get("interview_insights", [])[:12],
        "positioning_notes": profile.get("positioning_notes", [])[:12],
    }


def _job_label(job: JobPosting) -> str:
    return f"{job.company} | {job.title}"


def coach_summary(state: GraphState) -> GraphState:
    scored = [ScoredJob.model_validate(item) for item in state.get("scored_jobs", [])]
    brief = CareerBrief.model_validate(state.get("career_brief") or {})
    if not scored and not (state.get("approved_strategy") or {}).get("approved"):
        if brief.readiness != "ready_to_search":
            return {"coach_summary": "The coach brief still has unresolved questions. Answer them or run search with the current assumptions."}
        return {"coach_summary": _format_pending_summary(brief)}
    if not scored:
        return {"coach_summary": "No jobs were scored. Broaden the strategy or switch to demo/replay mode if API keys are unavailable."}
    top = scored[:3]
    sponsor_counts: dict[str, int] = {}
    for job in scored:
        sponsor_counts[job.sponsorship_risk.value] = sponsor_counts.get(job.sponsorship_risk.value, 0) + 1
    return {"coach_summary": _format_results_summary(brief, top, sponsor_counts)}


def capture_feedback(state: GraphState) -> GraphState:
    scored_by_id = {item["job_id"]: item for item in state.get("scored_jobs", [])}
    merged = []
    for feedback in state.get("user_feedback", []):
        item = dict(feedback)
        job = scored_by_id.get(item.get("job_id"), {})
        item.setdefault("company", job.get("company", ""))
        item.setdefault("query", job.get("search_query", ""))
        item.setdefault("role_family", _infer_role_family(job.get("title", "")))
        merged.append(item)
    return {"user_feedback": merged}


def update_search_memory(state: GraphState) -> GraphState:
    memory = SearchMemory.model_validate(state.get("search_memory") or load_memory().model_dump())
    feedback = [FeedbackRecord.model_validate(item) for item in state.get("user_feedback", [])]
    updated = update_memory_from_feedback(memory, feedback)
    if feedback:
        save_memory(updated)
    return {"search_memory": updated.model_dump(mode="json"), "conversation_updated": False}


def _after_strategy_review(state: GraphState) -> str:
    approved = state.get("approved_strategy") or {}
    return "execute_search" if approved.get("approved") else "coach_summary"


def _format_pending_summary(brief: CareerBrief) -> str:
    return "\n".join(
        [
            "### Coach Thesis",
            brief.search_thesis or brief.positioning or "Review and approve the proposed search strategy before running search.",
            "",
            "### Search Assumptions",
            f"- Target lanes: {', '.join(brief.target_role_lanes) or 'Not set'}",
            f"- Adjacent lanes: {', '.join(brief.adjacent_role_lanes) or 'Not set'}",
            f"- Excluded lanes: {', '.join(brief.excluded_lanes) or 'None'}",
            f"- Sponsorship: {brief.sponsorship_stance or 'Not set'}",
            "",
            "### Next Step",
            "Review the Strategy tab, edit obvious misses, then use **Run approved search**.",
        ]
    )


def _format_results_summary(brief: CareerBrief, top: list[ScoredJob], sponsor_counts: dict[str, int]) -> str:
    top_lines = [f"- **{job.company}** — {job.title} ({job.location}), score {job.overall_fit_score}" for job in top]
    sponsor_lines = [f"- {label}: {count}" for label, count in sponsor_counts.items()]
    lane_lines = sorted({job.search_query for job in top if job.search_query})[:4]
    return "\n".join(
        [
            "### Coach Thesis",
            brief.search_thesis or brief.positioning or "Search completed against the current coach brief.",
            "",
            "### Apply First",
            *(top_lines or ["- No scored jobs available."]),
            "",
            "### Strongest Search Lanes",
            *(f"- {lane}" for lane in lane_lines),
            "",
            "### Sponsorship Pattern",
            *(sponsor_lines or ["- No sponsorship assessments available."]),
            "",
            "### Next Step",
            "Start with high-fit roles that are sponsor-friendly or unclear-but-plausible. Use feedback labels to teach the next search what to prioritize or avoid.",
        ]
    )


def _latest_user_message(messages: list[ChatMessage]) -> str:
    for message in reversed(messages):
        if message.role == "user":
            return message.content
    return ""


def _initial_coach_turn(state: GraphState, profile: CandidateProfile, config: AppConfig) -> CoachTurn:
    if config.has_openai_key and not state.get("demo_mode"):
        try:
            return structured_response(
                config,
                CoachTurn,
                INITIAL_COACH_PROMPT,
                f"Resume text:\n{state.get('resume_text', '')[:9000]}\n\nCandidate profile:\n{profile.model_dump_json()}",
            )
        except LLMError:
            pass
    return _heuristic_initial_coach_turn(profile, state.get("resume_text", ""))


def _coach_reply(state: GraphState, profile: CandidateProfile, latest_user: str) -> CoachTurn:
    if state.get("demo_mode") or not latest_user:
        return _heuristic_coach_reply(profile, latest_user)
    # Keep this structured so the app can reliably update the open-question list.
    try:
        from .config import load_config

        config = load_config()
        if config.has_openai_key:
            return structured_response(
                config,
                CoachTurn,
                COACH_TURN_PROMPT,
                f"Candidate profile:\n{profile.model_dump_json()}\n\nCurrent state:\n{state}\n\nLatest user answer:\n{latest_user}",
            )
    except Exception:
        pass
    return _heuristic_coach_reply(profile, latest_user)


def _heuristic_initial_coach_turn(profile: CandidateProfile, resume_text: str) -> CoachTurn:
    combined = normalize_text(" ".join([resume_text, profile.experience_summary, " ".join(profile.target_functions)]))
    role_signal = "product/strategy/analytics"
    if "ai" in combined and "product" in combined:
        role_signal = "AI product, product analytics, and product strategy"
    elif "operation" in combined and "analytics" in combined:
        role_signal = "operations analytics, business operations, and strategy"
    elif "product" in combined:
        role_signal = "product management and product strategy"

    questions = [
        "Which role family should be the lead lane: AI product, product analytics, strategy/ops, or something else?",
        "Which locations should I search first, and are remote roles acceptable?",
    ]
    if "international" in combined or "sponsor" in combined or "visa" in combined:
        questions.append("Should I treat sponsorship as needed immediately or future-risk only?")
    else:
        questions.append("Do you need sponsorship now, in the future, or not at all?")

    reply = (
        f"Your resume reads strongest for {role_signal}, not a generic MBA search. "
        "Before I search, I want to calibrate the lane and constraints so I do not overfit to the wrong titles. "
        + " ".join(questions[:3])
    )
    return CoachTurn(reply=reply, open_questions=questions[:3], interview_complete=False)


def _heuristic_coach_reply(profile: CandidateProfile, latest_user: str) -> CoachTurn:
    text = latest_user.lower()
    complete = _user_signaled_enough(text) or _has_enough_interview_signal(text)
    open_questions = []
    if not complete and not any(location in text for location in ["los angeles", "san francisco", "seattle", "new york", "remote", "hybrid", "onsite", "on-site", "anywhere", "us", "u.s."]):
        open_questions.append("Which locations should I treat as realistic, and are remote or hybrid roles acceptable?")
    if not complete and "sponsor" not in text and "international" not in text:
        open_questions.append("Should I screen as if sponsorship is needed now, in the future, or not at all?")
    if not complete and not any(term in text for term in ["senior", "manager", "associate", "entry", "post-mba", "mba"]):
        open_questions.append("Should I avoid senior roles unless they are clearly post-MBA appropriate?")

    if "ai" in text and "product" in text:
        reply = (
            "I think your instinct is directionally right: AI product roles are the cleanest narrative, but I would not make PM title the only path. "
            "Your stronger search lanes should be AI Product Manager, Product Strategy, Product Analytics, and AI Solutions/Strategy roles. "
            "I will exclude workforce/dispatch optimization and keep product analytics as an acceptable adjacent lane. "
        )
    else:
        reply = (
            "That helps. I will translate this into search lanes that preserve your stated goal while keeping adjacent roles available where they improve fit. "
        )
    if "international" in text or "sponsor" in text:
        reply += "Because sponsorship matters, I will treat explicit no-sponsorship language as a blocker and avoid claiming sponsor-friendliness unless the posting says so. "
    if complete:
        reply += "That is enough to move from interview to search. I’ll treat this as ready: review the strategy lanes, edit any obvious misses, then run the approved search."
        open_questions = []
    elif open_questions:
        reply += "The remaining thing I need is: " + " ".join(open_questions[:2])
    else:
        reply += "I have enough to revise the preference state and search strategy. Review the lanes and run search when ready."
        complete = True
    return CoachTurn(reply=reply.strip(), open_questions=open_questions[:2], interview_complete=complete)


def _user_signaled_enough(text: str) -> bool:
    signals = [
        "good enough",
        "enough",
        "let me know if you need more",
        "let me know if these are good",
        "run search",
        "start search",
        "search now",
    ]
    return any(signal in text for signal in signals)


def _has_enough_interview_signal(text: str) -> bool:
    has_role = any(term in text for term in ["ai product", "product strategy", "analytics strategy", "strategy", "product", "ai-related", "ai related"])
    has_company_or_industry = any(term in text for term in ["tech", "startup", "series", "company", "companies", "industry"])
    has_sponsorship = any(term in text for term in ["sponsor", "international", "h1b", "visa", "work authorization"])
    return has_role and (has_company_or_industry or has_sponsorship)


def _default_state(state: dict[str, Any]) -> dict[str, Any]:
    default = {
        "resume_text": "",
        "messages": [],
        "open_questions": [],
        "serpapi_results": [],
        "normalized_jobs": [],
        "deduped_jobs": [],
        "sponsorship_assessments": {},
        "triage_decisions": [],
        "scored_jobs": [],
        "user_feedback": [],
        "query_diagnostics": [],
        "run_trace": [],
        "search_memory": load_memory().model_dump(mode="json"),
        "career_brief": {},
        "demo_mode": False,
        "live_search_enabled": True,
        "conversation_updated": False,
        "interview_complete": False,
        "errors": [],
    }
    default.update(state)
    if not default.get("cache_run_path"):
        default["cache_run_path"] = None
    return default


def _save_result(result: GraphState) -> dict[str, Any]:
    run_path = save_graph_state(result, result.get("cache_run_path"))
    result["cache_run_path"] = str(run_path)
    return result


def _elapsed_ms(start: float) -> int:
    return round((perf_counter() - start) * 1000)


def _append_trace(
    state: GraphState,
    event: str,
    duration_ms: int | None = None,
    details: dict[str, Any] | None = None,
) -> None:
    trace = state.setdefault("run_trace", [])
    item = {
        "time": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "event": event,
        "duration_ms": duration_ms,
        "details": details or {},
    }
    trace.append(item)
    print(f"[career-search-trace] {event} duration_ms={duration_ms} details={item['details']}", flush=True)


def _heuristic_profile(resume_text: str) -> CandidateProfile:
    lower = resume_text.lower()
    target_functions = []
    for label in ["product management", "product strategy", "product operations", "business operations", "analytics", "ai solutions"]:
        if label in lower or any(part in lower for part in label.split()):
            target_functions.append(label)
    skills = [skill for skill in ["SQL", "Python", "Tableau", "Excel", "analytics", "stakeholder management", "AI products"] if skill.lower() in lower]
    education = [line for line in resume_text.splitlines() if "mba" in line.lower() or "university" in line.lower() or "school" in line.lower()][:3]
    return CandidateProfile(
        name=resume_text.splitlines()[0].strip() if resume_text.splitlines() else None,
        education=education,
        current_status="MBA candidate or early-career professional" if "mba" in lower else "Career search candidate",
        target_functions=target_functions or ["product strategy", "business operations", "analytics"],
        skills=skills,
        tools=[tool for tool in ["SQL", "Python", "Tableau", "Excel"] if tool.lower() in lower],
        industries=["technology", "AI", "SaaS"] if "ai" in lower or "product" in lower else [],
        experience_summary="Candidate has experience across product, analytics, operations, and cross-functional execution.",
        seniority_level="post-MBA / early career",
        notable_achievements=[line.strip("- ") for line in resume_text.splitlines() if line.strip().startswith("-")][:4],
        strengths_for_search=["Cross-functional execution", "Analytical toolkit", "Product-adjacent experience"],
        potential_gaps=["May need role calibration between PM, strategy, operations, and solutions roles"],
        evidence_notes=["Extracted from resume keywords and bullet content."],
    )


def _heuristic_refine_profile(profile: CandidateProfile, conversation: str) -> CandidateProfile:
    text = conversation.lower()
    target_functions = list(profile.target_functions)
    strengths = list(profile.strengths_for_search)
    gaps = list(profile.potential_gaps)
    insights = list(profile.interview_insights)
    positioning = list(profile.positioning_notes)

    def add_unique(values: list[str], item: str) -> None:
        if item and item not in values:
            values.append(item)

    if "ai" in text:
        add_unique(target_functions, "AI product strategy")
        add_unique(target_functions, "AI strategy")
        add_unique(strengths, "Explicit interest in creating business value from AI")
        add_unique(insights, "User wants an AI-related role and values hands-on AI value creation.")
        add_unique(positioning, "Position as AI product/strategy or AI-enabled decision support rather than generic PM.")
    if "product analytics" in text or "analytics strategy" in text:
        add_unique(target_functions, "product analytics")
        add_unique(strengths, "Comfort with analytics-led product and strategy roles")
        add_unique(insights, "User is open to product analytics as an adjacent lane.")
    if "not necessarily need a product role" in text or "doesn't really have to be product" in text:
        add_unique(target_functions, "AI strategy")
        add_unique(insights, "User does not require a PM title if the role is strongly AI-related.")
    if "series b" in text or "startup" in text:
        add_unique(insights, "User is open to startups, preferably Series B onward.")
    if "sponsor" in text or "international" in text:
        add_unique(insights, "User needs sponsorship-aware screening.")
    if "haven't built anything ai-specific" in text or "not ai-related" in text:
        add_unique(gaps, "AI-specific shipped product evidence may be weaker than analytics/product strategy evidence.")
        add_unique(positioning, "Avoid overstating shipped AI ownership; emphasize AI readiness, metrics, data quality, evaluation, and decision-support artifacts.")
    if "workforce" in text or "dispatch" in text:
        add_unique(gaps, "Avoid roles framed primarily around workforce, dispatch, routing, or logistics optimization unless the AI/product angle is clear.")
        add_unique(insights, "User wants to avoid workforce/dispatch optimization.")

    return profile.model_copy(
        update={
            "target_functions": target_functions,
            "strengths_for_search": strengths,
            "potential_gaps": gaps,
            "interview_insights": insights,
            "positioning_notes": positioning,
        }
    )


def _heuristic_preferences(resume_text: str, conversation: str, config: AppConfig) -> UserPreferences:
    combined = f"{resume_text}\n{conversation}".lower()
    requires_sponsorship = not any(term in combined for term in ["citizen", "green card", "do not need sponsorship", "no sponsorship needed"])
    locations = []
    for location in ["Los Angeles", "San Francisco", "Seattle", "New York", "Boston", "Chicago", "Remote"]:
        if location.lower() in combined:
            locations.append(location)
    avoid_roles = []
    if "workforce" in combined or "dispatch" in combined:
        avoid_roles.append("workforce and dispatch optimization")
    wants_ai = " ai " in f" {combined} " or "artificial intelligence" in combined
    product_path = "product" in combined
    analytics_ok = "product analytics" in combined or "analytics are fine" in combined
    target_titles = ["AI Product Manager", "Product Manager", "Product Strategy Manager"] if wants_ai and product_path else ["Product Manager", "Product Strategy Manager", "Business Operations Manager"]
    adjacent_roles = ["Product Analytics", "AI Solutions Consultant", "AI Strategy and Operations"]
    if not analytics_ok:
        adjacent_roles.append("Product Operations")
    return UserPreferences(
        primary_goal="Find AI-focused roles, with product as the preferred path and sponsorship risk screened conservatively." if wants_ai else "Find high-fit post-MBA technology-adjacent roles with sponsorship-aware screening.",
        target_job_titles=target_titles,
        acceptable_adjacent_roles=adjacent_roles,
        role_families_to_avoid=avoid_roles,
        preferred_locations=locations or ["Los Angeles", "San Francisco", "Seattle", "New York", "Remote"],
        remote_preference=RemotePreference.remote if "remote only" in combined else RemotePreference.any,
        target_industries=["technology", "AI", "SaaS", "marketplaces"],
        work_authorization_status="Requires sponsorship or future sponsorship" if requires_sponsorship else "No sponsorship needed",
        requires_sponsorship=requires_sponsorship,
        sponsorship_timing=SponsorshipTiming.future if requires_sponsorship else SponsorshipTiming.not_needed,
        desired_seniority=DesiredSeniority.post_mba,
        optimization_priority="balanced fit with sponsorship risk awareness",
        max_searches=config.max_searches_per_run,
    )


def _heuristic_career_brief(
    profile: CandidateProfile,
    prefs: UserPreferences,
    conversation: str,
    memory: SearchMemory,
) -> CareerBrief:
    combined = normalize_text(" ".join([conversation, profile.experience_summary, prefs.primary_goal]))
    target_lanes = prefs.target_job_titles or profile.target_functions or ["product strategy"]
    adjacent_lanes = prefs.acceptable_adjacent_roles or ["product analytics", "AI solutions", "strategy and operations"]
    excluded = list(dict.fromkeys(prefs.role_families_to_avoid + memory.rejected_role_families))
    if "workforce" in combined or "dispatch" in combined:
        excluded.append("workforce/dispatch optimization")
    user_evidence = []
    if "ai" in combined:
        user_evidence.append("User is explicitly interested in AI-related roles.")
    if "series b" in combined or "startup" in combined:
        user_evidence.append("User is open to startups, preferably Series B onward.")
    if "sponsor" in combined or "international" in combined:
        user_evidence.append("User needs sponsorship-aware screening.")
    unresolved = []
    if not target_lanes:
        unresolved.append("Choose a lead role lane.")
    if not prefs.preferred_locations:
        unresolved.append("Clarify location scope.")
    if not prefs.work_authorization_status and prefs.sponsorship_timing == SponsorshipTiming.unknown:
        unresolved.append("Clarify sponsorship timing.")
    readiness = "ready_to_search" if len(unresolved) == 0 and (target_lanes or adjacent_lanes) else "needs_more_info"
    if "let me know if you need more" in combined or "good enough" in combined:
        readiness = "ready_to_search"
        unresolved = []
    positioning = (
        "AI product/strategy and product analytics for AI-enabled decision support"
        if "ai" in combined
        else "product, strategy, and analytics roles grounded in operational decision support"
    )
    return CareerBrief(
        positioning=positioning,
        target_role_lanes=target_lanes,
        adjacent_role_lanes=adjacent_lanes,
        excluded_lanes=sorted(set(excluded)),
        target_industries=prefs.target_industries,
        company_stage_preferences=["Series B+ startups", "technology companies"] if "series b" in combined or "startup" in combined else [],
        location_scope=prefs.preferred_locations,
        remote_preference=prefs.remote_preference,
        sponsorship_stance=prefs.work_authorization_status or ("Needs sponsorship-aware screening" if prefs.requires_sponsorship else "No sponsorship needed"),
        seniority_calibration=prefs.desired_seniority.value,
        resume_evidence=profile.evidence_notes + profile.strengths_for_search[:4],
        user_evidence=user_evidence,
        search_thesis=f"Search broadly for {positioning}, then rank against sponsorship, evidence of AI/value creation, product analytics fit, and seniority.",
        scoring_guidance="Reward roles that connect AI/analytics/product strategy to measurable business decisions; penalize pure routing/dispatch optimization, pure data science, and sponsorship blockers.",
        unresolved_questions=unresolved,
        readiness=readiness,
        confidence=0.75 if readiness == "ready_to_search" else 0.55,
    )


def _heuristic_strategy(
    profile: CandidateProfile,
    prefs: UserPreferences,
    memory: SearchMemory,
    brief: CareerBrief | None = None,
) -> SearchStrategyPlan:
    brief = brief or CareerBrief()
    titles = brief.target_role_lanes or prefs.target_job_titles or profile.target_functions or ["Product Strategy Manager"]
    adjacent = brief.adjacent_role_lanes or prefs.acceptable_adjacent_roles or ["Product Operations", "AI Solutions Consultant", "Business Operations"]
    locations = _normalize_locations(brief.location_scope or prefs.preferred_locations) or ["United States"]
    avoid_terms = [normalize_text(item) for item in (brief.excluded_lanes + prefs.role_families_to_avoid)]
    queries: list[SearchQuery] = []
    families = []
    broad_titles = _broad_role_titles(titles, adjacent, prefs)
    for title in broad_titles:
        if len(queries) >= prefs.max_searches:
            break
        if any(term and term in normalize_text(title) for term in avoid_terms):
            continue
        family = _infer_role_family(title)
        families.append(family)
        queries.append(
            SearchQuery(
                query=title,
                location=_canonical_location(locations[len(queries) % len(locations)]),
                rationale=f"Broad Google Jobs search for {title}; scoring will trim weak matches.",
                expected_tradeoff="Higher recall with more noise handled by triage and ranking.",
                job_family=family,
                strategy_type=SearchStrategyType.target_role,
                confidence=0.7,
            )
        )
    if prefs.requires_sponsorship and len(queries) < prefs.max_searches:
        queries.append(
            SearchQuery(
                query="strategy and operations manager",
                location=_canonical_location(locations[0]),
                rationale="Broad adjacent lane; sponsorship is assessed after retrieval from posting text.",
                expected_tradeoff="More recall; scoring will penalize sponsorship blockers and wrong seniority.",
                job_family="strategy operations",
                strategy_type=SearchStrategyType.adjacent_role,
                confidence=0.6,
            )
        )
    return SearchStrategyPlan(
        strategy_summary=brief.search_thesis or "Mix direct target roles with adjacent product, strategy, operations, analytics, and sponsorship-aware probes.",
        job_families=sorted(set(families)),
        queries=queries[: prefs.max_searches],
    )


def _broad_role_titles(titles: list[str], adjacent: list[str], prefs: UserPreferences) -> list[str]:
    seed = titles + adjacent
    text = normalize_text(" ".join(seed + [prefs.primary_goal]))
    defaults = [
        "product analyst",
        "product manager",
        "product strategy manager",
        "product analytics manager",
        "business operations analyst",
        "strategy and operations manager",
        "program manager",
        "AI product manager",
    ]
    if "ai" in text:
        defaults = [
            "AI product manager",
            "product analyst",
            "product manager",
            "product strategy manager",
            "product analytics manager",
            "strategy and operations manager",
            "business operations analyst",
            "program manager",
        ]
    seen = set()
    broad = []
    for title in defaults:
        if title not in seen:
            seen.add(title)
            broad.append(title)
    return broad


def _sanitize_strategy_queries(queries: list[SearchQuery], prefs: UserPreferences) -> list[SearchQuery]:
    sanitized = []
    seen = set()
    fallback_locations = _normalize_locations(prefs.preferred_locations) or ["United States"]
    for query in queries:
        clean_query = _sanitize_query_text(query.query)
        if not clean_query or clean_query in seen:
            continue
        seen.add(clean_query)
        sanitized.append(
            query.model_copy(
                update={
                    "query": clean_query,
                    "location": _canonical_location(query.location) or fallback_locations[(len(sanitized)) % len(fallback_locations)],
                    "expected_tradeoff": query.expected_tradeoff or "Broad retrieval; scoring and filters trim lower-fit jobs.",
                }
            )
        )
    return sanitized


def _sanitize_query_text(query: str) -> str:
    text = (query or "").replace("/", " ")
    text = text.split(" OR ", 1)[0]
    text = text.split(" AND ", 1)[0]
    text = text.replace("(", " ").replace(")", " ")
    words = [word.strip(",;:") for word in text.split() if word.strip(",;:")]
    blocked = {
        "mba",
        "sponsorship",
        "visa",
        "h1b",
        "requirements",
        "roadmap",
        "metrics",
        "kpi",
        "experimentation",
        "decision",
        "support",
    }
    kept = [word for word in words if word.lower() not in blocked]
    if not kept:
        kept = words
    return " ".join(kept[:5]).strip()


def _canonical_location(location: str | None) -> str | None:
    if not location:
        return None
    normalized_locations = _normalize_locations([location])
    if normalized_locations:
        return normalized_locations[0]
    return None


def _normalize_locations(locations: list[str] | None) -> list[str]:
    if not locations:
        return []
    normalized: list[str] = []
    for location in locations:
        for candidate in _split_location_candidates(location):
            canonical = _canonical_location_candidate(candidate)
            if canonical:
                normalized.append(canonical)
    seen = set()
    deduped = []
    for location in normalized:
        key = normalize_text(location)
        if key not in seen:
            seen.add(key)
            deduped.append(location)
    return deduped


def _split_location_candidates(location: str) -> list[str]:
    text = (location or "").strip()
    if not text:
        return []
    lowered = normalize_text(text)
    if lowered in {"any", "open", "flexible", "no preference", "coach decides", "coach decide"}:
        return []
    if lowered.endswith(" united states") and "(" not in text:
        return [text]
    if "(" in text and ")" in text:
        inner = text[text.find("(") + 1 : text.rfind(")")]
        if inner.strip():
            text = inner
    raw_tokens = [token.strip() for token in text.replace(";", ",").replace("\n", ",").split(",") if token.strip()]
    candidates: list[str] = []
    index = 0
    while index < len(raw_tokens):
        token = raw_tokens[index]
        next_token = raw_tokens[index + 1] if index + 1 < len(raw_tokens) else ""
        next_key = normalize_text(next_token)
        token_key = normalize_text(token)
        if (
            len(next_key) == 2
            and token_key in _CITY_STATE_ABBREVIATIONS
            and next_key in _STATE_LOCATION_LOOKUP
            and _CITY_STATE_ABBREVIATIONS[token_key] != next_key
        ):
            candidates.append(token)
            candidates.append(next_token)
            index += 2
        elif len(next_key) == 2 and token_key not in _STATE_LOCATION_LOOKUP and next_key in _STATE_LOCATION_LOOKUP:
            candidates.append(f"{token}, {next_token.upper()}")
            index += 2
        elif next_key == "united states" and token_key in _STATE_LOCATION_LOOKUP:
            candidates.append(f"{token}, United States")
            index += 2
        else:
            candidates.append(token)
            index += 1
    return candidates


def _canonical_location_candidate(location: str) -> str | None:
    if not location:
        return None
    lookup = {
        "san francisco bay area ca": "San Francisco, CA",
        "bay area ca": "San Francisco, CA",
        "san francisco": "San Francisco, CA",
        "sf": "San Francisco, CA",
        "new york ny": "New York, NY",
        "new york": "New York, NY",
        "nyc": "New York, NY",
        "los angeles ca": "Los Angeles, CA",
        "los angeles": "Los Angeles, CA",
        "seattle wa": "Seattle, WA",
        "seattle": "Seattle, WA",
        "austin tx": "Austin, TX",
        "austin": "Austin, TX",
        "chicago il": "Chicago, IL",
        "chicago": "Chicago, IL",
        "boston ma": "Boston, MA",
        "boston": "Boston, MA",
        "portland or": "Portland, OR",
        "portland": "Portland, OR",
        "remote": "United States",
        "anywhere": "United States",
        "united states": "United States",
    }
    state_lookup = {
        "california": "California, United States",
        "ca": "California, United States",
        "oregon": "Oregon, United States",
        "or": "Oregon, United States",
        "washington": "Washington, United States",
        "wa": "Washington, United States",
        "new york state": "New York, United States",
        "ny": "New York, United States",
        "illinois": "Illinois, United States",
        "il": "Illinois, United States",
        "massachusetts": "Massachusetts, United States",
        "ma": "Massachusetts, United States",
        "texas": "Texas, United States",
        "tx": "Texas, United States",
    }
    key = normalize_text(location)
    if key in lookup:
        return lookup[key]
    if key in state_lookup:
        return state_lookup[key]
    if key.endswith(" united states"):
        return location
    return location


_STATE_LOCATION_LOOKUP = {
    "ca",
    "or",
    "wa",
    "ny",
    "il",
    "ma",
    "tx",
    "california",
    "oregon",
    "washington",
    "new york state",
    "illinois",
    "massachusetts",
    "texas",
}

_CITY_STATE_ABBREVIATIONS = {
    "new york": "ny",
    "nyc": "ny",
    "san francisco": "ca",
    "sf": "ca",
    "los angeles": "ca",
    "seattle": "wa",
    "austin": "tx",
    "chicago": "il",
    "boston": "ma",
    "portland": "or",
}


def _clamp_preferences(prefs: UserPreferences, config: AppConfig) -> UserPreferences:
    prefs.max_searches = max(1, min(config.max_searches_per_run, prefs.max_searches))
    return prefs


def _serialize_rows(rows: list[tuple[SearchQuery, dict[str, Any]]]) -> list[dict[str, Any]]:
    return [{"query": query.model_dump(mode="json"), "raw": raw} for query, raw in rows]


def _deserialize_rows(rows: list[dict[str, Any]]) -> list[tuple[SearchQuery, dict[str, Any]]]:
    return [(SearchQuery.model_validate(item["query"]), item["raw"]) for item in rows]


def _repair_query(diagnostic: QueryDiagnostic, profile: CandidateProfile, prefs: UserPreferences) -> QueryRepairDecision:
    base = split_csvish(diagnostic.query)[0] if diagnostic.query else "business operations"
    family = _infer_role_family(base)
    replacement = {
        "product": "Product Strategy Manager MBA",
        "analytics": "Product Analytics Manager MBA",
        "operations": "Business Operations Manager tech",
        "strategy": "Strategy and Operations Manager tech",
    }.get(family, "AI Solutions Consultant MBA")
    location = (prefs.preferred_locations or [diagnostic.location or "United States"])[0]
    if profile.tools:
        replacement = f"{replacement} {profile.tools[0]}"
    return QueryRepairDecision(
        should_retry=True,
        replacement_query=replacement,
        replacement_location=location,
        repair_reason="Broadened title wording while preserving the candidate's strongest role family.",
        expected_improvement="Should recover roles that use adjacent titles or analytics/operations wording.",
    )


def _job_keyword_score(job: JobPosting, state: GraphState) -> int:
    score = 0
    text = normalize_text(" ".join([job.title, job.description, job.search_query]))
    profile = CandidateProfile.model_validate(state.get("candidate_profile") or {})
    prefs = UserPreferences.model_validate(state.get("inferred_preferences") or {})
    brief = CareerBrief.model_validate(state.get("career_brief") or {})
    for term in brief.target_role_lanes + brief.adjacent_role_lanes + prefs.target_job_titles + prefs.acceptable_adjacent_roles + profile.skills + profile.tools:
        if normalize_text(term) in text:
            score += 1
    for term in brief.excluded_lanes:
        if normalize_text(term) in text:
            score -= 4
    assessment = state.get("sponsorship_assessments", {}).get(job.job_id, {})
    if assessment.get("sponsorship_risk") == SponsorshipRisk.no_sponsorship.value:
        score -= 3
    return score


def _infer_role_family(title: str) -> str:
    text = normalize_text(title)
    if "product" in text:
        return "product"
    if "analytics" in text or "data" in text:
        return "analytics"
    if "operation" in text or "bizops" in text:
        return "operations"
    if "strategy" in text:
        return "strategy"
    if "solution" in text:
        return "solutions"
    return "general management"
