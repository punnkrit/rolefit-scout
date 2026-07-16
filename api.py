from __future__ import annotations

from io import BytesIO
from pathlib import Path
from secrets import token_urlsafe
from typing import Any

from fastapi import Cookie, FastAPI, File, HTTPException, Request, Response, UploadFile
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response as FastAPIResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel

from src.cache import (
    browser_run_cache_dir,
    create_browser_run_cache_dir,
    latest_browser_cache_dir,
    list_browser_run_cache_dirs,
    load_browser_graph_state,
    save_graph_state,
)
from src.config import load_config
from src.export import dataframe_to_csv, jobs_to_dataframe
from src.graph import run_approved_search, run_coach_brief, run_resume_profile, run_search_strategy
from src.memory import load_memory, save_memory, update_memory_from_feedback
from src.resume_parser import ResumeParseError, parse_resume_file
from src.schemas import CareerBrief, FeedbackRecord, ScoredJob, SearchQuery, UserPreferences


BROWSER_COOKIE = "career_agent_browser_id"


class StateRequest(BaseModel):
    state: dict[str, Any] = {}


class PreferencesRequest(StateRequest):
    preferences: dict[str, Any]


class CareerBriefRequest(StateRequest):
    career_brief: dict[str, Any]


class StrategyRequest(StateRequest):
    queries: list[dict[str, Any]]


class CoachMessageRequest(StateRequest):
    message: str


class FeedbackRequest(StateRequest):
    feedback: dict[str, Any]


app = FastAPI(title="Career Search Coach API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5173", "http://127.0.0.1:5173"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):51[0-9]{2}",
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)


@app.get("/api/health")
def health(request: Request, response: Response, browser_id: str = Cookie(default=None, alias=BROWSER_COOKIE)) -> dict[str, Any]:
    _get_or_set_browser_id(request, response, browser_id)
    config = load_config()
    return {
        "ok": True,
        "openai_configured": config.has_openai_key,
        "serpapi_configured": config.has_serpapi_key,
        "max_searches_per_run": config.max_searches_per_run,
        "max_jobs_to_score": config.max_jobs_to_score,
    }


@app.post("/api/resume/parse")
async def parse_resume(request: Request, response: Response, upload: UploadFile = File(...), browser_id: str = Cookie(default=None, alias=BROWSER_COOKIE)) -> dict[str, str]:
    _get_or_set_browser_id(request, response, browser_id)
    try:
        data = await upload.read()
        text = parse_resume_file(BytesIO(data), upload.filename or "resume.txt")
    except ResumeParseError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc
    return {"resume_text": text}


@app.post("/api/profile")
def profile(request_body: StateRequest, request: Request, response: Response, browser_id: str = Cookie(default=None, alias=BROWSER_COOKIE)) -> dict[str, Any]:
    browser_id = _get_or_set_browser_id(request, response, browser_id)
    return _public_state(run_resume_profile(_prepare_state(request_body.state, browser_id), load_config()))


@app.post("/api/preferences")
def preferences(request_body: PreferencesRequest, request: Request, response: Response, browser_id: str = Cookie(default=None, alias=BROWSER_COOKIE)) -> dict[str, Any]:
    browser_id = _get_or_set_browser_id(request, response, browser_id)
    prefs = UserPreferences.model_validate(request_body.preferences)
    state = _prepare_state(request_body.state, browser_id)
    state["inferred_preferences"] = prefs.model_dump(mode="json")
    _clear_coach_and_search_outputs(state)
    state["interview_complete"] = False
    state["conversation_updated"] = False
    save_graph_state(state, state.get("cache_run_path"))
    return _public_state(state)


@app.post("/api/coach-brief")
def coach_brief(request_body: StateRequest, request: Request, response: Response, browser_id: str = Cookie(default=None, alias=BROWSER_COOKIE)) -> dict[str, Any]:
    browser_id = _get_or_set_browser_id(request, response, browser_id)
    return _public_state(run_coach_brief(_prepare_state(request_body.state, browser_id), load_config()))


@app.post("/api/coach-brief/apply")
def apply_coach_brief(request_body: CareerBriefRequest, request: Request, response: Response, browser_id: str = Cookie(default=None, alias=BROWSER_COOKIE)) -> dict[str, Any]:
    browser_id = _get_or_set_browser_id(request, response, browser_id)
    brief = CareerBrief.model_validate(request_body.career_brief)
    state = _prepare_state(request_body.state, browser_id)
    state["career_brief"] = brief.model_dump(mode="json")
    state["interview_complete"] = brief.readiness == "ready_to_search"
    state["open_questions"] = brief.unresolved_questions
    save_graph_state(state, state.get("cache_run_path"))
    return _public_state(state)


@app.post("/api/coach-chat")
def coach_chat(request_body: CoachMessageRequest, request: Request, response: Response, browser_id: str = Cookie(default=None, alias=BROWSER_COOKIE)) -> dict[str, Any]:
    browser_id = _get_or_set_browser_id(request, response, browser_id)
    state = _prepare_state(request_body.state, browser_id)
    state["messages"] = [*state.get("messages", []), {"role": "user", "content": request_body.message}]
    state["conversation_updated"] = True
    return _public_state(run_coach_brief(state, load_config()))


@app.post("/api/strategy")
def strategy(request_body: StateRequest, request: Request, response: Response, browser_id: str = Cookie(default=None, alias=BROWSER_COOKIE)) -> dict[str, Any]:
    browser_id = _get_or_set_browser_id(request, response, browser_id)
    return _public_state(run_search_strategy(_prepare_state(request_body.state, browser_id), load_config()))


