# Technicals: Career Search Coach

This is the engineering handoff for the current Career Search Coach implementation. It is written for a future agent or engineer who needs to run, debug, extend, or review the app quickly.

## 1. Product And Architecture Summary

Career Search Coach is a local AI-assisted job-fit search prototype. It accepts a resume, captures search preferences, generates a role-search brief and query strategy, searches Google Jobs through SerpApi, scores retrieved jobs with OpenAI structured outputs, and presents matches in a React results workbench with an application tracker.

The current primary app is:

- React + TypeScript frontend in `src-ui/`
- Vite dev/build pipeline from `package.json`
- FastAPI wrapper in `api.py`
- Existing Python/LangGraph backend in `src/`

There is also a local-only admin replay viewer:

- Admin React entry in `src-ui/admin.tsx`
- Admin Vite config in `vite.admin.config.ts`
- Read-only local FastAPI app in `admin_api.py`

The legacy Streamlit app remains in `app.py`, but new product work should target the React/FastAPI surface unless explicitly requested otherwise.

The backend is intentionally still step-oriented. The UI does not run the full graph for every interaction. Each step calls a narrow API endpoint so expensive search/scoring work happens only when the user approves and runs the strategy.

## 2. Runtime Stack

Frontend:

- React 19
- TypeScript
- Vite
- Phosphor icons
- Playwright as a dev dependency for browser smoke checks

API:

- FastAPI
- Uvicorn
- CORS allowing local Vite ports in the `51xx` range

Backend:

- LangGraph orchestration in `src/graph.py`
- Pydantic v2 models in `src/schemas.py`
- OpenAI Responses API structured outputs through `src/llm_client.py`
- SerpApi Google Jobs integration through `src/serpapi_client.py`
- Local JSON cache and replay through `src/cache.py`
- Local feedback memory through `src/memory.py`
- Pandas CSV export through `src/export.py`
- Resume parsing with `pypdf` and `python-docx`

## 3. Install, Run, Test

Install:

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install
Copy-Item .env.example .env
```

Run API:

```powershell
uvicorn api:app --reload --host 127.0.0.1 --port 8010
```

Run frontend:

```powershell
npm run dev
```

Build frontend:

```powershell
npm run build
```

Run local admin API:

```powershell
uvicorn admin_api:app --host 127.0.0.1 --port 8020
```

Run local admin frontend:

```powershell
npm run admin:dev
```

Build local admin frontend:

```powershell
npm run admin:build
```

Run tests:

```powershell
python -m pytest
```

In this workspace the validated commands have been:

```bash
npm run build
uv run --with-requirements requirements.txt pytest tests -s
```

Baseline test result:

```text
24 passed
```

## 4. Environment Variables

`src/config.py` loads `.env` with `python-dotenv`.

Required for live AI/search mode:

- `OPENAI_API_KEY`: enables profile extraction, brief generation, strategy generation, and job scoring.
- `SERPAPI_API_KEY`: enables live Google Jobs search.

Optional:

- `OPENAI_MODEL`: defaults to `gpt-5.4-nano-2026-03-17`.
- `MAX_SEARCHES_PER_RUN`: default 8, clamped to 1-8.
- `MAX_JOBS_TO_SCORE`: default 25.

Do not commit `.env`.

## 5. Primary Files

```text
api.py                    FastAPI endpoints around graph entrypoints
app.py                    Legacy Streamlit UI
index.html                Vite shell
package.json              Frontend scripts and dependencies
requirements.txt          Python dependencies
src-ui/
  main.tsx                Primary React app and stateful screens
  styles.css              Visual system and responsive layout
src/
  cache.py                Local graph-state cache and replay artifacts
  config.py               Environment variable loading and config object
  deduper.py              Conservative job deduplication
  export.py               Scored job dataframe and CSV export
  graph.py                LangGraph workflow, prompts, and step entrypoints
  job_normalizer.py       SerpApi raw result to JobPosting normalization
  llm_client.py           OpenAI strict structured-output wrapper
  memory.py               Feedback-to-search-memory updates
  resume_parser.py        PDF, DOCX, TXT resume parsing
  schemas.py              Pydantic contracts and GraphState TypedDict
  serpapi_client.py       SerpApi Google Jobs calls and pagination
  sponsorship.py          Deterministic sponsorship classifier
  utils.py                Text normalization, splitting, IDs, truncation
tests/
  test_graph_demo.py      Graph entrypoint and mocked-LLM behavior tests
  test_infrastructure.py  Parser, normalizer, dedupe, cache, memory tests
