# PRD: Career Coach Search Agent

## 1. Product Overview

Build a stateful career coach and job search agent that helps MBA students and early-career professionals discover, evaluate, and track job opportunities that fit their resume, goals, preferences, and work authorization constraints.

The product is not a form-driven job search tool. It is an agent-centered career search assistant. The user uploads a resume, then the agent interviews the user, interprets their background, proposes search lanes, searches live postings, adapts weak searches, evaluates job fit, explains recommendations, and learns from the user's feedback.

The first implementation should be a Streamlit v2 app backed by a LangGraph workflow. Streamlit is used for speed and iteration; LangGraph is used because the product is a stateful graph with conversation, branching, tool calls, repair loops, scoring, feedback, and memory.

## 2. Product Positioning

The product should feel like:

- A career coach who understands MBA and early-career job search.
- A search analyst who knows how to translate a resume into job families and search strategies.
- A tracker assistant that keeps application decisions organized.
- A sponsorship-aware reviewer that conservatively flags work authorization risk.

The product should not feel like:

- A generic chatbot.
- A job board clone.
- A deterministic form that only searches titles the user already knows.
- A one-shot resume-to-score script.

## 3. Target Users

Primary users:

- MBA students and recent MBA graduates.
- International students who must consider sponsorship now or in the future.
- Career switchers who are not sure which titles/functions best match their background.
- Early-career professionals who want structured help translating experience into job-search lanes.

Initial wedge:

- International MBA students targeting product, strategy, operations, analytics, AI solutions, business operations, marketplace, SaaS, or technology-adjacent roles.

## 4. Core Jobs To Be Done

The user hires the product to:

1. Understand what roles they are realistically competitive for.
2. Discover job families and titles they may not have considered.
3. Search broadly enough to find opportunities, but intelligently enough to avoid noise.
4. Understand whether jobs fit their resume, goals, seniority, location, and sponsorship needs.
5. Maintain a ranked tracker with human review labels and notes.
6. Learn from rejected jobs and improve the next search.

## 5. Product Principles

### 5.1 The Agent Owns Career Search Strategy

The user should not need to know every correct job title. The agent should infer plausible role families from the resume and conversation, explain why they make sense, and ask for approval before searching.

### 5.2 Conversation Builds Structure

The app should use conversation to elicit goals and constraints, then convert the conversation into structured state. Forms are useful for obvious fields such as location, search budget, and sponsorship timing, but the core preference discovery should be conversational.

### 5.3 Deterministic Code Guards, Agents Reason

Deterministic code should handle:

- Resume file parsing.
- SerpApi execution.
- Search budget enforcement.
- Conservative deduplication.
- Cache and replay.
- CSV export.
- Basic validation and schema enforcement.

LLM/agent logic should handle:

- Candidate profile interpretation.
- Career coaching and follow-up questions.
- Preference elicitation.
- Job-family expansion.
- Search strategy generation.
- Query repair after weak results.
- Sponsorship wording interpretation.
- Job triage and fit scoring.
- User-facing explanations.
- Learning from feedback.

### 5.4 Evidence Over Vibes

Every important recommendation should be grounded in evidence from the resume, preferences, conversation, or job posting.

## 6. High-Level User Workflow

### Step 1: Upload Resume

The user uploads a resume as PDF, DOCX, TXT, or pasted text.

The system:

- Extracts readable text deterministically.
- Shows a preview.
- Uses an LLM to extract a structured candidate profile.
- Shows a coach-style profile summary with strengths, possible gaps, and likely role families.

### Step 2: Coach Interview

The agent asks targeted follow-up questions based on the resume and missing preference information.

Example questions:

- "Are you optimizing for PM title, product-adjacent role fit, sponsorship likelihood, compensation, or brand?"
- "Are you open to product analytics or product operations if those are stronger-fit paths into PM?"
- "How strict are your location constraints?"
- "Do you need sponsorship immediately, in the future, or are you unsure?"
- "Are there industries or role types you actively want to avoid?"

The agent should ask a small number of high-signal questions, not a long generic questionnaire.

### Step 3: Preference State Extraction

The agent converts the conversation into structured preferences:

