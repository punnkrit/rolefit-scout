# RoleFit Scout

RoleFit Scout is a job-fit search app that turns a resume and search constraints into focused search lanes, LLM-scored role matches, and an application tracker.

## Hosted Demo

The Sites build is an interactive, frontend-only demo with a fictional candidate and fictional companies. It uses no API keys, sends no resume data to a server, and keeps demo feedback in the current browser session. The local full-stack mode remains available for private development.

```powershell
npm run build:demo
```

The current app is a React + TypeScript frontend with a thin FastAPI API layer. The original Python LangGraph backend in `src/` remains the source of truth for profile extraction, coach brief generation, strategy generation, search, sponsorship assessment, scoring, cache/replay, export, and feedback memory. The legacy Streamlit UI is still available in `app.py` for comparison, but the primary UI is `src-ui/`.

## Current Product Flow

1. `Resume`: upload, drag/drop, or paste a resume; extract and review the profile before continuing.
2. `Preferences`: set goals, target titles, adjacent lanes, industries, remote preference, sponsorship timing, hard exclusions, and searchable multi-select locations.
3. `Role search brief`: review and edit the generated search thesis, role lanes, sponsorship stance, seniority calibration, and scoring guidance.
4. `Strategy`: review/edit Google Jobs query/location lanes, then run approved search.
5. `Results`: filter, sort, inspect, save, track, and export LLM-scored matches.

The coach chat UI is intentionally hidden for now behind `SHOW_COACH_CHAT = false` in `src-ui/main.tsx`. The backend chat endpoint is preserved, but chat no longer regenerates search strategy.

## Features

- PDF, DOCX, TXT upload plus pasted resume text.
- Drag-and-drop resume upload.
- Resume profile extraction that stays on the Resume page until the user continues.
- Start-over flow that clears app state and local resume text.
- Searchable multi-select location picker.
- `Any` preference toggles for fields the user wants the coach to decide.
- Editable role-search brief with compact readout and expandable edit sections.
- Editable query/location strategy before running search.
- SerpApi Google Jobs search with diagnostics and query repair.
- Deterministic sponsorship hints plus sponsorship-aware LLM scoring.
- Parallel LLM scoring, defaulting to 25 jobs across 5-job batches.
- Results workbench with filters, score slider, sponsorship filter, location/action filters, sort, pagination, job detail tabs, save, and CSV export.
- Factual Role Details from the job posting text and extracted scoring fields.
- Company Insights from extracted posting facts, with posting-text fallback when available.
- Application tracker with saved jobs, stage updates, open-link actions, removal, and selected-job navigation.
- Browser-scoped local cache/replay for previous runs.
- Local feedback memory that learns from user labels.

## Requirements