```

## 6. React UI Flow

`src-ui/main.tsx` owns the client-side workflow state and persists it to `localStorage` as `career-search-state`.

All API fetches use `credentials: "include"` so the backend-issued browser cookie is sent with requests. The frontend treats `cache_run_id` and `cache_run_label` as the public replay identifiers. It must not depend on server filesystem paths.

Workflow:

1. Resume
   - Upload, drag/drop, or paste resume text.
   - `/api/resume/parse` parses uploaded files.
   - `/api/profile` runs resume profile extraction.
   - The user remains on the Resume page after extraction and uses the profile header button to continue.
   - `Start over` clears local storage, app state, and local textarea state.

2. Preferences
   - User-owned constraints.
   - `Any` toggles let the coach decide for goal/title/adjacent/industry fields.
   - Location picker is searchable, multi-select, and closes on outside click.
   - `/api/preferences` saves preferences and clears downstream coach/search outputs.
   - The UI then calls `/api/coach-brief`.

3. Role Search Brief
   - Displays a compact readout of the thesis, best lanes, and sponsorship/level.
   - Detailed edits are hidden in `details` sections.
   - `/api/coach-brief/apply` saves edited brief.
   - Coach chat is currently hidden with `SHOW_COACH_CHAT = false`. The component and `/api/coach-chat` endpoint remain available for future work.

4. Strategy
   - `/api/strategy` proposes query/location lanes.
   - Users can edit query rows in `query | location` format.
   - `/api/search` runs only the approved-search path.

5. Results
   - Results use full workspace width; the progress sidebar is hidden on this step.
   - Filters: text search, minimum score, sponsorship-friendly only, location, recommended action.
   - Sorting: score, company, action.
   - Pagination: 5 rows per page.
   - Detail tabs: `Match fit`, `Role details`, `Company insights`.
   - `Match fit` merges the old "Why this match" and "Resume fit" content.
   - `Role details` renders `ScoredJob.job_description` or hydrates old cached runs from `deduped_jobs.description`.
   - `Company insights` renders LLM-extracted posting facts or falls back to company/about paragraphs in the posting text.
   - Application tracker supports add, save, remove, open link, selected-job navigation, and stage changes.

## 7. FastAPI Surface

`api.py` is a thin wrapper and should remain thin.

Endpoints:

- `GET /api/health`: API key/config status.
- `POST /api/resume/parse`: parse uploaded PDF/DOCX/TXT.
- `POST /api/profile`: run resume profile extraction.
- `POST /api/preferences`: save preferences and clear downstream outputs.
- `POST /api/coach-brief`: generate/update career brief.
- `POST /api/coach-brief/apply`: save edited career brief.
- `POST /api/coach-chat`: preserved hidden chat path; updates brief only and must not regenerate search strategy.
- `POST /api/strategy`: generate search strategy.
- `POST /api/search`: run approved search and scoring.
- `POST /api/feedback`: save feedback and update memory.
- `POST /api/export`: export scored jobs as CSV.
- `GET /api/runs`: list cached runs for the current browser cookie only.
- `GET /api/runs/load?run_id=<id>`: load a selected run ID from the current browser scope, or the latest browser-scoped run when no ID is provided.

`api.py` sets an anonymous `career_agent_browser_id` cookie when needed. The cookie is generated server-side with a random token, marked `HttpOnly` and `SameSite=Lax`, and marked `Secure` when the request is HTTPS or arrives through an HTTPS reverse proxy (`x-forwarded-proto: https`).

Returned state should expose `cache_run_id` and `cache_run_label`, not `cache_run_path`. Client-supplied `cache_run_path` is ignored, and client-supplied `cache_run_id` is resolved only inside the current browser's scoped cache directory.

## 8. Local Admin Replay Surface

`admin_api.py` is a separate read-only API for local replay inspection. It must be run only with:

```powershell
uvicorn admin_api:app --host 127.0.0.1 --port 8020
```

Do not bind it to `0.0.0.0`, do not add it to Cloudflare Tunnel, and do not expose it through the public app URL. The API rejects non-localhost `Host` headers as a defensive guard, but deployment safety comes from keeping it off the tunnel.

Admin endpoints:

- `GET /api/admin/health`: local admin status.
- `GET /api/admin/runs`: list all browser-scoped cached runs.
- `GET /api/admin/runs/{browser_hash}/{run_id}`: load one run detail.
- `GET /api/admin/runs/{browser_hash}/{run_id}/export`: export that run's scored jobs as CSV.

The admin frontend runs separately with `npm run admin:dev` and usually opens at `http://127.0.0.1:5174/admin.html`; use Vite's printed localhost URL if that port is busy. It is read-only: no delete, no notes, no cache mutation. It shows summaries first and keeps raw resume text collapsed by default.