- Target outcomes.
- Role/title preferences.
- Acceptable adjacent roles.
- Preferred and excluded locations.
- Remote/hybrid/on-site preference.
- Industry interests.
- Sponsorship constraints.
- Seniority constraints.
- Companies/industries/keywords to avoid.
- Search budget.

The user can edit obvious fields in a form-like panel.

### Step 4: Search Strategy Proposal

Before calling SerpApi, the agent proposes a search strategy:

- Search lanes/job families.
- Query/location pairs.
- Rationale for each query.
- Expected tradeoffs.
- Which lanes are direct target roles vs adjacent bets.

The user can approve, remove, or edit lanes before search.

### Step 5: Search Execution

The system executes approved searches through SerpApi Google Jobs.

The search process should:

- Respect search budget.
- Put geography in SerpApi's location parameter when applicable.
- Keep query text role-like and practical.
- Cache raw results.
- Track per-query result counts.

### Step 6: Query Repair Loop

If a query returns no results or weak results, the query repair agent can spend remaining budget on a replacement query.

The repair agent receives:

- Failed query and location.
- Prior attempted queries.
- Candidate profile.
- Preferences.
- Failure reason or result count.

The repair agent returns:

- Whether to retry.
- Replacement query.
- Replacement location.
- Repair rationale.
- Expected improvement.

### Step 7: Normalize, Dedupe, And Preserve Raw Evidence

The system normalizes SerpApi jobs into a consistent schema.

Deduplication should be conservative:

- Remove same normalized company + title + location.
- Keep different titles, levels, teams, or locations unless clearly identical.

Raw SerpApi records should remain cached for debugging.

### Step 8: Sponsorship Assessment

Sponsorship assessment is hybrid:

- Deterministic rules catch obvious sponsor-friendly or blocker language.
- LLM classifier reviews unclear or nuanced wording.

The system should return:

- Sponsorship risk label.
- Evidence from the posting.
- Reasoning summary.

Allowed labels:

- Sponsor-Friendly
- No Sponsorship
- High Risk
- Unclear

The app must never claim sponsorship availability unless explicit evidence exists.

### Step 9: Job Triage

If the retrieved job pool exceeds the scoring budget, an LLM triage agent selects jobs for detailed scoring.

The triage agent should consider:

- Role fit.
- Resume evidence.
- Location preference.
- Sponsorship risk.
- Seniority fit.
- Industry fit.
- User goals from the coach interview.

The system should cache triage decisions and reasons.

### Step 10: Fit Scoring And Ranking

The LLM scorer evaluates selected jobs using a transparent rubric.

Each scored job should include:

- Overall Fit Score from 0 to 100.
- Role Fit from 0 to 5.
- Skill Fit from 0 to 5.
- Experience Fit from 0 to 5.
- Location Fit from 0 to 5.
- Industry Fit from 0 to 5.
- Sponsorship Fit from 0 to 5.
- Key matches.
- Key gaps.
- Sponsorship evidence.
- Recommended action.
- Explanation grounded in resume and job posting evidence.

If the LLM omits jobs, retry missing IDs once. If missing jobs remain, use heuristic fallback only to preserve tracker completeness.

### Step 11: Coach Summary

After ranking jobs, the coach agent summarizes:

- Strongest search lanes.
- Weakest or noisy lanes.
- Top jobs to apply to first.
- Sponsorship risk pattern.
- Suggested changes for the next search.

This should be written as practical career advice, not generic encouragement.

### Step 12: Human Review And Feedback Learning

The user labels jobs:

- Apply
- Maybe
- Reject
- Wrong Role
- Sponsorship Issue
- Too Senior
- Bad Location
- Duplicate

The feedback learner updates memory:

- Role families to prioritize or avoid.
- Seniority calibration.
- Location constraints.
- Sponsorship constraints.
- Company/industry preferences.
- Query patterns that produced useful or useless results.

## 7. LangGraph Architecture

Use LangGraph as the main orchestration layer.

### 7.1 Graph Nodes

Required nodes:

- `parse_resume`
- `extract_candidate_profile`
- `coach_interview`
- `update_preferences`
- `propose_search_strategy`
- `strategy_review`
- `execute_search`
- `repair_queries`
- `normalize_and_dedupe`
- `assess_sponsorship`
- `triage_jobs`
- `score_jobs`
- `coach_summary`
- `capture_feedback`
- `update_search_memory`