@app.post("/api/search")
def search(request_body: StrategyRequest, request: Request, response: Response, browser_id: str = Cookie(default=None, alias=BROWSER_COOKIE)) -> dict[str, Any]:
    browser_id = _get_or_set_browser_id(request, response, browser_id)
    queries = [SearchQuery.model_validate(item).model_dump(mode="json") for item in request_body.queries if str(item.get("query", "")).strip()]
    state = _prepare_state(request_body.state, browser_id)
    state["approved_strategy"] = {"approved": True, "edited_queries": queries}
    return _public_state(run_approved_search(state, load_config()))


@app.post("/api/feedback")
def feedback(request_body: FeedbackRequest, request: Request, response: Response, browser_id: str = Cookie(default=None, alias=BROWSER_COOKIE)) -> dict[str, Any]:
    browser_id = _get_or_set_browser_id(request, response, browser_id)
    record = FeedbackRecord.model_validate(request_body.feedback)
    state = _prepare_state(request_body.state, browser_id)
    state.setdefault("user_feedback", []).append(record.model_dump(mode="json"))
    memory = update_memory_from_feedback(load_memory(), [record])
    save_memory(memory)
    state["search_memory"] = memory.model_dump(mode="json")
    save_graph_state(state, state.get("cache_run_path"))
    return _public_state(state)


@app.post("/api/export")
def export_tracker(request_body: StateRequest, request: Request, browser_id: str = Cookie(default=None, alias=BROWSER_COOKIE)) -> FastAPIResponse:
    scored = [ScoredJob.model_validate(item) for item in request_body.state.get("scored_jobs", [])]
    csv_bytes = dataframe_to_csv(jobs_to_dataframe(scored))
    csv_response = FastAPIResponse(
        csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": "attachment; filename=career_search_tracker.csv"},
    )
    _get_or_set_browser_id(request, csv_response, browser_id)
    return csv_response


@app.get("/api/runs")
def runs(request: Request, response: Response, browser_id: str = Cookie(default=None, alias=BROWSER_COOKIE)) -> dict[str, Any]:
    browser_id = _get_or_set_browser_id(request, response, browser_id)
    paths = list_browser_run_cache_dirs(browser_id)
    latest = latest_browser_cache_dir(browser_id)
    return {
        "runs": [{"id": path.name, "label": path.name} for path in paths],
        "latest": {"id": latest.name, "label": latest.name} if latest else None,
    }


@app.get("/api/runs/load")
def load_run(request: Request, response: Response, run_id: str | None = None, browser_id: str = Cookie(default=None, alias=BROWSER_COOKIE)) -> dict[str, Any]:
    browser_id = _get_or_set_browser_id(request, response, browser_id)
    target_id = run_id
    if not target_id:
        latest = latest_browser_cache_dir(browser_id)
        target_id = latest.name if latest else None
    if not target_id:
        raise HTTPException(status_code=404, detail="No cached runs found.")
    try:
        return _public_state(load_browser_graph_state(browser_id, target_id))
    except (FileNotFoundError, ValueError) as exc:
        raise HTTPException(status_code=404, detail="Cached run not found.") from exc


def _get_or_set_browser_id(request: Request, response: Response, browser_id: str | None) -> str:
    value = browser_id or token_urlsafe(32)
    if not browser_id:
        response.set_cookie(
            BROWSER_COOKIE,
            value,
            httponly=True,
            samesite="lax",
            secure=request.url.scheme == "https" or request.headers.get("x-forwarded-proto") == "https",
            max_age=60 * 60 * 24 * 365,
        )
    return value


def _prepare_state(state: dict[str, Any] | None, browser_id: str) -> dict[str, Any]:
    prepared = dict(state or {})
    prepared.setdefault("messages", [])
    prepared.setdefault("demo_mode", False)
    prepared.setdefault("live_search_enabled", True)
    cache_run_id = prepared.get("cache_run_id")
    prepared.pop("cache_run_path", None)
    try:
        prepared["cache_run_path"] = str(browser_run_cache_dir(browser_id, cache_run_id)) if cache_run_id else str(create_browser_run_cache_dir(browser_id))
    except ValueError:
        prepared["cache_run_path"] = str(create_browser_run_cache_dir(browser_id))
    return prepared


def _public_state(state: dict[str, Any]) -> dict[str, Any]:
    public = dict(state)
    path = public.pop("cache_run_path", None)
    if path:
        label = Path(path).name
        public["cache_run_id"] = label
        public["cache_run_label"] = label
    return public


def _clear_coach_and_search_outputs(state: dict[str, Any]) -> None:
    for key in ("career_brief", "open_questions"):
        state.pop(key, None)
    _clear_search_outputs(state)


def _clear_search_outputs(state: dict[str, Any]) -> None:
    for key in (
        "search_strategy",
        "approved_strategy",
        "serpapi_results",
        "normalized_jobs",
        "deduped_jobs",
        "sponsorship_assessments",
        "triage_decisions",
        "scored_jobs",
        "coach_summary",
        "query_diagnostics",
    ):
        state.pop(key, None)


DIST_DIR = Path(__file__).parent / "dist"
if DIST_DIR.exists():
    app.mount("/", StaticFiles(directory=DIST_DIR, html=True), name="frontend")