## 9. LangGraph Entry Points

`src/graph.py` preserves the full graph for compatibility, but the UI uses narrow entrypoints:

- `run_resume_profile(state, config)`: parse/extract candidate profile only.
- `run_coach_brief(state, config)`: update preferences/coach state and create `CareerBrief` without strategy/search.
- `run_search_strategy(state, config)`: create `SearchStrategyPlan` without search.
- `run_approved_search(state, config)`: execute search, repair, normalize/dedupe, add sponsorship hints, score jobs, and summarize.

Full graph nodes:

- `parse_resume`
- `extract_candidate_profile`
- `coach_interview`
- `refine_candidate_profile`
- `update_preferences`
- `update_career_brief`
- `propose_search_strategy`
- `strategy_review`
- `execute_search`
- `repair_queries`
- `normalize_and_dedupe`
- `assess_sponsorship`
- `score_jobs`
- `coach_summary`
- `capture_feedback`
- `update_search_memory`

Approved search intentionally skips earlier profile/coaching/strategy agents and runs only the search/scoring path from the current saved strategy.

## 10. Graph State And Schemas

`GraphState` is a `TypedDict` in `src/schemas.py`. Most values are serialized Pydantic payloads so the app can cache/replay JSON.

Important models:

- `CandidateProfile`: resume-derived profile, strengths, gaps, skills, evidence, positioning.
- `UserPreferences`: user-owned constraints and sponsorship timing.
- `CareerBrief`: coach-owned thesis, lanes, exclusions, sponsorship stance, seniority calibration, scoring guidance, unresolved questions.
- `SearchQuery`: Google Jobs query/location lane with rationale and metadata.
- `SearchStrategyPlan`: summary and query list.
- `QueryDiagnostic`: per-query result counts, repair status, errors.
- `JobPosting`: normalized raw job posting.
- `SponsorshipAssessment`: deterministic sponsorship hint.
- `JobScore`: LLM scoring output, including extracted role/company details.
- `ScoredJob`: UI-ready scored row, including original posting description, extracted responsibilities/qualifications/company insights, URL/source/date, scores, matches, and gaps.
- `FeedbackRecord`: user label and notes.
- `SearchMemory`: durable local preference memory from feedback.

Schema compatibility matters because cached runs may have older `ScoredJob` rows. The React UI currently hydrates missing `job_description`, `source`, `date_posted`, `url`, and `search_query` from `deduped_jobs`/`normalized_jobs`.

## 11. LLM Integration

All schema-returning OpenAI calls go through `structured_response()` in `src/llm_client.py`.

Behavior:

- Uses `OpenAI(api_key=config.openai_api_key)`.
- Calls `client.responses.create()`.
- Requests strict JSON Schema output.
- Converts Pydantic JSON Schema into OpenAI-compatible strict schema.
- Retries once after JSON/Pydantic validation failure.
- Raises `LLMError` if both attempts fail.

Primary LLM call sites:

- Candidate profile extraction.
- Profile refinement from chat.
- Preference extraction.
- Career brief generation.
- Search strategy generation.
- Job scoring and posting-detail extraction.

`score_jobs()` is deliberately strict: when OpenAI is unavailable or demo mode is enabled, it returns no final scored jobs and records an error instead of inventing heuristic scores.

## 12. Search, Repair, Sponsorship, Scoring

Search:

- Query text is kept short and role-like.
- Location is passed separately as SerpApi's `location`.
- Backend sanitization prevents invalid combined locations and impossible city/state pairs.
- `search_google_jobs_paginated()` calls SerpApi Google Jobs with US locale settings and pagination tokens.
- Result counts/errors are stored in `query_diagnostics`.

Repair:

- `repair_queries()` retries zero-result searches while budget remains.
- Repair is deterministic in the current implementation.

Normalize/dedupe:

- `normalize_jobs()` converts raw rows to `JobPosting`.
- `dedupe_jobs()` removes exact company/title/location duplicates and near-identical long descriptions.

Sponsorship:

- `assess_sponsorship_deterministic()` provides positive/blocker/high-risk/unclear hints.
- LLM scoring makes the final sponsorship sub-score and evidence call.
- The app should not label a role sponsor-friendly without explicit positive evidence.