### 7.2 Graph State

The graph state should include:

```json
{
  "resume_text": "string",
  "candidate_profile": {},
  "messages": [],
  "inferred_preferences": {},
  "open_questions": [],
  "search_strategy": {},
  "approved_strategy": {},
  "serpapi_results": [],
  "normalized_jobs": [],
  "deduped_jobs": [],
  "sponsorship_assessments": {},
  "triage_decisions": [],
  "scored_jobs": [],
  "coach_summary": "string",
  "user_feedback": [],
  "search_memory": {},
  "cache_run_path": "string or null"
}
```

### 7.3 Graph Routing

Routing examples:

- If resume parsing fails, return to upload state.
- If required preferences are missing, continue coach interview.
- If strategy is not approved, return to strategy review.
- If a query returns weak results and budget remains, route to query repair.
- If job pool exceeds scoring budget, route to triage before scoring.
- If user feedback is submitted, route to memory update.

## 8. UI Requirements: Streamlit v2

Use Streamlit for the first version.

Main UI panels:

1. Resume upload and preview.
2. Chat panel for coach interview.
3. Candidate profile panel.
4. Preference state panel.
5. Search strategy review panel.
6. Search diagnostics panel.
7. Ranked tracker panel.
8. Coach summary panel.
9. Feedback/human review panel.
10. Debug and replay panel.

The UI should support:

- Natural-language chat with the coach.
- Editing structured preference fields.
- Approving or modifying search lanes.
- Running search only after strategy approval.
- Viewing query-level diagnostics.
- Replaying cached runs without API calls.
- Exporting tracker CSV.

## 9. Data Schemas

### 9.1 Candidate Profile

Includes:

- Name.
- Education.
- Current status.
- Experience summary.
- Targetable functions.
- Skills.
- Tools.
- Industries.
- Seniority level.
- Notable achievements.
- Search strengths.
- Search gaps.
- Evidence notes.

### 9.2 Preference State

Includes:

- Primary goal.
- Role/title preferences.
- Acceptable adjacent roles.
- Role families to avoid.
- Location preferences.
- Remote/hybrid/on-site preference.
- Industry preferences.
- Work authorization status.
- Sponsorship timing.
- Seniority preference.
- Exclusions.
- Optimization priority.
- Search budget.

### 9.3 Search Strategy

Includes:

- Strategy summary.
- Job families.
- Query/location pairs.
- Strategy type:
  - target_role
  - adjacent_role
  - broadened_repair
  - sponsorship_probe
- Rationale.
- Confidence.
- Expected tradeoff.

### 9.4 Job Posting

Includes:

- Job ID.
- Title.
- Company.
- Location.
- Description.
- Source.
- Apply URL.
- Date posted.
- Search query.
- Raw data.

### 9.5 Sponsorship Assessment

Includes:

- Job ID.
- Sponsorship risk.
- Evidence.
- Reasoning summary.

### 9.6 Scored Job

Includes:

- Rank.
- Job ID.
- Company.
- Title.
- Location.
- Overall Fit Score.
- Fit sub-scores.
- Sponsorship risk.
- Sponsorship evidence.
- Key matches.
- Key gaps.
- Recommended action.
- Explanation.
- Apply URL.
- Human review label.
- Notes.

## 10. Model And API Requirements

Use:

```text
OPENAI_MODEL=gpt-5.4-nano-2026-03-17
```

Use OpenAI structured outputs for JSON-producing agent calls.

Required environment variables:

```text
OPENAI_API_KEY=
SERPAPI_API_KEY=
OPENAI_MODEL=gpt-5.4-nano-2026-03-17
```

Optional:

```text
MAX_SEARCHES_PER_RUN=8
MAX_JOBS_TO_SCORE=50
```

## 11. Cost Controls

The product must enforce:

- Search budget per run.
- Scoring budget per run.
- Replay mode to avoid repeat API costs.
- Cache for raw SerpApi and LLM outputs.
- Batch LLM scoring.
- Triage before detailed scoring when job volume is high.

## 12. Cache, Replay, And Debugging

Each run should create a local cache folder.

