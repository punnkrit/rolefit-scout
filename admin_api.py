from __future__ import annotations

from pathlib import Path
from typing import Any

from fastapi import FastAPI, HTTPException, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse
from fastapi.responses import Response

from src.cache import BROWSER_RUNS_ROOT, list_all_browser_run_cache_dirs, load_graph_state, load_run_metadata
from src.export import dataframe_to_csv, jobs_to_dataframe
from src.schemas import ScoredJob


app = FastAPI(title="Career Search Coach Local Admin API")
app.add_middleware(
    CORSMiddleware,
    allow_origins=["http://localhost:5174", "http://127.0.0.1:5174"],
    allow_origin_regex=r"http://(localhost|127\.0\.0\.1):51[0-9]{2}",
    allow_credentials=False,
    allow_methods=["GET"],
    allow_headers=["*"],
)


@app.middleware("http")
async def require_localhost_host(request: Request, call_next):
    host = request.headers.get("host", "").split(":")[0].lower()
    if host not in {"127.0.0.1", "localhost", "::1"}:
        return JSONResponse({"detail": "Admin API is localhost-only."}, status_code=403)
    return await call_next(request)


@app.get("/api/admin/health")
def health() -> dict[str, Any]:
    return {"ok": True, "cache_root": str(BROWSER_RUNS_ROOT), "mode": "local-only"}


@app.get("/api/admin/runs")
def list_runs() -> dict[str, Any]:
    runs = [load_run_metadata(path) for path in list_all_browser_run_cache_dirs()]
    return {"runs": runs}


@app.get("/api/admin/runs/{browser_hash}/{run_id}")
def load_run(browser_hash: str, run_id: str) -> dict[str, Any]:
    path = _admin_run_path(browser_hash, run_id)
    state = load_graph_state(path)
    return {"metadata": load_run_metadata(path), "state": _admin_state(state)}


@app.get("/api/admin/runs/{browser_hash}/{run_id}/export")
def export_run(browser_hash: str, run_id: str) -> Response:
    path = _admin_run_path(browser_hash, run_id)
    state = load_graph_state(path)
    scored = [ScoredJob.model_validate(item) for item in state.get("scored_jobs", [])]
    csv_bytes = dataframe_to_csv(jobs_to_dataframe(scored))
    return Response(
        csv_bytes,
        media_type="text/csv",
        headers={"Content-Disposition": f"attachment; filename={run_id}-career-search-tracker.csv"},
    )


def _admin_run_path(browser_hash: str, run_id: str) -> Path:
    if Path(browser_hash).name != browser_hash or Path(run_id).name != run_id:
        raise HTTPException(status_code=404, detail="Run not found.")
    path = BROWSER_RUNS_ROOT / browser_hash / run_id
    if not path.is_dir():
        raise HTTPException(status_code=404, detail="Run not found.")
    return path


def _admin_state(state: dict[str, Any]) -> dict[str, Any]:
    public = dict(state)
    public.pop("cache_run_path", None)
    return public
