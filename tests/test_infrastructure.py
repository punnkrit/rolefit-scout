from __future__ import annotations

from pathlib import Path

from fastapi.testclient import TestClient

from admin_api import app as admin_app
from api import BROWSER_COOKIE, app
from src.cache import BROWSER_RUNS_ROOT, build_run_metadata, load_graph_state, save_graph_state
from src.config import AppConfig
from src.deduper import dedupe_jobs
from src.export import dataframe_to_csv, jobs_to_dataframe
from src.job_normalizer import normalize_jobs
from src.memory import update_memory_from_feedback
from src.resume_parser import parse_txt
from src.schemas import FeedbackRecord, JobPosting, ReviewLabel, ScoredJob, SearchMemory, SearchQuery, SponsorshipRisk
from src.sponsorship import assess_sponsorship_deterministic


def test_parse_txt_and_normalize_jobs() -> None:
    text = parse_txt(Path("tests/sample_resume.txt").read_bytes())
    assert "Demo Candidate" in text

    raw = {
        "job_id": "job-1",
        "title": "Product Manager",
        "company_name": "Acme",
        "location": "Los Angeles, CA",
        "description": "Visa sponsorship available.",
        "apply_options": [{"title": "Company", "link": "https://example.com"}],
    }
    jobs = normalize_jobs([(SearchQuery(query="Product Manager", location="Los Angeles"), raw)])
    assert jobs[0].company == "Acme"
    assert jobs[0].url == "https://example.com"


def test_conservative_dedupe_keeps_distinct_locations() -> None:
    jobs = [
        JobPosting(job_id="1", title="Product Manager", company="Acme", location="Los Angeles"),
        JobPosting(job_id="2", title="Product Manager", company="Acme", location="Seattle"),
        JobPosting(job_id="3", title="Product Manager", company="Acme", location="Los Angeles"),
    ]
    kept = dedupe_jobs(jobs)
    assert [job.job_id for job in kept] == ["1", "2"]


def test_sponsorship_rules_are_conservative() -> None:
    sponsor = assess_sponsorship_deterministic(
        JobPosting(job_id="1", title="PM", company="Acme", location="Remote", description="Visa sponsorship available for qualified candidates.")
    )
    blocked = assess_sponsorship_deterministic(
        JobPosting(job_id="2", title="Ops", company="Acme", location="Remote", description="Must be authorized to work without sponsorship.")
    )
    unclear = assess_sponsorship_deterministic(
        JobPosting(job_id="3", title="Ops", company="Acme", location="Remote", description="Great role for an MBA.")
    )
    assert sponsor.sponsorship_risk == SponsorshipRisk.sponsor_friendly
    assert blocked.sponsorship_risk == SponsorshipRisk.no_sponsorship
    assert unclear.sponsorship_risk == SponsorshipRisk.unclear


def test_export_cache_and_memory(tmp_path: Path) -> None:
    job = ScoredJob(
        rank=1,
        job_id="1",
        company="Acme",
        title="Product Manager",
        location="Remote",
        overall_fit_score=80,
        role_fit=4,
        skill_fit=4,
        experience_fit=4,
        location_fit=5,
        industry_fit=4,
        sponsorship_fit=3,
        recommended_action="Apply",
    )
    df = jobs_to_dataframe([job])
    assert b"Product Manager" in dataframe_to_csv(df)

    path = save_graph_state({"resume_text": "hello", "scored_jobs": [job.model_dump(mode="json")]}, tmp_path / "run")
    loaded = load_graph_state(path)
    assert loaded["resume_text"] == "hello"
    assert loaded["scored_jobs"][0]["job_id"] == "1"

    memory = update_memory_from_feedback(
        SearchMemory(),
        [FeedbackRecord(job_id="1", label=ReviewLabel.apply, role_family="product", company="Acme", query="Product Manager MBA")],
    )
    assert "product" in memory.preferred_role_families
    assert "Product Manager MBA" in memory.useful_query_patterns