- Python 3.11+
- Node.js 20+ recommended
- OpenAI API key for live profile extraction, brief/strategy generation, and job scoring
- SerpApi key for live Google Jobs search

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install -r requirements.txt
npm install
Copy-Item .env.example .env
```

Fill in `.env`:

```text
OPENAI_API_KEY=
SERPAPI_API_KEY=
OPENAI_MODEL=gpt-5.4-nano-2026-03-17
MAX_SEARCHES_PER_RUN=8
MAX_JOBS_TO_SCORE=25
```

Never commit `.env`.

## Run

Start the API:

```powershell
uvicorn api:app --reload --host 127.0.0.1 --port 8010
```

Start the React app:

```powershell
npm run dev
```

Open the Vite URL, usually:

```text
http://127.0.0.1:5173
```

The API allows local Vite origins on `localhost` or `127.0.0.1` ports in the `51xx` range.

## Legacy Streamlit UI

The pre-redesign Streamlit app is still available:

```powershell
streamlit run app.py
```

Use it only as a reference for legacy behavior. New UI work should happen in `src-ui/` and `api.py`.

## Local Admin Replay Viewer

The admin replay viewer is a separate local-only miniapp for reviewing cached user runs on the workstation. It is read-only and must not be added to Cloudflare Tunnel.

Start the admin API:

```powershell
uvicorn admin_api:app --host 127.0.0.1 --port 8020
```

Start the admin UI:

```powershell
npm run admin:dev
```

Open:

```text
http://127.0.0.1:5174/admin.html
```

If Vite reports a different local port because `5174` is already in use, use the printed `127.0.0.1` URL.

Do not bind the admin API to `0.0.0.0`, and do not expose port `8020` or `5174` through Cloudflare. The admin viewer scans `.cache/career_search_agent/browser_runs/*/*/`, lists all browser-scoped runs by derived metadata, and hides raw resume text behind a collapsed section by default.

## Test And Validate

Backend/unit tests:

```powershell
python -m pytest
```

Frontend production build:

```powershell
npm run build
```

Admin frontend production build:

```powershell
npm run admin:build
```

Current verified checks:

```text
npm run build
python -m pytest
```

The test suite covers graph entrypoints, approved-search fast path, query/location sanitization, mocked LLM scoring, parallel scoring batches, resume parsing, job normalization, dedupe, sponsorship rules, cache/replay, export, and feedback memory.

## Project Structure

```text
api.py                       FastAPI wrapper around the backend graph
admin_api.py                 Local-only read-only admin replay API
app.py                       Legacy Streamlit UI
index.html                   Vite app shell
admin.html                   Vite admin app shell
package.json                 React/TypeScript scripts and dependencies
requirements.txt             Python dependencies
TECHNICALS.md                Engineering handoff and architecture notes
career_search_agent_prd.md   Product requirements and original design context
business_case.md             Product and business rationale
run_app.bat                  Windows helper
src-ui/                      Primary React UI
src/
  cache.py                   Local graph-state cache and replay
  config.py                  Environment/config loading
  deduper.py                 Conservative job deduplication
  export.py                  Tracker dataframe and CSV export
  graph.py                   LangGraph workflow, prompts, and node functions
  job_normalizer.py          SerpApi result normalization
  llm_client.py              OpenAI structured-output helper
  memory.py                  Feedback memory
  resume_parser.py           PDF, DOCX, TXT parsing
  schemas.py                 Pydantic models and graph state
  serpapi_client.py          SerpApi Google Jobs client
  sponsorship.py             Sponsorship risk rules
  utils.py                   Shared utility functions
tests/                       Unit and graph-flow tests
```

## Runtime Data

Local runtime data is written under:

```text
.cache/career_search_agent/
```

This includes graph-state snapshots, raw search results, normalized/deduped jobs, scored jobs, query diagnostics, feedback, and memory. Runtime data and secrets are ignored by Git.

React/FastAPI replay is scoped to an anonymous browser cookie named `career_agent_browser_id`. The cookie is generated by the backend, marked `HttpOnly` and `SameSite=Lax`, and marked `Secure` when served over HTTPS. JavaScript does not read or write it.

New cached runs are stored under:

```text
.cache/career_search_agent/browser_runs/<sha256-browser-id>/<run-id>/
```

Only runs for the current browser cookie are listed in Replay. Incognito/private browser sessions get a separate cookie and should start with an empty Replay list. Existing legacy runs under `.cache/career_search_agent/runs/` remain on disk for compatibility but are no longer shown by the React UI or `/api/runs`.

This is lightweight privacy partitioning, not authentication. Anyone using the same browser profile can still see that browser profile's cached runs.

Each saved run also writes `metadata.json` for the local admin viewer. Existing runs without metadata are still readable because the admin API derives the same summary from `graph_state.json`.

## Notes For Future Work

- The app is a local prototype, not a hosted SaaS service.
- There is no authentication, cloud database, billing, or automatic job application submission.
- Demo mode can retrieve sample jobs but intentionally does not fabricate final heuristic fit scores.
- Cache/replay is schema-sensitive; when changing `ScoredJob`, keep backward-compatible UI fallbacks.
- Browser-scoped replay hides other browsers' cached runs but is not a substitute for login-based authorization.
- The hidden coach chat can be revisited later, but it should not automatically regenerate search strategy unless that behavior is explicitly redesigned.
