from __future__ import annotations

import json
from hashlib import sha256
from dataclasses import asdict, is_dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


CACHE_ROOT = Path(".cache/career_search_agent")
RUNS_ROOT = CACHE_ROOT / "runs"
BROWSER_RUNS_ROOT = CACHE_ROOT / "browser_runs"
MEMORY_PATH = CACHE_ROOT / "memory.json"


ARTIFACT_MAP = {
    "resume_text": "resume_text.json",
    "candidate_profile": "candidate_profile.json",
    "messages": "conversation_messages.json",
    "inferred_preferences": "preferences.json",
    "search_strategy": "search_strategy.json",
    "approved_strategy": "strategy_approval.json",
    "serpapi_results": "raw_serpapi_results.json",
    "normalized_jobs": "normalized_jobs.json",
    "deduped_jobs": "deduped_jobs.json",
    "sponsorship_assessments": "sponsorship_assessments.json",
    "triage_decisions": "triage_decisions.json",
    "scored_jobs": "scored_jobs.json",
    "coach_summary": "coach_summary.json",
    "user_feedback": "feedback.json",
    "query_diagnostics": "query_diagnostics.json",
}


def create_run_cache_dir(root: Path = RUNS_ROOT) -> Path:
    run_id = datetime.now().strftime("%Y%m%d-%H%M%S") + "-" + uuid4().hex[:8]
    path = root / run_id
    path.mkdir(parents=True, exist_ok=True)
    return path


def browser_runs_root(browser_id: str, root: Path = BROWSER_RUNS_ROOT) -> Path:
    digest = sha256(browser_id.encode("utf-8")).hexdigest()
    return root / digest


def create_browser_run_cache_dir(browser_id: str, root: Path = BROWSER_RUNS_ROOT) -> Path:
    return create_run_cache_dir(browser_runs_root(browser_id, root))


def _safe_run_id(run_id: str) -> str:
    candidate = Path(run_id).name
    if candidate != run_id or not candidate:
        raise ValueError("Invalid run id.")
    return candidate


def browser_run_cache_dir(browser_id: str, run_id: str, root: Path = BROWSER_RUNS_ROOT) -> Path:
    return browser_runs_root(browser_id, root) / _safe_run_id(run_id)


def latest_cache_dir(root: Path = RUNS_ROOT) -> Path | None:
    if not root.exists():
        return None
    dirs = [path for path in root.iterdir() if path.is_dir()]
    return max(dirs, key=lambda path: path.name) if dirs else None


def list_run_cache_dirs(root: Path = RUNS_ROOT) -> list[Path]:
    if not root.exists():
        return []
    return sorted((path for path in root.iterdir() if path.is_dir()), key=lambda path: path.name, reverse=True)


def latest_browser_cache_dir(browser_id: str, root: Path = BROWSER_RUNS_ROOT) -> Path | None:
    return latest_cache_dir(browser_runs_root(browser_id, root))


def list_browser_run_cache_dirs(browser_id: str, root: Path = BROWSER_RUNS_ROOT) -> list[Path]:
    return list_run_cache_dirs(browser_runs_root(browser_id, root))


def write_json(path: Path, name: str, data: Any) -> None:
    path.mkdir(parents=True, exist_ok=True)
    (path / name).write_text(json.dumps(_jsonable(data), indent=2), encoding="utf-8")


def read_json(path: Path) -> Any:
    return json.loads(path.read_text(encoding="utf-8"))


def save_graph_state(state: dict[str, Any], run_path: str | Path | None = None) -> Path:
    path = Path(run_path) if run_path else create_run_cache_dir()
    state = dict(state)
    state["cache_run_path"] = str(path)
    write_json(path, "graph_state.json", state)
    for key, artifact_name in ARTIFACT_MAP.items():
        if key in state:
            write_json(path, artifact_name, state[key])
    write_json(path, "metadata.json", build_run_metadata(state, path))
    return path


def save_browser_graph_state(state: dict[str, Any], browser_id: str, run_id: str | None = None) -> Path:
    path = browser_run_cache_dir(browser_id, run_id) if run_id else create_browser_run_cache_dir(browser_id)
    return save_graph_state(state, path)


