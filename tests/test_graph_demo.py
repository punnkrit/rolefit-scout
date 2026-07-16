from __future__ import annotations

from pathlib import Path

from src.config import AppConfig
from src.graph import _normalize_locations, _sanitize_strategy_queries, run_approved_search, run_coach_brief, run_graph, run_resume_profile, run_search_strategy, score_jobs
from src.schemas import CandidateProfile, CareerBrief, JobScore, ScoredJobList, SearchQuery
from src.schemas import SearchStrategyPlan, SponsorshipAssessmentList, SponsorshipRisk, TriageSelection, TriageSelectionList, UserPreferences


def test_demo_graph_builds_strategy_without_search(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resume_text = Path(__file__).with_name("sample_resume.txt").read_text(encoding="utf-8")
    state = run_graph(
        {
            "resume_text": resume_text,
            "demo_mode": True,
            "live_search_enabled": False,
            "approved_strategy": {"approved": False, "edited_queries": []},
        },
        AppConfig(openai_api_key=None, serpapi_api_key=None, max_searches_per_run=4, max_jobs_to_score=3),
    )
    assert state["candidate_profile"]["name"] == "Demo Candidate"
    assert UserPreferences.model_validate(state["inferred_preferences"]).max_searches == 4
    assert SearchStrategyPlan.model_validate(state["search_strategy"]).queries
    assert CareerBrief.model_validate(state["career_brief"]).search_thesis
    assert state["scored_jobs"] == []
    assert state["cache_run_path"]
    assert "optimizing most for role fit" not in state["messages"][-1]["content"]
    assert "Your resume reads strongest" in state["messages"][-1]["content"]


def test_resume_profile_entrypoint_does_not_build_strategy_or_search(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resume_text = Path(__file__).with_name("sample_resume.txt").read_text(encoding="utf-8")
    state = run_resume_profile(
        {
            "resume_text": resume_text,
            "demo_mode": True,
            "live_search_enabled": False,
        },
        AppConfig(openai_api_key=None, serpapi_api_key=None, max_searches_per_run=4, max_jobs_to_score=3),
    )
    assert state["candidate_profile"]["name"] == "Demo Candidate"
    assert not state.get("search_strategy")
    assert state["serpapi_results"] == []
    assert state["scored_jobs"] == []


def test_coach_brief_entrypoint_does_not_build_strategy_or_search(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resume_text = Path(__file__).with_name("sample_resume.txt").read_text(encoding="utf-8")
    state = run_coach_brief(
        {
            "resume_text": resume_text,
            "demo_mode": True,
            "live_search_enabled": False,
            "inferred_preferences": UserPreferences(
                primary_goal="Find AI product roles.",
                target_job_titles=["AI Product Manager"],
                preferred_locations=["San Francisco, CA"],
                max_searches=4,
            ).model_dump(mode="json"),
        },
        AppConfig(openai_api_key=None, serpapi_api_key=None, max_searches_per_run=4, max_jobs_to_score=3),
    )
    assert CareerBrief.model_validate(state["career_brief"]).search_thesis
    assert not state.get("search_strategy")
    assert state["serpapi_results"] == []
    assert state["scored_jobs"] == []


def test_search_strategy_entrypoint_does_not_search(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resume_text = Path(__file__).with_name("sample_resume.txt").read_text(encoding="utf-8")
    brief_state = run_coach_brief(
        {
            "resume_text": resume_text,
            "demo_mode": True,
            "live_search_enabled": False,
            "inferred_preferences": UserPreferences(
                primary_goal="Find AI product roles.",
                target_job_titles=["AI Product Manager"],
                preferred_locations=["San Francisco, CA"],
                max_searches=4,
            ).model_dump(mode="json"),
        },
        AppConfig(openai_api_key=None, serpapi_api_key=None, max_searches_per_run=4, max_jobs_to_score=3),
    )
    state = run_search_strategy(
        brief_state,
        AppConfig(openai_api_key=None, serpapi_api_key=None, max_searches_per_run=4, max_jobs_to_score=3),
    )
    assert SearchStrategyPlan.model_validate(state["search_strategy"]).queries
    assert state["approved_strategy"] == {"approved": False, "edited_queries": []}
    assert state["serpapi_results"] == []
    assert state["scored_jobs"] == []


def test_app_no_longer_exposes_search_budget() -> None:
    app_text = Path("app.py").read_text(encoding="utf-8")
    assert "Search budget" not in app_text


def test_app_uses_gated_workflow_instead_of_clickable_tabs() -> None:
    app_text = Path("app.py").read_text(encoding="utf-8")
    assert "st.tabs" not in app_text
    assert "Continue to Coach Brief" in app_text
    assert "workflow_radio" not in app_text
    assert "st.multiselect(\n            \"Locations\"" in app_text


def test_demo_graph_does_not_generate_heuristic_scores(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    source_tests = Path(__file__).parent
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "sample_jobs.json").write_text((source_tests / "sample_jobs.json").read_text(encoding="utf-8"), encoding="utf-8")
    resume_text = (source_tests / "sample_resume.txt").read_text(encoding="utf-8")

    first = run_graph(
        {
            "resume_text": resume_text,
            "demo_mode": True,
            "live_search_enabled": False,
            "approved_strategy": {"approved": False, "edited_queries": []},
        },
        AppConfig(openai_api_key=None, serpapi_api_key=None, max_searches_per_run=5, max_jobs_to_score=3),
    )
    strategy = SearchStrategyPlan.model_validate(first["search_strategy"])
    second = run_graph(
        {
            **first,
            "approved_strategy": {"approved": True, "edited_queries": [query.model_dump(mode="json") for query in strategy.queries]},
            "demo_mode": True,
            "live_search_enabled": False,
        },
        AppConfig(openai_api_key=None, serpapi_api_key=None, max_searches_per_run=5, max_jobs_to_score=3),
    )
    assert second["deduped_jobs"]
    assert second["scored_jobs"] == []
    assert second["sponsorship_assessments"]
    assert any("No heuristic scores" in error for error in second["errors"])


def test_chat_answer_gets_coach_reply_and_updates_strategy(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resume_text = Path(__file__).with_name("sample_resume.txt").read_text(encoding="utf-8")
    state = run_graph(
        {
            "resume_text": resume_text,
            "demo_mode": True,
            "conversation_updated": True,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "I want a role involving AI. It does not have to be product, but product-based AI is my preferred path. "
                        "I need sponsorship because I am an international student. I do not want workforce or dispatch optimization, "
                        "but product analytics is fine. Let me know what you think."
                    ),
                }
            ],
            "approved_strategy": {"approved": False, "edited_queries": []},
        },
        AppConfig(openai_api_key=None, serpapi_api_key=None, max_searches_per_run=5, max_jobs_to_score=3),
    )
    assert state["messages"][-1]["role"] == "assistant"
    assert "AI product roles" in state["messages"][-1]["content"]
    profile = CandidateProfile.model_validate(state["candidate_profile"])
    assert "AI strategy" in profile.target_functions
    assert any("AI-related role" in insight for insight in profile.interview_insights)
    prefs = UserPreferences.model_validate(state["inferred_preferences"])
    assert "workforce and dispatch optimization" in prefs.role_families_to_avoid
    brief = CareerBrief.model_validate(state["career_brief"])
    assert "AI" in brief.positioning
    assert "workforce/dispatch optimization" in brief.excluded_lanes
    strategy = SearchStrategyPlan.model_validate(state["search_strategy"])
    assert any("AI" in query.query for query in strategy.queries)


def test_chat_interview_completes_when_user_says_enough(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resume_text = Path(__file__).with_name("sample_resume.txt").read_text(encoding="utf-8")
    state = run_graph(
        {
            "resume_text": resume_text,
            "demo_mode": True,
            "conversation_updated": True,
            "messages": [
                {
                    "role": "user",
                    "content": (
                        "AI Product/Strategy is my lead lane. Tech companies and Series B startups are fine. "
                        "I need sponsorship. Let me know if these are good enough."
                    ),
                }
            ],
            "approved_strategy": {"approved": False, "edited_queries": []},
        },
        AppConfig(openai_api_key=None, serpapi_api_key=None, max_searches_per_run=5, max_jobs_to_score=3),
    )
    assert state["interview_complete"] is True
    assert state["open_questions"] == []
    assert CareerBrief.model_validate(state["career_brief"]).readiness == "ready_to_search"
    assert "ready" in state["messages"][-1]["content"].lower()


def test_profile_refines_without_inventing_shipped_ai(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    resume_text = Path(__file__).with_name("sample_resume.txt").read_text(encoding="utf-8")
    state = run_graph(
        {
            "resume_text": resume_text,
            "demo_mode": True,
            "conversation_updated": True,
            "messages": [
                {
                    "role": "user",
                    "content": "AI Product/Strategy is my lead lane, but we haven't built anything AI-specific yet.",
                }
            ],
            "approved_strategy": {"approved": False, "edited_queries": []},
        },
        AppConfig(openai_api_key=None, serpapi_api_key=None, max_searches_per_run=5, max_jobs_to_score=3),
    )
    profile = CandidateProfile.model_validate(state["candidate_profile"])
    assert "AI strategy" in profile.target_functions
    assert any("weaker" in gap for gap in profile.potential_gaps)
    assert any("Avoid overstating" in note for note in profile.positioning_notes)


def test_strategy_queries_are_broad_and_serpapi_friendly() -> None:
    prefs = UserPreferences(preferred_locations=["San Francisco Bay Area, CA"])
    queries = _sanitize_strategy_queries(
        [
            SearchQuery(
                query="AI Product Manager OR Technical Product Manager (AI features) product analytics experimentation A/B testing requirements roadmap",
                location="San Francisco Bay Area, CA",
            )
        ],
        prefs,
    )
    assert queries[0].query == "AI Product Manager"
    assert queries[0].location == "San Francisco, CA"


def test_strategy_locations_never_keep_combined_parenthetical_location() -> None:
    prefs = UserPreferences(preferred_locations=["California, United States", "Oregon, United States", "Seattle, WA"])
    queries = _sanitize_strategy_queries(
        [
            SearchQuery(
                query="Product Manager",
                location="United States (California, Oregon, Seattle, New York, Chicago, Boston)",
            )
        ],
        prefs,
    )
    assert queries[0].location == "California, United States"
    assert "(" not in queries[0].location


def test_location_normalization_accepts_states_and_target_cities() -> None:
    locations = _normalize_locations(["California, Oregon, Seattle, New York, Chicago, Boston"])
    assert locations == [
        "California, United States",
        "Oregon, United States",
        "Seattle, WA",
        "New York, NY",
        "Chicago, IL",
        "Boston, MA",
    ]


def test_location_normalization_splits_impossible_city_state_pair() -> None:
    locations = _normalize_locations(["Seattle, NY"])
    assert locations == ["Seattle, WA", "New York, United States"]


def test_llm_scoring_is_required_and_used(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    source_tests = Path(__file__).parent
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "sample_jobs.json").write_text((source_tests / "sample_jobs.json").read_text(encoding="utf-8"), encoding="utf-8")
    resume_text = (source_tests / "sample_resume.txt").read_text(encoding="utf-8")

    def fake_structured_response(config, output_model, system_prompt, user_prompt):
        if output_model is ScoredJobList:
            import ast
            import re

            jobs_text = re.search(r"Jobs:\n(.+)$", user_prompt, re.S).group(1)
            jobs = ast.literal_eval(jobs_text)
            return ScoredJobList(
                jobs=[
                    JobScore(
                        job_id=job["job_id"],
                        role_fit=4,
                        skill_fit=3,
                        experience_fit=3,
                        location_fit=3,
                        industry_fit=4,
                        sponsorship_fit=3,
                        key_matches=["LLM-scored match"],
                        key_gaps=["LLM-scored gap"],
                        recommended_action="Maybe",
                        explanation="Mock LLM score.",
                    )
                    for job in jobs[:2]
                ]
            )
        if output_model is SponsorshipAssessmentList:
            return SponsorshipAssessmentList(assessments=[])
        if output_model is TriageSelectionList:
            import ast
            import re

            jobs_text = re.search(r"Jobs:\n(.+)$", user_prompt, re.S).group(1)
            jobs = ast.literal_eval(jobs_text)
            return TriageSelectionList(
                selections=[
                    TriageSelection(job_id=job["job_id"], keep=index < 2, priority=index + 1, reason="Mock triage.")
                    for index, job in enumerate(jobs)
                ]
            )
        raise AssertionError(f"Unexpected structured output model: {output_model}")

    monkeypatch.setattr("src.graph.structured_response", fake_structured_response)
    first = run_graph(
        {
            "resume_text": resume_text,
            "demo_mode": True,
            "live_search_enabled": False,
            "approved_strategy": {"approved": False, "edited_queries": []},
        },
        AppConfig(openai_api_key=None, serpapi_api_key=None, max_searches_per_run=5, max_jobs_to_score=2),
    )
    strategy = SearchStrategyPlan.model_validate(first["search_strategy"])
    second = run_graph(
        {
            **first,
            "approved_strategy": {"approved": True, "edited_queries": [query.model_dump(mode="json") for query in strategy.queries]},
            "demo_mode": False,
            "live_search_enabled": False,
        },
        AppConfig(openai_api_key="test-key", serpapi_api_key=None, max_searches_per_run=5, max_jobs_to_score=2),
    )
    assert len(second["scored_jobs"]) == 2
    assert second["scored_jobs"][0]["key_matches"] == ["LLM-scored match"]
    assert second["scored_jobs"][0]["sponsorship_risk"] in {risk.value for risk in SponsorshipRisk}


def test_approved_search_skips_prior_agents_and_scores_only(tmp_path: Path, monkeypatch) -> None:
    monkeypatch.chdir(tmp_path)
    source_tests = Path(__file__).parent
    tests_dir = tmp_path / "tests"
    tests_dir.mkdir()
    (tests_dir / "sample_jobs.json").write_text((source_tests / "sample_jobs.json").read_text(encoding="utf-8"), encoding="utf-8")
    resume_text = (source_tests / "sample_resume.txt").read_text(encoding="utf-8")

    first = run_graph(
        {
            "resume_text": resume_text,
            "demo_mode": True,
            "live_search_enabled": False,
            "approved_strategy": {"approved": False, "edited_queries": []},
        },
        AppConfig(openai_api_key=None, serpapi_api_key=None, max_searches_per_run=5, max_jobs_to_score=2),
    )
    strategy = SearchStrategyPlan.model_validate(first["search_strategy"])

    def fake_structured_response(config, output_model, system_prompt, user_prompt):
        assert output_model is ScoredJobList
        import ast
        import re

        jobs_text = re.search(r"Jobs:\n(.+)$", user_prompt, re.S).group(1)
        jobs = ast.literal_eval(jobs_text)
        return ScoredJobList(
            jobs=[
                JobScore(
                    job_id=job["job_id"],
                    role_fit=4,
                    skill_fit=4,
                    experience_fit=3,
                    location_fit=3,
                    industry_fit=4,
                    sponsorship_fit=2,
                    sponsorship_risk=SponsorshipRisk.unclear,
                    sponsorship_evidence="No explicit statement was found.",
                    sponsorship_reasoning_summary="The scorer evaluated sponsorship inside the scoring pass.",
                    key_matches=["Search-path score"],
                    key_gaps=["Sponsorship unclear"],
                    recommended_action="Maybe",
                    explanation="Mock approved-search scoring.",
                )
                for job in jobs
            ]
        )

    monkeypatch.setattr("src.graph.structured_response", fake_structured_response)
    second = run_approved_search(
        {
            **first,
            "approved_strategy": {"approved": True, "edited_queries": [query.model_dump(mode="json") for query in strategy.queries]},
            "demo_mode": False,
            "live_search_enabled": False,
        },
        AppConfig(openai_api_key="test-key", serpapi_api_key=None, max_searches_per_run=5, max_jobs_to_score=2),
    )
    assert len(second["scored_jobs"]) == 2
    assert second["scored_jobs"][0]["key_matches"] == ["Search-path score"]
    assert second["messages"] == first["messages"]


def test_scoring_uses_short_ids_minimal_payload_and_five_parallel_batches(monkeypatch) -> None:
    calls = []

    def fake_structured_response(config, output_model, system_prompt, user_prompt):
        assert output_model is ScoredJobList
        import ast
        import re

        jobs_text = re.search(r"Jobs:\n(.+)$", user_prompt, re.S).group(1)
        jobs = ast.literal_eval(jobs_text)
        calls.append(jobs)
        for index, job in enumerate(jobs, start=1):
            assert set(job) == {"job_id", "title", "company", "location", "description"}
            assert job["job_id"].startswith("job_")
            assert "original-serpapi-id" not in job["job_id"]
            assert "source" not in job
            assert "date_posted" not in job
            assert "url" not in job
            assert "search_query" not in job
            assert "Full context" in job["description"]
        return ScoredJobList(
            jobs=[
                JobScore(
                    job_id=job["job_id"],
                    role_fit=4,
                    skill_fit=4,
                    experience_fit=3,
                    location_fit=3,
                    industry_fit=4,
                    sponsorship_fit=3,
                    key_matches=["Minimal payload"],
                    key_gaps=[],
                    recommended_action="Maybe",
                    explanation="Mock score.",
                )
                for job in jobs
            ]
        )

    monkeypatch.setattr("src.graph.structured_response", fake_structured_response)
    jobs = [
        {
            "job_id": f"original-serpapi-id-{index:02d}-this-should-not-be-sent-to-llm",
            "title": f"Product Manager {index:02d}",
            "company": f"Company {index:02d}",
            "location": "United States",
            "description": f"Full context description for Product Manager {index:02d}.",
            "source": "Google Jobs",
            "date_posted": "2026-05-01",
            "url": f"https://example.com/{index}",
            "search_query": "Product Manager",
        }
        for index in range(25)
    ]
    state = {
        "deduped_jobs": jobs,
        "candidate_profile": {"target_functions": ["product management"]},
        "inferred_preferences": {"target_job_titles": ["Product Manager"]},
        "career_brief": {"target_role_lanes": ["Product Manager"], "readiness": "ready_to_search"},
        "sponsorship_assessments": {},
        "run_trace": [],
        "errors": [],
    }

    result = score_jobs(
        state,
        AppConfig(openai_api_key="test-key", serpapi_api_key=None, max_searches_per_run=5, max_jobs_to_score=25),
    )

    assert len(result["scored_jobs"]) == 25
    assert {job["job_id"] for job in result["scored_jobs"]} == {job["job_id"] for job in jobs}
    assert len(calls) == 5
    assert sorted(len(call) for call in calls) == [5, 5, 5, 5, 5]
    batch_starts = [item for item in state["run_trace"] if item["event"] == "scoring.batch.start"]
    assert len(batch_starts) == 5
    assert all(item["details"]["batch_size"] == 5 for item in batch_starts)