Cache should include:

- Resume text.
- Candidate profile.
- Conversation messages.
- Inferred preferences.
- Search strategy.
- Strategy approval state.
- Query repairs.
- Raw SerpApi results.
- Normalized jobs.
- Deduped jobs.
- Sponsorship assessments.
- Triage decisions.
- Scoring requests and responses.
- Final tracker.
- Coach summary.
- User feedback.
- Graph state snapshot.

Replay mode should load a cached graph state and render the app without SerpApi or OpenAI calls.

## 13. Memory And Feedback

The app should maintain lightweight local memory.

Memory should store:

- Preferred role families.
- Rejected role families.
- Companies or industries to avoid.
- Sponsorship risk sensitivity.
- Seniority calibration.
- Query patterns that produced useful results.
- Query patterns that produced poor results.

For the first version, local JSON memory is acceptable.

## 14. Reuse From Current Codebase

Recommended reuse:

- `resume_parser.py`
- `serpapi_client.py`
- `job_normalizer.py`
- `deduper.py`
- `export.py`
- `cache.py`
- parts of `schemas.py`
- parts of `llm_client.py`

Recommended replacement or heavy redesign:

- `app.py`
- `orchestrator.py`
- current preference form flow
- current tracker-first UX

Do not treat the current implementation as the architecture contract. Treat it as a working reference and source of reusable utilities.

## 15. Non-Goals For First Real Version

The first real version does not need:

- User authentication.
- Cloud database.
- Browser extension.
- Automatic applications.
- Recruiter messaging.
- LinkedIn scraping.
- Production billing.

## 16. Evaluation Plan

Evaluate usefulness, not just technical success.

For each test user/session, answer:

- Did the agent ask good follow-up questions?
- Did the agent infer plausible role families?
- Did the agent challenge narrow or weak goals respectfully?
- Did the strategy proposal make sense?
- Did the search retrieve enough plausible jobs?
- Did the tracker contain jobs the user would actually apply to?
- Did sponsorship reasoning avoid overclaiming?
- Did user feedback improve the next search?

Test scenarios:

1. Vague goal: user says "I want a good tech role."
2. Narrow goal: user only wants PM but resume fits adjacent roles.
3. Sponsorship-sensitive international MBA.
4. Career switcher with unclear target function.
5. User rejects several jobs as too senior or wrong role.
6. User wants remote only but has location-sensitive role goals.

## 17. Implementation Roadmap

### Phase 1: Fork And Foundation

- Duplicate the existing folder.
- Add LangGraph dependencies.
- Keep reusable utilities.
- Create typed graph state.
- Build minimal Streamlit v2 shell with chat and panels.

### Phase 2: Coach Intake

- Resume upload.
- Candidate profile extraction.
- Coach interview.
- Preference state extraction.

### Phase 3: Strategy And Search

- Search strategy proposal.
- Strategy approval UI.
- SerpApi execution.
- Query repair loop.

### Phase 4: Review And Ranking

- Normalize and dedupe.
- Sponsorship assessment.
- Triage.
- Fit scoring.
- Coach summary.

### Phase 5: Feedback And Memory

- Human review labels.
- Feedback learning.
- Updated search strategy from feedback.
- Replay/debug workflow.

## 18. Acceptance Criteria

The product is useful when:

1. User can upload a resume.
2. Agent extracts and explains a candidate profile.
3. Agent asks targeted follow-up questions.
4. Agent creates structured preferences from conversation.
5. Agent proposes search lanes and explains them.
6. User can approve or edit the strategy.
7. Agent retrieves jobs through SerpApi.
8. Agent repairs weak searches when useful.
9. Agent assesses sponsorship risk with evidence.
10. Agent ranks jobs with clear reasoning.
11. User can label jobs and add notes.
12. Agent updates future strategy from feedback.
13. App can replay cached runs without API calls.
14. App exports tracker CSV.

## 19. Handoff Note For New Coding Agent

Start from `career_search_agent_prd.md`, not `job_fit_agent_prd.md`.

The existing app is a useful reference implementation, but the new product should be built around a LangGraph stateful career-coach workflow. Reuse infrastructure selectively. Do not preserve the old form-first, tracker-first flow unless it serves the new agent experience.