def load_graph_state(path: str | Path) -> dict[str, Any]:
    run_path = Path(path)
    graph_state = run_path / "graph_state.json"
    if graph_state.exists():
        state = read_json(graph_state)
        state["cache_run_path"] = str(run_path)
        return state
    state: dict[str, Any] = {"cache_run_path": str(run_path)}
    for key, artifact_name in ARTIFACT_MAP.items():
        artifact = run_path / artifact_name
        if artifact.exists():
            state[key] = read_json(artifact)
    return state


def load_browser_graph_state(browser_id: str, run_id: str) -> dict[str, Any]:
    path = browser_run_cache_dir(browser_id, run_id)
    if not path.is_dir():
        raise FileNotFoundError(run_id)
    return load_graph_state(path)


def list_all_browser_run_cache_dirs(root: Path = BROWSER_RUNS_ROOT) -> list[Path]:
    if not root.exists():
        return []
    paths: list[Path] = []
    for browser_dir in root.iterdir():
        if browser_dir.is_dir():
            paths.extend(path for path in browser_dir.iterdir() if path.is_dir())
    return sorted(paths, key=lambda path: path.name, reverse=True)


def load_run_metadata(path: str | Path) -> dict[str, Any]:
    run_path = Path(path)
    metadata_path = run_path / "metadata.json"
    if metadata_path.exists():
        return read_json(metadata_path)
    return build_run_metadata(load_graph_state(run_path), run_path)


def build_run_metadata(state: dict[str, Any], path: str | Path) -> dict[str, Any]:
    run_path = Path(path)
    profile = state.get("candidate_profile") or {}
    prefs = state.get("inferred_preferences") or {}
    brief = state.get("career_brief") or {}
    strategy = state.get("search_strategy") or {}
    scored_jobs = state.get("scored_jobs") or []
    target_lanes = brief.get("target_role_lanes") or strategy.get("job_families") or []
    top_matches = sorted(scored_jobs, key=lambda item: item.get("overall_fit_score", 0), reverse=True)[:5]
    return {
        "run_id": run_path.name,
        "browser_hash": _browser_hash_from_run_path(run_path),
        "created_at": _created_at_from_run_id(run_path.name),
        "updated_at": _mtime_iso(run_path / "graph_state.json" if (run_path / "graph_state.json").exists() else run_path),
        "candidate_name": profile.get("name") or "Unknown candidate",
        "candidate_headline": profile.get("current_status") or brief.get("positioning") or "",
        "latest_step": _latest_step(state),
        "preferred_locations": prefs.get("preferred_locations") or brief.get("location_scope") or [],
        "target_lanes": target_lanes,
        "scored_jobs_count": len(scored_jobs),
        "top_matches": [
            {
                "title": item.get("title", "Untitled role"),
                "company": item.get("company", "Unknown company"),
                "location": item.get("location", ""),
                "score": item.get("overall_fit_score", 0),
                "recommended_action": item.get("recommended_action", ""),
            }
            for item in top_matches
        ],
    }


def _browser_hash_from_run_path(path: Path) -> str:
    return path.parent.name if path.parent.parent.name == BROWSER_RUNS_ROOT.name else ""


def _created_at_from_run_id(run_id: str) -> str:
    try:
        return datetime.strptime("-".join(run_id.split("-")[:2]), "%Y%m%d-%H%M%S").replace(tzinfo=timezone.utc).isoformat()
    except ValueError:
        return ""


def _mtime_iso(path: Path) -> str:
    return datetime.fromtimestamp(path.stat().st_mtime, tz=timezone.utc).isoformat()


def _latest_step(state: dict[str, Any]) -> str:
    if state.get("scored_jobs"):
        return "results"
    if state.get("search_strategy"):
        return "strategy"
    if state.get("career_brief"):
        return "brief"
    if state.get("inferred_preferences"):
        return "preferences"
    if state.get("candidate_profile"):
        return "profile"
    if state.get("resume_text"):
        return "resume"
    return "draft"


def _jsonable(data: Any) -> Any:
    if hasattr(data, "model_dump"):
        return data.model_dump(mode="json")
    if is_dataclass(data):
        return asdict(data)
    if isinstance(data, dict):
        return {key: _jsonable(value) for key, value in data.items()}
    if isinstance(data, list):
        return [_jsonable(item) for item in data]
    if isinstance(data, tuple):
        return [_jsonable(item) for item in data]
    return data
