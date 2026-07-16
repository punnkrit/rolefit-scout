# Business Case: Career Coach Search Agent

## Executive Summary

Career Coach Search Agent helps MBA students and early-career professionals turn a resume, career goals, and work authorization constraints into a practical job-search strategy and ranked application tracker. The product combines three jobs that are usually fragmented across career advising, job boards, spreadsheets, and generic chatbots: career coaching, search strategy, and evidence-based job evaluation.

The initial wedge is international MBA students targeting product, strategy, analytics, operations, AI solutions, SaaS, marketplace, and technology-adjacent roles. These users face a high-friction search problem: they often do not know every relevant job title, must evaluate sponsorship risk, and need to decide where to spend limited application time.

The MVP is a local Streamlit/LangGraph prototype. It demonstrates the core business value: the agent interviews the user, builds a structured career brief, proposes search lanes, retrieves jobs, flags sponsorship risk conservatively, scores fit, exports a tracker, and learns from feedback.

## Problem

Job search is not just a retrieval problem. For MBA students and career switchers, the hardest parts are:

- Translating experience into realistic role families.
- Discovering adjacent titles beyond the obvious ones.
- Balancing aspiration with evidence of fit.
- Avoiding search terms that are too narrow or too broad.
- Understanding whether a posting is likely blocked by sponsorship or work authorization language.
- Keeping application decisions organized across many postings.
- Learning from rejected jobs and improving the next search.

International students have an additional burden: sponsorship risk can make an otherwise strong role non-actionable. Existing job boards usually treat this as a weak filter or leave it to the user to infer manually from posting text.

## Target Users

Primary users:

- MBA students and recent MBA graduates.
- International students who need sponsorship now or in the future.
- Career switchers who are unsure which job families match their background.
- Early-career professionals seeking more structured role discovery.

Initial wedge:

- International MBA students seeking product, AI, product strategy, product analytics, business operations, strategy and operations, marketplace, SaaS, or technology-adjacent roles.

Buyer or sponsor possibilities:

- Individual job seekers.
- MBA career centers.
- International student offices.
- Career coaches serving graduate students and early-career professionals.

## Value Proposition

Career Coach Search Agent acts as:

- A career coach that interprets the resume and asks targeted follow-up questions.
- A search analyst that turns goals into practical job-search lanes.
- A sponsorship-aware reviewer that flags work authorization risk conservatively.
- A tracker assistant that ranks jobs, explains fit, and exports decisions.
- A lightweight memory system that learns from Apply, Maybe, Reject, Too Senior, Bad Location, Wrong Role, and Sponsorship Issue feedback.

The product saves time, improves search quality, and makes job-search reasoning more explicit.

## Why Existing Alternatives Are Incomplete

Job boards:

- Strong at listing roles.
- Weak at translating a candidate's background into search strategy.
- Often poor at sponsorship nuance.
- Do not explain role fit against a specific resume and goal.

Generic chatbots:

- Helpful for brainstorming.
- Usually disconnected from live postings, structured state, and tracker workflows.
- Can overclaim fit or sponsorship unless constrained.

Spreadsheets:

- Useful for tracking.
- Do not discover jobs, interpret postings, or learn from feedback.

Career coaches:

- High-value but time-constrained and expensive.
- Often cannot manually inspect large job pools for every student.

Career Coach Search Agent sits between these options: cheaper and more scalable than one-on-one advising, more personalized than job boards, and more operational than a generic chatbot.

## MVP Capabilities

The current prototype supports:

- Resume upload or pasted resume text.
- Coach interview chat.
- Structured candidate profile.
- Editable preference state.
- Career brief with search thesis, target lanes, adjacent lanes, exclusions, sponsorship stance, and readiness.
- Search strategy proposal before spending API calls.
- Search lane edits and approval.
- SerpApi Google Jobs execution.
- Query diagnostics and repair.
- Job normalization and conservative deduplication.
- Sponsorship risk assessment with evidence.
- Job triage and LLM fit scoring.
- Ranked tracker with Apply/Maybe/Skip recommendations.
- Feedback labels and notes.
- Local memory from feedback.
- Cache and replay.
- CSV export.

## Differentiation

The differentiator is not only "AI ranks jobs." The stronger position is:

> A career-search agent that owns the strategy loop before retrieval and the evaluation loop after retrieval.

Key differentiators:

- Resume-aware and conversation-aware search lanes.
- Human approval before search execution.
- Sponsorship risk handled as a first-class constraint.
- Transparent fit dimensions and evidence.
- Feedback memory that changes future strategy.
- Debuggable local cache for every run.

## Success Metrics

Product usefulness metrics:

- Percentage of sessions where users approve or lightly edit the proposed search strategy.
- Percentage of retrieved jobs users label Apply or Maybe.
- Reduction in time to produce a credible application tracker.
- Number of useful adjacent role families discovered per session.
- User-rated quality of coach questions and strategy rationale.
- Sponsorship classification precision for explicit blocker or sponsor-friendly language.
- Improvement in second-run relevance after feedback.

Technical operating metrics:

- Searches per run.
- Live queries with results.
- Deduped jobs per run.
- Jobs scored per run.
- LLM scoring omissions or validation failures.
- Cache replay success rate.
- Cost per useful tracker.

## Business Model Options

Individual subscription:

- Low-cost monthly subscription during active recruiting seasons.
- Best for self-serve MBA students and early-career professionals.

Career center license:

- School or program pays for student access.
- Strong fit for MBA programs, international student offices, and career services teams.

Coach productivity tool:

- Career coaches use it to prepare student-specific search strategies and trackers.
- Could be sold as a workflow assistant rather than a student-facing app.

Freemium wedge:

- Free resume-to-strategy and demo search.
- Paid live searches, scoring, memory, and export.

## Risks And Mitigations

Risk: Sponsorship advice is sensitive.

- Mitigation: label risk conservatively, show evidence, avoid legal claims, and never claim sponsorship availability without explicit posting language.

Risk: Job search APIs can be noisy or incomplete.

- Mitigation: use broad recall-oriented searches, query diagnostics, repair loops, deduplication, and scoring/triage after retrieval.

Risk: LLM scoring may overrate title matches.

- Mitigation: use a strict rubric, require evidence from posting and candidate profile, surface key gaps, and collect user feedback.

Risk: Users may trust recommendations too much.

- Mitigation: keep human review labels, show explanations, and position the product as decision support rather than an application authority.

Risk: API costs can grow.

- Mitigation: enforce search and scoring budgets, use replay mode, cache raw artifacts, and triage before detailed scoring.

## Roadmap

Near term:

- Improve scoring retry for omitted job IDs.
- Add richer feedback persistence to the tracker.
- Add saved search profiles for different career paths.
- Add more evaluation fixtures from realistic job-search sessions.

Medium term:

- Add company-level sponsorship intelligence.
- Add alumni/company relationship signals.
- Add comparison views for search lanes and result quality.
- Add hosted multi-user storage.
- Add career-center dashboards.

Long term:

- Integrate with application tracking systems.
- Support tailored resume bullets and cover-letter drafts after a job is selected.
- Add interview-prep handoff for high-fit roles.
- Build school-specific or cohort-specific role-discovery benchmarks.

## Strategic Takeaway

Career Coach Search Agent is valuable because it addresses the decision layer of job search, not just the listing layer. It helps users answer: "What should I search for, which jobs are worth my time, and why?" For international MBA students and career switchers, that clarity is the difference between browsing job boards and running a focused search campaign.