Scoring:

- Deterministic keyword ranking selects up to `MAX_JOBS_TO_SCORE` candidates for LLM scoring.
- LLM scoring runs in batches of 5, with up to 5 workers.
- The prompt includes title, company, location, and full description.
- The LLM returns sub-scores, matches, gaps, recommendation, sponsorship evidence, explanation, role summary, responsibilities, qualifications, and company insights.
- Overall score is the average of six 0-5 sub-scores converted to 0-100.
- Failed batches recursively split; omitted jobs are not heuristically scored.

## 13. Cache, Replay, Memory

Cache root:

```text
.cache/career_search_agent/
```

Run cache:

```text
.cache/career_search_agent/runs/<timestamp-run-id>/
```

This legacy global run cache remains for Streamlit compatibility and older tests. The React/FastAPI app no longer lists it through `/api/runs`.

Browser-scoped run cache:

```text
.cache/career_search_agent/browser_runs/<sha256-browser-id>/<timestamp-run-id>/
```

The browser ID is the backend-issued `career_agent_browser_id` cookie. `src/cache.py` hashes it before using it as a directory name. Incognito/private windows receive a different cookie and therefore a different scoped cache root.

`save_graph_state()` writes `graph_state.json` plus individual artifacts for resume text, profile, messages, preferences, strategy, raw SerpApi results, normalized jobs, deduped jobs, sponsorship hints, scored jobs, summary, feedback, and diagnostics. The FastAPI layer still calls the existing graph/cache functions, but it pre-populates `cache_run_path` with a browser-scoped directory and strips that internal path before returning state to the UI.

`save_graph_state()` also writes `metadata.json` for each run. Metadata is derived from `graph_state.json` and includes run ID, browser hash, timestamps, candidate name/headline, latest completed step, preferred locations, target lanes, scored job count, and top matches. Existing runs without metadata remain admin-viewable because `load_run_metadata()` derives the same summary from `graph_state.json`.

Replay:

- The UI lists `{ id, label }` objects from `/api/runs`; IDs are run directory names, never full paths.
- `/api/runs/load` resolves `run_id` only under the current browser scope and returns 404 for invalid, missing, or cross-browser IDs.
- `load_graph_state()` prefers `graph_state.json` and falls back to individual artifacts.

Memory:

- Durable memory lives at `.cache/career_search_agent/memory.json`.
- Feedback updates preferred/rejected role families, avoid lists, sponsorship sensitivity, seniority calibration, useful query patterns, and poor query patterns.

## 14. Tests

The test suite verifies:

- Narrow graph entrypoints do not accidentally run later workflow stages.
- Approved search skips prior agents and scores only.
- Demo/sample search does not fabricate heuristic final scores.
- Chat updates coach state without triggering search.
- Query and location sanitization.
- Browser-scoped cache isolation, no-cookie initialization, hidden legacy global runs, and cross-browser load rejection.
- Mocked LLM scoring.
- Minimal scoring payload, short scoring IDs, 25-job cap, and parallel batches.
- Resume parsing, normalization, dedupe, sponsorship rules, cache, export, and memory.

Run before pushing:

```bash
npm run build
npm run admin:build
uv run --with-requirements requirements.txt pytest tests -s
```

## 15. Known Gaps And Extension Points

Known gaps:

- Local-only prototype.
- No auth, cloud database, deployment, billing, or account-level isolation.
- Browser-scoped replay is privacy partitioning only. It prevents casual cross-browser cache exposure on the same public URL, but anyone with the same browser profile can still see that profile's runs.
- No automatic application submission.
- No LinkedIn scraping.
- Demo mode intentionally does not create final heuristic scores.
- Cache/replay is schema-sensitive.
- Application tracker state is local UI state plus feedback records, not a full persistent pipeline database.

Safe extension points:

- Persist tracker stages into backend feedback or a lightweight local table.
- Revisit coach chat as a true agent only after defining what it can mutate.
- Add richer company facts from the posting or a separate company enrichment provider.
- Add retry-on-missing-ID behavior for scoring.
- Add evaluation fixtures for real anonymized job-search sessions.

Risky areas:

- `GraphState` and `ScoredJob` changes because cache replay depends on compatibility.
- `llm_client._strict_json_schema()` because every structured-output call depends on it.
- `score_jobs()` because tests intentionally require LLM scoring for final results.
- `.env` and `.cache/` handling because secrets/runtime data must not be committed.