def test_browser_scoped_runs_hide_global_cache_and_set_cookie(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    save_graph_state({"resume_text": "global"}, tmp_path / ".cache" / "career_search_agent" / "runs" / "global-run")

    client = TestClient(app)
    response = client.get("/api/runs")

    assert response.status_code == 200
    assert response.cookies.get(BROWSER_COOKIE)
    assert response.json() == {"runs": [], "latest": None}


def test_browser_scoped_runs_are_isolated(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    first = TestClient(app)
    second = TestClient(app)

    payload = {
        "state": {"cache_run_path": str(tmp_path / ".cache" / "career_search_agent" / "runs" / "stolen")},
        "preferences": {"primary_goal": "Find product roles."},
    }
    first_response = first.post("/api/preferences", json=payload)
    assert first_response.status_code == 200
    run_id = first_response.json()["cache_run_id"]
    assert "cache_run_path" not in first_response.json()

    first_runs = first.get("/api/runs").json()
    second_runs = second.get("/api/runs").json()
    assert [item["id"] for item in first_runs["runs"]] == [run_id]
    assert second_runs == {"runs": [], "latest": None}

    forbidden = second.get(f"/api/runs/load?run_id={run_id}")
    assert forbidden.status_code == 404

    loaded = first.get(f"/api/runs/load?run_id={run_id}")
    assert loaded.status_code == 200
    assert loaded.json()["cache_run_id"] == run_id
    assert loaded.json()["inferred_preferences"]["primary_goal"] == "Find product roles."


def test_browser_scoped_state_cannot_overwrite_other_browser_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    first = TestClient(app)
    second = TestClient(app)

    first_run = first.post("/api/preferences", json={"state": {}, "preferences": {"primary_goal": "First browser"}}).json()["cache_run_id"]
    second_response = second.post(
        "/api/preferences",
        json={"state": {"cache_run_id": first_run}, "preferences": {"primary_goal": "Second browser"}},
    )

    assert second_response.status_code == 200
    assert second_response.json()["cache_run_id"] == first_run
    assert first.get(f"/api/runs/load?run_id={first_run}").json()["inferred_preferences"]["primary_goal"] == "First browser"
    assert second.get(f"/api/runs/load?run_id={first_run}").json()["inferred_preferences"]["primary_goal"] == "Second browser"


def test_run_metadata_extracts_admin_summary(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = BROWSER_RUNS_ROOT / "browserhash" / "20260526-120000-abc12345"
    state = {
        "resume_text": "Jane Candidate resume",
        "candidate_profile": {"name": "Jane Candidate", "current_status": "MBA candidate", "target_functions": ["Product"]},
        "inferred_preferences": {"preferred_locations": ["New York, NY"]},
        "career_brief": {"target_role_lanes": ["Product Analytics"], "positioning": "Product analytics leader"},
        "scored_jobs": [
            ScoredJob(
                rank=1,
                job_id="job-1",
                company="Acme",
                title="Product Analytics Manager",
                location="New York, NY",
                overall_fit_score=88,
                role_fit=5,
                skill_fit=5,
                experience_fit=4,
                location_fit=5,
                industry_fit=4,
                sponsorship_fit=3,
                recommended_action="Apply",
            ).model_dump(mode="json")
        ],
    }
    save_graph_state(state, path)

    metadata = build_run_metadata(load_graph_state(path), path)

    assert metadata["candidate_name"] == "Jane Candidate"
    assert metadata["latest_step"] == "results"
    assert metadata["preferred_locations"] == ["New York, NY"]
    assert metadata["target_lanes"] == ["Product Analytics"]
    assert metadata["scored_jobs_count"] == 1
    assert metadata["top_matches"][0]["company"] == "Acme"


def test_admin_lists_browser_runs_and_excludes_legacy_global_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    save_graph_state({"candidate_profile": {"name": "Global User"}}, tmp_path / ".cache" / "career_search_agent" / "runs" / "global-run")
    first_path = BROWSER_RUNS_ROOT / "browser-a" / "20260526-120000-aaaaaaaa"
    second_path = BROWSER_RUNS_ROOT / "browser-b" / "20260526-130000-bbbbbbbb"
    save_graph_state({"candidate_profile": {"name": "First User"}}, first_path)
    save_graph_state({"candidate_profile": {"name": "Second User"}}, second_path)

    client = TestClient(admin_app, base_url="http://127.0.0.1")
    response = client.get("/api/admin/runs")

    assert response.status_code == 200
    names = {item["candidate_name"] for item in response.json()["runs"]}
    assert names == {"First User", "Second User"}


def test_admin_detail_rejects_path_traversal_and_loads_valid_run(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    path = BROWSER_RUNS_ROOT / "browser-a" / "20260526-120000-aaaaaaaa"
    save_graph_state({"candidate_profile": {"name": "Local User"}}, path)
    client = TestClient(admin_app, base_url="http://127.0.0.1")

    ok = client.get("/api/admin/runs/browser-a/20260526-120000-aaaaaaaa")
    forbidden = client.get("/api/admin/runs/%2E%2E/20260526-120000-aaaaaaaa")

    assert ok.status_code == 200
    assert ok.json()["metadata"]["candidate_name"] == "Local User"
    assert forbidden.status_code in {400, 404}


def test_admin_rejects_non_localhost_host(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    client = TestClient(admin_app, base_url="https://career-agent-mvp.apocryphaai.org")

    response = client.get("/api/admin/health")

    assert response.status_code == 403
    assert response.json()["detail"] == "Admin API is localhost-only."


def test_admin_export_returns_csv_for_empty_and_scored_runs(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    empty_path = BROWSER_RUNS_ROOT / "browser-a" / "20260526-120000-empty000"
    scored_path = BROWSER_RUNS_ROOT / "browser-a" / "20260526-130000-scored00"
    save_graph_state({"candidate_profile": {"name": "Empty User"}, "scored_jobs": []}, empty_path)
    save_graph_state(
        {
            "candidate_profile": {"name": "Scored User"},
            "scored_jobs": [
                ScoredJob(
                    rank=1,
                    job_id="job-1",
                    company="Acme",
                    title="Product Manager",
                    location="Remote",
                    overall_fit_score=80,
                    role_fit=4,
                    skill_fit=4,
                    experience_fit=4,
                    location_fit=5,
                    industry_fit=4,
                    sponsorship_fit=3,
                    recommended_action="Apply",
                ).model_dump(mode="json")
            ],
        },
        scored_path,
    )
    client = TestClient(admin_app, base_url="http://127.0.0.1")

    empty = client.get("/api/admin/runs/browser-a/20260526-120000-empty000/export")
    scored = client.get("/api/admin/runs/browser-a/20260526-130000-scored00/export")

    assert empty.status_code == 200
    assert b"recommended_action" in empty.content
    assert scored.status_code == 200
    assert b"Product Manager" in scored.content
