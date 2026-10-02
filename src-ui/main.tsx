import React, { FormEvent, useEffect, useMemo, useRef, useState } from "react";
import { createRoot } from "react-dom/client";
import {
  ArrowSquareOut,
  BookmarkSimple,
  Briefcase,
  Check,
  CheckCircle,
  DownloadSimple,
  FileText,
  GithubLogo,
  MagnifyingGlass,
  MapPin,
  PencilSimple,
  Plus,
  SpinnerGap,
  Strategy,
  DotsThreeVertical,
  WarningCircle
} from "@phosphor-icons/react";
import "./styles.css";
import { demoState, freshDemoState } from "./demo";

const API_BASE = import.meta.env.VITE_API_BASE || "";
const STATIC_DEMO = import.meta.env.VITE_STATIC_DEMO === "true";
const SOURCE_URL = "https://github.com/punnkrit/rolefit-scout";
const SHOW_COACH_CHAT = false;

type Step = "resume" | "preferences" | "brief" | "strategy" | "results";

type GraphState = {
  resume_text?: string;
  candidate_profile?: Record<string, any>;
  inferred_preferences?: Preferences;
  career_brief?: CareerBrief;
  open_questions?: string[];
  messages?: ChatMessage[];
  search_strategy?: SearchStrategy;
  approved_strategy?: Record<string, any>;
  query_diagnostics?: QueryDiagnostic[];
  deduped_jobs?: JobPosting[];
  normalized_jobs?: JobPosting[];
  scored_jobs?: ScoredJob[];
  coach_summary?: string;
  user_feedback?: Record<string, any>[];
  cache_run_id?: string;
  cache_run_label?: string;
  cache_run_path?: string;
  demo_mode?: boolean;
  live_search_enabled?: boolean;
  conversation_updated?: boolean;
  errors?: string[];
  run_trace?: Record<string, any>[];
};

type Preferences = {
  primary_goal?: string;
  target_job_titles?: string[];
  acceptable_adjacent_roles?: string[];
  role_families_to_avoid?: string[];
  preferred_locations?: string[];
  remote_preference?: "remote" | "hybrid" | "onsite" | "any";
  target_industries?: string[];
  requires_sponsorship?: boolean;
  sponsorship_timing?: "now" | "future" | "not_needed" | "unknown";
  max_searches?: number;
};

type CareerBrief = {
  positioning?: string;
  search_thesis?: string;
  target_role_lanes?: string[];
  adjacent_role_lanes?: string[];
  excluded_lanes?: string[];
  target_industries?: string[];
  location_scope?: string[];
  sponsorship_stance?: string;
  seniority_calibration?: string;
  scoring_guidance?: string;
  unresolved_questions?: string[];
  readiness?: "needs_more_info" | "ready_to_search";
  confidence?: number;
};

type SearchQuery = {
  query: string;
  location?: string | null;
  rationale?: string;
  expected_tradeoff?: string;
  priority?: number;
  job_family?: string;
  strategy_type?: string;
  confidence?: number;
};

type SearchStrategy = {
  strategy_summary?: string;
  job_families?: string[];
  queries?: SearchQuery[];
};

type ScoredJob = {
  rank: number;
  job_id: string;
  company: string;
  title: string;
  location: string;
  overall_fit_score: number;
  recommended_action: "Apply" | "Maybe" | "Skip";
  sponsorship_risk: string;
  sponsorship_evidence?: string;
  key_matches: string[];
  key_gaps: string[];
  explanation: string;
  job_description?: string;
  role_summary?: string;
  responsibilities?: string[];
  qualifications?: string[];
  company_insights?: string[];
  url?: string | null;
  role_fit: number;
  skill_fit: number;
  experience_fit: number;
  location_fit: number;
  industry_fit: number;
  sponsorship_fit: number;
  search_query?: string;
  source?: string;
  date_posted?: string | null;
};

type JobPosting = {
  job_id: string;
  company: string;
  title: string;
  location: string;
  description?: string;
  source?: string;
  url?: string | null;
  date_posted?: string | null;
  search_query?: string;
};

type QueryDiagnostic = {
  query: string;
  location?: string | null;
  result_count?: number;
  repaired?: boolean;
  error?: string;
};

type ChatMessage = { role: "user" | "assistant" | "system"; content: string };

const LOCATION_OPTIONS = [
  "United States",
  "California, United States",
  "New York, United States",
  "Oregon, United States",
  "Washington, United States",
  "Texas, United States",
  "Illinois, United States",
  "Massachusetts, United States",
  "Washington, DC",
  "New York, NY",
  "Los Angeles, CA",
  "San Francisco, CA",
  "San Jose, CA",
  "Seattle, WA",
  "Austin, TX",
  "Chicago, IL",
  "Boston, MA",
  "Portland, OR",
  "Denver, CO",
  "Atlanta, GA",
  "Dallas, TX",
  "Houston, TX",
  "Miami, FL",
  "Philadelphia, PA",
  "Phoenix, AZ",
  "San Diego, CA",
  "Charlotte, NC",
  "Raleigh, NC",
  "Minneapolis, MN"
];

const EMPTY_PREFS: Preferences = {
  primary_goal: "",
  target_job_titles: [],
  acceptable_adjacent_roles: [],
  role_families_to_avoid: [],
  preferred_locations: [],
  remote_preference: "any",
  target_industries: [],
  requires_sponsorship: true,
  sponsorship_timing: "future",
  max_searches: 8
};

function App() {
  const [state, setState] = useState<GraphState>(() => loadLocalState());
  const [step, setStep] = useState<Step>(() => STATIC_DEMO ? "results" : "resume");
  const [busy, setBusy] = useState("");
  const [error, setError] = useState("");
  const [health, setHealth] = useState<Record<string, any> | null>(null);

  useEffect(() => {
    document.title = STATIC_DEMO ? "RoleFit Scout · Interactive Demo" : "RoleFit Scout";
  }, []);

  useEffect(() => {
    api<Record<string, any>>("/api/health").then(setHealth).catch(() => setHealth(null));
  }, []);

  useEffect(() => {
    localStorage.setItem("career-search-state", JSON.stringify(state));
  }, [state]);

  const complete = useMemo(() => ({
    resume: Boolean(state.candidate_profile),
    preferences: hasPreferences(state.inferred_preferences),
    brief: hasPreferences(state.inferred_preferences) && hasMeaningfulBrief(state.career_brief),
    strategy: hasMeaningfulBrief(state.career_brief) && Boolean(state.search_strategy?.queries?.length),
    results: Boolean(state.scored_jobs?.length)
  }), [state]);

  async function run<T>(label: string, action: () => Promise<T>, onDone: (value: T) => void, next?: Step) {
    setBusy(label);
    setError("");
    try {
      const value = await action();
      onDone(value);
      if (next) setStep(next);
    } catch (err) {
      setError(err instanceof Error ? err.message : "Request failed.");
    } finally {
      setBusy("");
    }
  }

  return (
    <div className="app-shell">
      <a className="skip-link" href="#main">Skip to content</a>
      <header className="topbar">
        <div>
          <h1>RoleFit Scout</h1>
        </div>
        <div className="status-cluster">
          {STATIC_DEMO ? <span className="demo-badge">Demo mode</span> : <>
            <Toggle label="Demo" checked={Boolean(state.demo_mode)} onChange={(demo_mode) => setState({ ...state, demo_mode })} />
            <Toggle
              label="Live search"
              checked={state.live_search_enabled !== false}
              onChange={(live_search_enabled) => setState({ ...state, live_search_enabled })}
            />
            <div className="keys">
              <span>OpenAI {health?.openai_configured ? "ready" : "missing"}</span>
              <span>SerpApi {health?.serpapi_configured ? "ready" : "missing"}</span>
            </div>
          </>}
          <a className="source-link" href={SOURCE_URL} target="_blank" rel="noreferrer">
            <GithubLogo size={18} weight="fill" /> GitHub source <ArrowSquareOut size={15} />
          </a>
        </div>
      </header>

      {STATIC_DEMO && <section className="demo-notice" aria-labelledby="demo-title">
        <div>
          <h2 id="demo-title">Interactive demo</h2>
          <p>Fictional data. No live searches or AI analysis.</p>
        </div>
        <div className="demo-deploy">
          <a href={`${SOURCE_URL}#deploy-the-live-version`} target="_blank" rel="noreferrer">Deploy the live version <ArrowSquareOut size={17} /></a>
        </div>
      </section>}

      <nav className="workflow" aria-labelledby="workflow-title">
        <div className="workflow-heading">
          <h2 id="workflow-title">Your job-search workflow</h2>
          <span>Step {(["resume", "preferences", "brief", "strategy", "results"] as Step[]).indexOf(step) + 1} of 5</span>
        </div>
        {STATIC_DEMO && <p className="workflow-context">
          {complete.strategy
            ? "This fictional candidate is already set up. Review the completed steps or explore the sample matches."
            : "Explore the five-step workflow using the fictional candidate."}
        </p>}
        <ol className="workflow-steps">
        {([
          ["resume", "Resume", STATIC_DEMO ? "Sample resume loaded" : "Profile extracted", "Add your resume"],
          ["preferences", "Preferences", "Preferences set", "Set your preferences"],
          ["brief", "Coach brief", STATIC_DEMO ? "Sample brief ready" : "Brief ready", "Review your brief"],
          ["strategy", "Strategy", "Search plan ready", "Build your search plan"],
          ["results", "Results", STATIC_DEMO ? "Sample matches ready" : `${state.scored_jobs?.length || 0} matches ready`, "Run your search"]
        ] as const).map(([key, label, readyLabel, pendingLabel], index) => {
          const locked = key !== "resume" && !isUnlocked(key, complete);
          const status = complete[key] ? readyLabel : pendingLabel;
          return (
            <li key={key} className={complete[key] ? "complete" : ""}>
              <button className={step === key ? "active" : ""} aria-label={`Step ${index + 1}: ${label}. ${status}${complete[key] ? ". Completed" : ""}`} aria-current={step === key ? "step" : undefined} disabled={locked} onClick={() => setStep(key)}>
                <span className="workflow-number" aria-hidden="true">{index + 1}</span>
                <span className="workflow-copy">
                  <span className="workflow-label">{label}</span>
                  <span className="workflow-status">{complete[key] && <Check size={13} weight="bold" aria-hidden="true" />}{status}</span>
                </span>
              </button>
              {index < 4 && <span className="workflow-connector" aria-hidden="true">›</span>}
            </li>
          );
        })}
        </ol>
      </nav>

      <main id="main" className={step === "results" ? "main-grid results-main" : "main-grid"}>
        <aside className="briefing-panel">
          <Progress state={state} complete={complete} onStartOver={() => {
            localStorage.removeItem("career-search-state");
            setState(STATIC_DEMO ? { demo_mode: true, live_search_enabled: false } : {});
            setStep("resume");
          }} />
          <Replay onLoad={(loaded) => setState(loaded)} />
        </aside>

        <section className="workspace">
          {error ? <Notice tone="danger" text={error} /> : null}
          {state.errors?.length ? <Notice tone="warn" text={state.errors[state.errors.length - 1]} /> : null}
          {busy ? <Loading label={busy} /> : null}
          {step === "resume" && (
            <ResumeStep
              state={state}
              onState={setState}
              onExtract={() => run("Extracting resume profile", () => api<GraphState>("/api/profile", { state }), setState)}
              onContinue={() => setStep("preferences")}
            />
          )}
          {step === "preferences" && (
            <PreferencesStep
              state={state}
              onSave={(preferences) =>
                run("Saving preferences and generating coach brief", () => savePreferencesAndBrief(state, preferences), setState, "brief")
              }
            />
          )}
          {step === "brief" && (
            <BriefStep
              state={state}
              coachThinking={busy === "Coach is thinking"}
              onGenerate={() => run("Generating coach brief", () => api<GraphState>("/api/coach-brief", { state }), setState)}
              onApply={(career_brief) =>
                run("Applying coach brief", () => api<GraphState>("/api/coach-brief/apply", { state, career_brief }), setState, "strategy")
              }
              onChat={(message) => {
                setState({
                  ...state,
                  messages: [...(state.messages || []), { role: "user", content: message }],
                  conversation_updated: true
                });
                run("Coach is thinking", () => api<GraphState>("/api/coach-chat", { state, message }), setState);
              }}
            />
          )}
          {step === "strategy" && (
            <StrategyStep
              state={state}
              onBuild={() => run("Building strategy", () => api<GraphState>("/api/strategy", { state }), setState)}
              onSearch={(queries) => run("Running approved search", () => api<GraphState>("/api/search", { state, queries }), setState, "results")}
            />
          )}
          {step === "results" && <ResultsStep state={state} onState={setState} />}
        </section>
      </main>
    </div>
  );
}

function ResumeStep({ state, onState, onExtract, onContinue }: {
  state: GraphState;
  onState: (state: GraphState) => void;
  onExtract: () => void;
  onContinue: () => void;
}) {
  const [text, setText] = useState(state.resume_text || "");
  const [dragActive, setDragActive] = useState(false);

  useEffect(() => {
    setText(state.resume_text || "");
  }, [state.resume_text]);

  async function upload(file: File) {
    if (STATIC_DEMO) {
      if (!file.name.toLowerCase().endsWith(".txt")) {
        throw new Error("The hosted demo accepts pasted text or .txt files. PDF and DOCX parsing requires the private API.");
      }
      const resumeText = await file.text();
      setText(resumeText);
      onState({ ...state, resume_text: resumeText });
      return;
    }
    const form = new FormData();
    form.append("upload", file);
    const response = await fetch(`${API_BASE}/api/resume/parse`, { method: "POST", body: form, credentials: "include" });
    if (!response.ok) throw new Error(await errorText(response));
    const payload = await response.json();
    setText(payload.resume_text);
    onState({ ...state, resume_text: payload.resume_text });
  }

  function handleDrop(event: React.DragEvent<HTMLLabelElement>) {
    event.preventDefault();
    setDragActive(false);
    const file = event.dataTransfer.files?.[0];
    if (file) upload(file);
  }

  return (
    <div className="two-column">
      <section className="panel">
        <h2>Resume intake</h2>
        <label
          className={dragActive ? "dropzone drag-active" : "dropzone"}
          onDragEnter={(event) => {
            event.preventDefault();
            setDragActive(true);
          }}
          onDragOver={(event) => {
            event.preventDefault();
            event.dataTransfer.dropEffect = "copy";
            setDragActive(true);
          }}
          onDragLeave={(event) => {
            event.preventDefault();
            if (event.currentTarget === event.target) setDragActive(false);
          }}
          onDrop={handleDrop}
        >
          <FileText size={30} />
          <span>{dragActive ? "Drop resume to upload" : "Drop resume here or browse files"}</span>
          <small>{STATIC_DEMO ? "TXT only in this demo" : "PDF, DOCX, or TXT"}</small>
          <input type="file" accept={STATIC_DEMO ? ".txt" : ".pdf,.docx,.txt"} onChange={(event) => event.target.files?.[0] && upload(event.target.files[0])} />
        </label>
        <textarea
          value={text}
          onChange={(event) => {
            setText(event.target.value);
            onState({ ...state, resume_text: event.target.value });
          }}
          placeholder="Paste resume text here..."
          aria-label={STATIC_DEMO ? "Sample resume text" : "Resume text"}
          rows={14}
        />
        <button className="primary" disabled={!text.trim()} onClick={onExtract}>{STATIC_DEMO ? "Load sample profile" : "Extract resume profile"}</button>
      </section>
      <ProfilePanel profile={state.candidate_profile} onContinue={onContinue} />
    </div>
  );
}

function PreferencesStep({ state, onSave }: { state: GraphState; onSave: (preferences: Preferences) => void }) {
  const [prefs, setPrefs] = useState<Preferences>({ ...EMPTY_PREFS, ...(state.inferred_preferences || {}) });
  const [anyMode, setAnyMode] = useState({
    primary_goal: !(state.inferred_preferences?.primary_goal || "").trim(),
    target_job_titles: !(state.inferred_preferences?.target_job_titles || []).length,
    acceptable_adjacent_roles: !(state.inferred_preferences?.acceptable_adjacent_roles || []).length,
    target_industries: !(state.inferred_preferences?.target_industries || []).length,
  });
  const canProceed = anyMode.primary_goal || Boolean((prefs.primary_goal || "").trim());
  const canProceedTargets = anyMode.target_job_titles || Boolean((prefs.target_job_titles || []).length);
  const canProceedAdjacent = anyMode.acceptable_adjacent_roles || Boolean((prefs.acceptable_adjacent_roles || []).length);
  const canProceedIndustries = anyMode.target_industries || Boolean((prefs.target_industries || []).length);
  const formReady = canProceed && canProceedTargets && canProceedAdjacent && canProceedIndustries;
  return (
    <section className="panel spacious">
      <h2>Search constraints</h2>
      <div className="form-grid">
        <AnyTextField
          label="Primary goal"
          value={prefs.primary_goal || ""}
          placeholder="Type your preference here"
          anyMode={anyMode.primary_goal}
          onAnyMode={(primary_goal) => setAnyMode({ ...anyMode, primary_goal })}
          onChange={(primary_goal) => setPrefs({ ...prefs, primary_goal })}
        />
        <AnyListField
          label="Target titles"
          values={prefs.target_job_titles}
          placeholder="Type your preference here"
          anyMode={anyMode.target_job_titles}
          onAnyMode={(target_job_titles) => setAnyMode({ ...anyMode, target_job_titles })}
          onChange={(target_job_titles) => setPrefs({ ...prefs, target_job_titles })}
        />
        <AnyListField
          label="Adjacent lanes"
          values={prefs.acceptable_adjacent_roles}
          placeholder="Type your preference here"
          anyMode={anyMode.acceptable_adjacent_roles}
          onAnyMode={(acceptable_adjacent_roles) => setAnyMode({ ...anyMode, acceptable_adjacent_roles })}
          onChange={(acceptable_adjacent_roles) => setPrefs({ ...prefs, acceptable_adjacent_roles })}
        />
        <AnyListField
          label="Industries"
          values={prefs.target_industries}
          placeholder="Type your preference here"
          anyMode={anyMode.target_industries}
          onAnyMode={(target_industries) => setAnyMode({ ...anyMode, target_industries })}
          onChange={(target_industries) => setPrefs({ ...prefs, target_industries })}
        />
      </div>
      <Field label="Locations">
        <SearchableMultiSelect
          options={LOCATION_OPTIONS}
          values={prefs.preferred_locations || []}
          placeholder="Search cities, states, or choose United States"
          onChange={(preferred_locations) => setPrefs({ ...prefs, preferred_locations })}
        />
      </Field>
      <div className="form-grid compact">
        <Segmented
          label="Remote"
          value={prefs.remote_preference || "any"}
          options={[["any", "Any"], ["hybrid", "Hybrid"], ["remote", "Remote"], ["onsite", "On-site"]]}
          onChange={(remote_preference) => setPrefs({ ...prefs, remote_preference: remote_preference as Preferences["remote_preference"] })}
        />
        <Segmented
          label="Sponsorship"
          value={sponsorshipValue(prefs)}
          options={[["future", "Future"], ["now", "Now"], ["not_needed", "Not needed"], ["unknown", "Either"]]}
          onChange={(value) => setPrefs({ ...prefs, requires_sponsorship: value !== "not_needed" && value !== "unknown", sponsorship_timing: value as Preferences["sponsorship_timing"] })}
        />
      </div>
      <Field label="Hard exclusions">
        <textarea value={join(prefs.role_families_to_avoid)} onChange={(e) => setPrefs({ ...prefs, role_families_to_avoid: split(e.target.value) })} rows={3} placeholder="Workforce optimization, dispatch operations" />
      </Field>
      {!formReady ? <p className="validation-note">Choose Any for flexible fields, or type a preference before continuing.</p> : null}
      <button className="primary" disabled={!formReady} onClick={() => onSave({
        ...prefs,
        primary_goal: anyMode.primary_goal ? "" : prefs.primary_goal,
        target_job_titles: anyMode.target_job_titles ? [] : prefs.target_job_titles,
        acceptable_adjacent_roles: anyMode.acceptable_adjacent_roles ? [] : prefs.acceptable_adjacent_roles,
        target_industries: anyMode.target_industries ? [] : prefs.target_industries,
      })}>Save and continue</button>
    </section>
  );
}

function BriefStep({ state, coachThinking, onGenerate, onApply, onChat }: {
  state: GraphState;
  coachThinking: boolean;
  onGenerate: () => void;
  onApply: (brief: CareerBrief) => void;
  onChat: (message: string) => void;
}) {
  const [brief, setBrief] = useState<CareerBrief>(state.career_brief || {});
  const [message, setMessage] = useState("");

  useEffect(() => setBrief(state.career_brief || {}), [state.career_brief]);

  if (!hasMeaningfulBrief(state.career_brief)) {
    return (
      <section className="panel empty-state">
        <PencilSimple size={38} />
        <h2>{STATIC_DEMO ? "Explore a sample brief" : "Generate the coach brief"}</h2>
        {!STATIC_DEMO && <p>The brief turns the resume and constraints into role lanes, scoring guidance, and unresolved questions.</p>}
        <button className="primary" onClick={onGenerate}>{STATIC_DEMO ? "Load sample brief" : "Generate coach brief"}</button>
      </section>
    );
  }

  return (
    <div className={SHOW_COACH_CHAT ? "two-column wide-left" : "brief-single"}>
      <section className="panel spacious">
        <h2>Role search brief</h2>
        <div className="coach-readout">
          <div>
            <h3>Search focus</h3>
            <p>{brief.search_thesis || brief.positioning}</p>
          </div>
          <div>
            <h3>Target roles</h3>
            <div className="readout-chips">
              {(brief.target_role_lanes || []).map((item) => <b key={item}>{item}</b>)}
              {!(brief.target_role_lanes || []).length ? <b>Coach is still calibrating</b> : null}
            </div>
          </div>
          <div>
            <h3>Sponsorship and level</h3>
            <p>{[brief.sponsorship_stance, brief.seniority_calibration].filter(Boolean).join(" · ") || "No special constraint captured yet."}</p>
          </div>
        </div>
        <div className="edit-stack">
          <details>
            <summary>Edit narrative</summary>
            <Field label="Candidate positioning">
              <textarea value={brief.positioning || ""} onChange={(e) => setBrief({ ...brief, positioning: e.target.value })} rows={4} />
            </Field>
            <Field label="Search thesis">
              <textarea value={brief.search_thesis || ""} onChange={(e) => setBrief({ ...brief, search_thesis: e.target.value })} rows={4} />
            </Field>
          </details>
          <details>
            <summary>Edit role lanes</summary>
            <div className="form-grid">
              <Field label="Primary lanes">
                <textarea value={join(brief.target_role_lanes)} onChange={(e) => setBrief({ ...brief, target_role_lanes: split(e.target.value) })} rows={3} />
              </Field>
              <Field label="Adjacent lanes">
                <textarea value={join(brief.adjacent_role_lanes)} onChange={(e) => setBrief({ ...brief, adjacent_role_lanes: split(e.target.value) })} rows={3} />
              </Field>
            </div>
          </details>
          <details>
            <summary>Edit scoring</summary>
            <Field label="Scoring guidance">
              <textarea value={brief.scoring_guidance || ""} onChange={(e) => setBrief({ ...brief, scoring_guidance: e.target.value })} rows={5} />
            </Field>
          </details>
        </div>
        <button className="primary" onClick={() => onApply(brief)}>Apply brief</button>
      </section>
      {SHOW_COACH_CHAT ? <aside className="panel chat-panel">
        <div className="chat-head">
          <h3>Coach chat</h3>
          <span>{coachThinking ? "Replying..." : "Ready"}</span>
        </div>
        <div className="messages">
          <CoachQuestionBubble questions={state.open_questions || brief.unresolved_questions || []} />
          {chatMessagesForDisplay(state.messages || [], state.open_questions || brief.unresolved_questions || []).map((item, index) => (
            <div className={`message ${item.role}`} key={`${item.role}-${index}`}>
              <ChatText text={item.content} />
            </div>
          ))}
          {coachThinking ? <div className="message assistant thinking"><span />Coach is thinking</div> : null}
        </div>
        <form onSubmit={(event) => {
          event.preventDefault();
          if (message.trim()) {
            onChat(message.trim());
            setMessage("");
          }
        }}>
          <input value={message} onChange={(e) => setMessage(e.target.value)} placeholder="Message the coach..." />
        </form>
      </aside> : null}
    </div>
  );
}

function StrategyStep({ state, onBuild, onSearch }: { state: GraphState; onBuild: () => void; onSearch: (queries: SearchQuery[]) => void }) {
  const [laneText, setLaneText] = useState("");
  const queries = state.search_strategy?.queries || [];
  useEffect(() => {
    setLaneText(queries.map((query) => `${query.query} | ${query.location || ""}`).join("\n"));
  }, [state.search_strategy]);

  if (!queries.length) {
    return (
      <section className="panel empty-state">
        <Strategy size={38} />
        <h2>{STATIC_DEMO ? "Explore a sample strategy" : "Build the search strategy"}</h2>
        {!STATIC_DEMO && <p>Propose search queries using the approved coach brief and preferences.</p>}
        <button className="primary" onClick={onBuild}>{STATIC_DEMO ? "Load sample strategy" : "Build search strategy"}</button>
      </section>
    );
  }

  const edited = parseLanes(laneText, queries);
  return (
    <section className="panel spacious">
      <div className="section-head">
        <div>
          <h2>Search strategy</h2>
          <p>{state.search_strategy?.strategy_summary}</p>
        </div>
        <button className="primary" onClick={() => onSearch(edited)}><MagnifyingGlass size={18} /> {STATIC_DEMO ? "Show sample results" : "Run approved search"}</button>
      </div>
      <div className="lane-grid">
        {queries.map((query, index) => (
          <article className="lane-card" key={`${query.query}-${index}`}>
            <span>{formatStrategyType(query.strategy_type)}</span>
            <h3>{query.query}</h3>
            <p>{query.location || "Any supported location"}</p>
            <small>{query.rationale || query.expected_tradeoff}</small>
          </article>
        ))}
      </div>
      <Field label="Edit lanes: one query | location per line">
        <textarea value={laneText} onChange={(e) => setLaneText(e.target.value)} rows={Math.max(5, queries.length + 1)} />
      </Field>
      <Diagnostics diagnostics={state.query_diagnostics || []} />
    </section>
  );
}

function ResultsStep({ state, onState }: { state: GraphState; onState: (state: GraphState) => void }) {
  const allJobs = useMemo(() => hydrateScoredJobs(state), [state]);
  const [query, setQuery] = useState("");
  const [minScore, setMinScore] = useState(60);
  const [location, setLocation] = useState("all");
  const [action, setAction] = useState("all");
  const [sortBy, setSortBy] = useState("score");
  const [page, setPage] = useState(1);
  const [selectedId, setSelectedId] = useState(allJobs[0]?.job_id || "");
  const [tab, setTab] = useState("fit");
  const [trackerIds, setTrackerIds] = useState<Set<string>>(() => new Set((state.user_feedback || []).map((item) => item.job_id).filter(Boolean)));
  const [trackerStages, setTrackerStages] = useState<Record<string, string>>({});
  const pageSize = 5;

  const locations = useMemo(() => unique(allJobs.map((job) => job.location).filter(Boolean)), [allJobs]);
  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    return allJobs
      .filter((job) => job.overall_fit_score >= minScore)
      .filter((job) => action === "all" || job.recommended_action === action)
      .filter((job) => location === "all" || job.location === location)
      .filter((job) => !needle || `${job.title} ${job.company} ${job.location}`.toLowerCase().includes(needle))
      .sort((a, b) => sortJobs(a, b, sortBy));
  }, [allJobs, minScore, action, location, query, sortBy]);
  const totalPages = Math.max(1, Math.ceil(filtered.length / pageSize));
  const safePage = Math.min(page, totalPages);
  const pageJobs = filtered.slice((safePage - 1) * pageSize, safePage * pageSize);
  const selected = filtered.find((job) => job.job_id === selectedId) || pageJobs[0] || filtered[0];

  useEffect(() => {
    setPage(1);
  }, [query, minScore, action, location, sortBy]);

  useEffect(() => {
    if (selected && selected.job_id !== selectedId) setSelectedId(selected.job_id);
  }, [selected, selectedId]);

  async function addToTracker(job: ScoredJob) {
    if (trackerIds.has(job.job_id)) return;
    const previousIds = new Set(trackerIds);
    setTrackerIds(new Set([...trackerIds, job.job_id]));
    setTrackerStages((stages) => ({ ...stages, [job.job_id]: stages[job.job_id] || "Saved" }));
    const feedback = {
      job_id: job.job_id,
      label: job.recommended_action === "Skip" ? "Maybe" : job.recommended_action,
      notes: "Added to application tracker from Results.",
      role_family: job.search_query || "",
      company: job.company,
      query: job.search_query || "",
    };
    try {
      const updated = await api<GraphState>("/api/feedback", { state, feedback });
      onState(updated);
    } catch (error) {
      setTrackerIds(previousIds);
      console.error(error);
    }
  }

  return (
    <section className="results-workbench">
      <aside className="panel result-filters">
        <div className="filter-head">
          <h3>Filters</h3>
          <button type="button" onClick={() => {
            setQuery("");
            setMinScore(60);
            setLocation("all");
            setAction("all");
            setSortBy("score");
          }}>Clear all</button>
        </div>
        <div className="search-box">
          <MagnifyingGlass size={18} />
          <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search roles or companies" />
        </div>
        <label className="range-filter">
          <span>Match score</span>
          <input type="range" min={0} max={100} value={minScore} onChange={(event) => setMinScore(Number(event.target.value))} />
          <b>{minScore}%</b>
        </label>
        <Field label="Location">
          <select value={location} onChange={(event) => setLocation(event.target.value)}>
            <option value="all">All locations</option>
            {locations.map((item) => <option key={item} value={item}>{item}</option>)}
          </select>
        </Field>
        <Field label="Recommended action">
          <select value={action} onChange={(event) => setAction(event.target.value)}>
            <option value="all">All actions</option>
            <option value="Apply">Apply</option>
            <option value="Maybe">Maybe</option>
            <option value="Skip">Skip</option>
          </select>
        </Field>
        <button className="secondary" onClick={() => downloadCsv(state)}><DownloadSimple size={18} /> Export CSV</button>
      </aside>

      <section className="panel match-list-panel">
        <div className="matches-head">
          <h3>{filtered.length} {STATIC_DEMO ? "sample matches" : "matches"}</h3>
          <label>Sort by
            <select value={sortBy} onChange={(event) => setSortBy(event.target.value)}>
              <option value="score">Match score</option>
              <option value="company">Company</option>
              <option value="action">Action</option>
            </select>
          </label>
        </div>
        {pageJobs.length ? (
          <div className="match-list">
            {pageJobs.map((job) => (
              <button
                type="button"
                className={selected?.job_id === job.job_id ? "match-row selected" : "match-row"}
                key={job.job_id}
                onClick={() => setSelectedId(job.job_id)}
              >
                <span className="row-rank">{job.rank || filtered.indexOf(job) + 1}</span>
                <CompanyMark name={job.company} />
                <span className="row-copy">
                  <b>{job.title}</b>
                  <small>{job.company}</small>
                  <em><MapPin size={14} />{job.location}</em>
                </span>
                <span className="row-score">
                  <b>{job.overall_fit_score}%</b>
                  <small>{matchLabel(job.overall_fit_score)}</small>
                </span>
              </button>
            ))}
          </div>
        ) : (
          <div className="empty-state compact-empty"><Briefcase size={34} /><h2>No matches</h2><p>Adjust filters or rerun search with broader lanes.</p></div>
        )}
        <div className="pagination">
          <button className="secondary" disabled={safePage <= 1} onClick={() => setPage(safePage - 1)}>Previous</button>
          <span>{safePage} / {totalPages}</span>
          <button className="secondary" disabled={safePage >= totalPages} onClick={() => setPage(safePage + 1)}>Next</button>
        </div>
      </section>

      <section className="panel job-detail-panel">
        {selected ? (
          <>
            <div className="detail-hero">
              <CompanyMark name={selected.company} large />
              <div>
                <h2>{selected.title}</h2>
                <p>{selected.company}</p>
                <span><MapPin size={16} /> {selected.location}</span>
              </div>
              <div className="detail-score">
                <strong>{selected.overall_fit_score}%</strong>
                <span>{matchLabel(selected.overall_fit_score)}</span>
              </div>
            </div>
            <div className="detail-actions">
              {selected.url ? <a className="secondary" href={selected.url} target="_blank" rel="noreferrer">View job <ArrowSquareOut size={17} /></a> : <button className="secondary" disabled>View job</button>}
              <button className="secondary" onClick={() => {
                setTrackerIds(new Set([...trackerIds, selected.job_id]));
                setTrackerStages((stages) => ({ ...stages, [selected.job_id]: stages[selected.job_id] || "Saved" }));
              }}><BookmarkSimple size={17} /> Save</button>
              <button className="secondary"><DotsThreeVertical size={18} /></button>
            </div>
            <div className="detail-tabs">
              {[
                ["fit", "Match fit"],
                ["role", "Role details"],
                ["company", "Company insights"],
              ].map(([key, label]) => <button key={key} className={tab === key ? "active" : ""} onClick={() => setTab(key)}>{label}</button>)}
            </div>
            <JobDetailTab job={selected} tab={tab} />
            <div className="detail-footer">
              <button className="primary" disabled={trackerIds.has(selected.job_id)} onClick={() => addToTracker(selected)}>
                <Plus size={18} /> {trackerIds.has(selected.job_id) ? "Added to tracker" : "Add to application tracker"}
              </button>
            </div>
          </>
        ) : (
          <div className="empty-state compact-empty"><Briefcase size={34} /><h2>No job selected</h2><p>Select a match to inspect fit evidence.</p></div>
        )}
      </section>
      <TrackerPanel
        jobs={allJobs.filter((job) => trackerIds.has(job.job_id))}
        stages={trackerStages}
        onStageChange={(jobId, stage) => setTrackerStages((stages) => ({ ...stages, [jobId]: stage }))}
        onRemove={(jobId) => {
          setTrackerIds(new Set([...trackerIds].filter((id) => id !== jobId)));
          setTrackerStages((stages) => {
            const next = { ...stages };
            delete next[jobId];
            return next;
          });
        }}
        onSelect={(job) => {
          setSelectedId(job.job_id);
          setTab("fit");
        }}
      />
    </section>
  );
}

function CompanyMark({ name, large = false }: { name: string; large?: boolean }) {
  const initial = (name.match(/[A-Za-z0-9]/)?.[0] || "J").toUpperCase();
  return <span className={large ? "company-mark large" : "company-mark"}>{initial}</span>;
}

function hydrateScoredJobs(state: GraphState): ScoredJob[] {
  const postingById = new Map<string, JobPosting>();
  [...(state.deduped_jobs || []), ...(state.normalized_jobs || [])].forEach((job) => {
    if (job?.job_id) postingById.set(job.job_id, job);
  });
  return (state.scored_jobs || []).map((job) => {
    const posting = postingById.get(job.job_id);
    if (!posting) return job;
    return {
      ...job,
      job_description: job.job_description || posting.description || "",
      source: job.source || posting.source || "",
      date_posted: job.date_posted || posting.date_posted || null,
      url: job.url || posting.url || null,
      search_query: job.search_query || posting.search_query || "",
    };
  });
}

function TrackerPanel({
  jobs,
  stages,
  onStageChange,
  onRemove,
  onSelect,
}: {
  jobs: ScoredJob[];
  stages: Record<string, string>;
  onStageChange: (jobId: string, stage: string) => void;
  onRemove: (jobId: string) => void;
  onSelect: (job: ScoredJob) => void;
}) {
  const stageOptions = ["Saved", "Applying", "Applied", "Interviewing", "Archived"];
  return (
    <section className="panel tracker-panel">
      <div className="tracker-head">
        <div>
          <p className="eyebrow">Pipeline</p>
          <h3>Application tracker</h3>
        </div>
        <span>{jobs.length} saved</span>
      </div>
      {jobs.length ? (
        <div className="tracker-table">
          {jobs.map((job) => (
            <article key={job.job_id} className="tracker-row">
              <button type="button" onClick={() => onSelect(job)}>
                <b>{job.title}</b>
                <span>{job.company} · {job.location}</span>
              </button>
              <strong>{job.overall_fit_score}%</strong>
              <select value={stages[job.job_id] || "Saved"} onChange={(event) => onStageChange(job.job_id, event.target.value)}>
                {stageOptions.map((stage) => <option key={stage} value={stage}>{stage}</option>)}
              </select>
              {job.url ? <a className="secondary" href={job.url} target="_blank" rel="noreferrer">Open <ArrowSquareOut size={15} /></a> : <button className="secondary" disabled>Open</button>}
              <button type="button" className="secondary" onClick={() => onRemove(job.job_id)}>Remove</button>
            </article>
          ))}
        </div>
      ) : (
        <div className="tracker-empty">Add roles from the detail panel to build a working application list.</div>
      )}
    </section>
  );
}

function JobDetailTab({ job, tab }: { job: ScoredJob; tab: string }) {
  if (tab === "role") {
    const description = cleanPostingText(job.job_description || "");
    const paragraphs = formatPostingParagraphs(description);
    return (
      <div className="detail-body">
        <h3>Role details</h3>
        <div className="job-description">
          {job.role_summary ? <p>{job.role_summary}</p> : null}
          <DescriptionList title="Responsibilities" items={job.responsibilities || []} />
          <DescriptionList title="Qualifications" items={job.qualifications || []} />
          {description ? (
            <section>
              <h4>Job description</h4>
              {paragraphs.map((paragraph) => <p key={paragraph}>{paragraph}</p>)}
            </section>
          ) : (
            <p className="muted-copy">No job description text was returned by the search provider for this role. Open the job link to review the original posting.</p>
          )}
        </div>
        <dl className="detail-facts">
          <div><dt>Recommended action</dt><dd>{job.recommended_action}</dd></div>
          <div><dt>Search lane</dt><dd>{job.search_query || "Not recorded"}</dd></div>
          <div><dt>Source</dt><dd>{job.source || "Google Jobs"}</dd></div>
          <div><dt>Date posted</dt><dd>{job.date_posted || "Not listed"}</dd></div>
        </dl>
      </div>
    );
  }
  if (tab === "company") {
    const insights = (job.company_insights || []).filter(Boolean);
    const fallbackInsights = insights.length ? insights : extractCompanyInsights(job);
    return (
      <div className="detail-body">
        <h3>Company insights</h3>
        {fallbackInsights.length ? (
          <div className="company-insights">
            {fallbackInsights.slice(0, 6).map((item) => <p key={item}>{item}</p>)}
          </div>
        ) : (
          <p className="muted-copy">No company-specific facts were extracted from the posting. Open the job link for employer context before applying.</p>
        )}
      </div>
    );
  }
  return (
    <div className="detail-body">
      <h3>Match fit</h3>
      <p>{job.explanation || "The backend scored this role against resume evidence, preferences, location, seniority, industry, and sponsorship signals."}</p>
      <MetricList job={job} />
      <SponsorshipStatus job={job} />
      <ImpactList title="Strong signals" items={job.key_matches || []} impact="High impact" />
      <ImpactList title="Consider improving" items={job.key_gaps || []} impact="Lower impact" tone="warn" />
    </div>
  );
}

function SponsorshipStatus({ job }: { job: ScoredJob }) {
  const status = job.sponsorship_risk || "Unclear";
  const evidence = job.sponsorship_evidence || "The posting does not include explicit sponsorship language.";
  return (
    <section className="sponsorship-status">
      <span>Sponsorship status</span>
      <b>{status}</b>
      <p>{evidence}</p>
    </section>
  );
}

function DescriptionList({ title, items }: { title: string; items: string[] }) {
  const cleanItems = items.filter(Boolean).slice(0, 8);
  if (!cleanItems.length) return null;
  return (
    <section>
      <h4>{title}</h4>
      <ul>
        {cleanItems.map((item) => <li key={item}>{item}</li>)}
      </ul>
    </section>
  );
}

function cleanPostingText(text: string) {
  return text
    .replace(/\r/g, "")
    .replace(/\n{3,}/g, "\n\n")
    .trim();
}

function formatPostingParagraphs(text: string) {
  const normalized = text.includes("\n")
    ? text
    : text.replace(/(?<=[.!?])\s+(?=(About|Responsibilities|Qualifications|Requirements|Benefits|What you|You will|The role)\b)/g, "\n\n");
  return normalized
    .split(/\n{2,}|\n(?=(?:About|Responsibilities|Qualifications|Requirements|Benefits|What you|You will|The role)\b)/)
    .map((paragraph) => paragraph.trim())
    .filter((paragraph) => paragraph.length > 2)
    .slice(0, 10);
}

function extractCompanyInsights(job: ScoredJob) {
  const description = cleanPostingText(job.job_description || "");
  if (!description) return [];
  const paragraphs = formatPostingParagraphs(description);
  const companyRoot = job.company.split(/[,(]/)[0].trim().toLowerCase();
  return paragraphs
    .filter((paragraph) => {
      const lower = paragraph.toLowerCase();
      return lower.includes(companyRoot) || lower.startsWith("about ") || lower.includes(" is a ") || lower.includes(" is an ");
    })
    .slice(0, 3);
}

function MetricList({ job }: { job: ScoredJob }) {
  const metrics = [
    ["Role", job.role_fit],
    ["Skills", job.skill_fit],
    ["Experience", job.experience_fit],
    ["Location", job.location_fit],
    ["Industry", job.industry_fit],
    ["Sponsorship", job.sponsorship_fit],
  ];
  return <div className="detail-metrics">{metrics.map(([label, value]) => <span key={label as string}>{label}<b>{value}/5</b></span>)}</div>;
}

function ImpactList({ title, items, impact, tone = "good" }: { title: string; items: string[]; impact: string; tone?: "good" | "warn" }) {
  return (
    <div className={tone === "warn" ? "impact-list warn" : "impact-list"}>
      <h4>{title}</h4>
      {(items.length ? items : ["No evidence returned."]).slice(0, 6).map((item) => (
        <div key={item}><CheckCircle size={18} /><span>{item}</span><b>{impact}</b></div>
      ))}
    </div>
  );
}

function sortJobs(a: ScoredJob, b: ScoredJob, sortBy: string) {
  if (sortBy === "company") return a.company.localeCompare(b.company);
  if (sortBy === "action") return a.recommended_action.localeCompare(b.recommended_action);
  return b.overall_fit_score - a.overall_fit_score;
}

function matchLabel(score: number) {
  if (score >= 85) return "Strong match";
  if (score >= 70) return "Good match";
  if (score >= 55) return "Possible match";
  return "Low match";
}

function unique(values: string[]) {
  return Array.from(new Set(values));
}

function JobCard({ job, state, onState }: { job: ScoredJob; state: GraphState; onState: (state: GraphState) => void }) {
  const [label, setLabel] = useState("Apply");
  const [notes, setNotes] = useState("");
  async function saveFeedback() {
    const feedback = { job_id: job.job_id, label, notes, role_family: job.search_query || "", company: job.company, query: job.search_query || "" };
    onState(await api<GraphState>("/api/feedback", { state, feedback }));
    setNotes("");
  }
  return (
    <article className="job-card">
      <div className="score-block"><strong>{job.overall_fit_score}</strong><span>fit</span></div>
      <div className="job-main">
        <div className="job-title-row">
          <div><span className="rank">#{job.rank}</span><h3>{job.title}</h3><p>{job.company} · {job.location}</p></div>
          {job.url ? <a className="icon-link" href={job.url} target="_blank" rel="noreferrer" aria-label="Open job"><ArrowSquareOut size={20} /></a> : null}
        </div>
        <div className="metric-row">
          {["role_fit", "skill_fit", "experience_fit", "location_fit", "industry_fit", "sponsorship_fit"].map((key) => (
            <span key={key}>{key.replace("_fit", "")} <b>{(job as any)[key]}/5</b></span>
          ))}
        </div>
        <p>{job.explanation}</p>
        <div className="split-list">
          <div><h4>Matches</h4>{(job.key_matches || []).slice(0, 4).map((item) => <span key={item}>{item}</span>)}</div>
          <div><h4>Gaps</h4>{(job.key_gaps || ["No major gap from posting text"]).slice(0, 4).map((item) => <span key={item}>{item}</span>)}</div>
        </div>
        <div className="feedback-row">
          <select value={label} onChange={(e) => setLabel(e.target.value)}>
            {["Apply", "Maybe", "Reject", "Wrong Role", "Sponsorship Issue", "Too Senior", "Bad Location", "Duplicate"].map((item) => <option key={item}>{item}</option>)}
          </select>
          <input value={notes} onChange={(e) => setNotes(e.target.value)} placeholder="Feedback note" />
          <button className="secondary" onClick={saveFeedback}>Save</button>
        </div>
      </div>
    </article>
  );
}

function ProfilePanel({ profile, onContinue }: { profile?: Record<string, any>; onContinue?: () => void }) {
  if (!profile) return <section className="panel empty-state"><FileText size={38} /><h2>Profile preview</h2><p>Extract a resume profile to see strengths, target functions, tools, and evidence.</p></section>;
  return (
    <section className="panel profile-panel">
      <div className="profile-head">
        <div>
          <p className="eyebrow">Resume profile</p>
          <h2>{profile.name || "Candidate"}</h2>
        </div>
        {onContinue ? <button className="primary continue-button" onClick={onContinue}>Continue to preferences</button> : null}
      </div>
      <p>{profile.experience_summary}</p>
      <ChipGroup title="Likely lanes" values={profile.target_functions} />
      <ChipGroup title="Strengths" values={profile.strengths_for_search} />
      <ChipGroup title="Skills" values={profile.skills} />
      <ChipGroup title="Potential gaps" values={profile.potential_gaps} />
    </section>
  );
}

function Progress({ state, complete, onStartOver }: { state: GraphState; complete: Record<Step, boolean>; onStartOver: () => void }) {
  const cacheLabel = state.cache_run_label || state.cache_run_id || state.cache_run_path;
  return (
    <section className="panel compact-panel">
      <p className="eyebrow">{STATIC_DEMO ? "Demo progress" : "Progress"}</p>
      <h3>{STATIC_DEMO ? "Sample candidate" : cacheLabel ? "Saved run" : "Working draft"}</h3>
      <div className="progress-list">
        {Object.entries(complete).map(([key, value]) => <span key={key} className={value ? "done" : ""}>{key}<b>{value ? "ready" : "pending"}</b></span>)}
      </div>
      <small>{cacheLabel || "Results will be cached after backend work runs."}</small>
      <button className="secondary" onClick={onStartOver}>Start over</button>
    </section>
  );
}

type CachedRun = { id: string; label: string };

function Replay({ onLoad }: { onLoad: (state: GraphState) => void }) {
  const [runs, setRuns] = useState<CachedRun[]>([]);
  const [selected, setSelected] = useState("");
  useEffect(() => {
    api<{ runs: CachedRun[]; latest: CachedRun | null }>("/api/runs").then((payload) => {
      setRuns(payload.runs);
      setSelected(payload.latest?.id || "");
    }).catch(() => undefined);
  }, []);
  return (
    <section className="panel compact-panel">
      <p className="eyebrow">{STATIC_DEMO ? "Sample scenario" : "Replay"}</p>
      <select aria-label={STATIC_DEMO ? "Sample scenario" : "Saved run"} value={selected} onChange={(e) => setSelected(e.target.value)}>
        <option value="">Select cached run</option>
        {runs.map((run) => <option key={run.id} value={run.id}>{run.label}</option>)}
      </select>
      <button className="secondary" disabled={!selected} onClick={async () => onLoad(await api<GraphState>(`/api/runs/load?run_id=${encodeURIComponent(selected)}`))}>{STATIC_DEMO ? "Reload sample" : "Load run"}</button>
    </section>
  );
}

function Diagnostics({ diagnostics }: { diagnostics: QueryDiagnostic[] }) {
  if (!diagnostics.length) return null;
  return <div className="diagnostics">{diagnostics.map((item) => <span key={`${item.query}-${item.location}`}>{item.query} · {item.result_count || 0} results{item.error ? ` · ${item.error}` : ""}</span>)}</div>;
}

function Field({ label, children }: { label: string; children: React.ReactNode }) {
  return <label className="field"><span>{label}</span>{children}</label>;
}

function AnyTextField({ label, value, placeholder, anyMode, onAnyMode, onChange }: {
  label: string;
  value: string;
  placeholder: string;
  anyMode: boolean;
  onAnyMode: (value: boolean) => void;
  onChange: (value: string) => void;
}) {
  return (
    <Field label={label}>
      <div className="any-field">
        <input
          value={anyMode ? "" : value}
          disabled={anyMode}
          onChange={(e) => {
            onAnyMode(false);
            onChange(e.target.value);
          }}
          placeholder={anyMode ? "Coach decides" : placeholder}
          required={!anyMode}
        />
        <button
          type="button"
          className={anyMode ? "mini-action selected" : "mini-action"}
          onClick={() => {
            const next = !anyMode;
            onAnyMode(next);
            if (next) onChange("");
          }}
        >
          Any
        </button>
      </div>
    </Field>
  );
}

function AnyListField({ label, values = [], placeholder, anyMode, onAnyMode, onChange }: {
  label: string;
  values?: string[];
  placeholder: string;
  anyMode: boolean;
  onAnyMode: (value: boolean) => void;
  onChange: (value: string[]) => void;
}) {
  return (
    <Field label={label}>
      <div className="any-field">
        <input
          value={anyMode ? "" : join(values)}
          disabled={anyMode}
          onChange={(e) => {
            onAnyMode(false);
            onChange(split(e.target.value));
          }}
          placeholder={anyMode ? "Coach decides" : placeholder}
          required={!anyMode}
        />
        <button
          type="button"
          className={anyMode ? "mini-action selected" : "mini-action"}
          onClick={() => {
            const next = !anyMode;
            onAnyMode(next);
            if (next) onChange([]);
          }}
        >
          Any
        </button>
      </div>
    </Field>
  );
}

function SearchableMultiSelect({ options, values, placeholder, onChange }: {
  options: string[];
  values: string[];
  placeholder: string;
  onChange: (values: string[]) => void;
}) {
  const [query, setQuery] = useState("");
  const [open, setOpen] = useState(false);
  const rootRef = useRef<HTMLDivElement | null>(null);
  const normalized = query.trim().toLowerCase();
  const filtered = options.filter((option) => option.toLowerCase().includes(normalized));

  useEffect(() => {
    function handlePointerDown(event: PointerEvent) {
      if (rootRef.current && !rootRef.current.contains(event.target as Node)) {
        setOpen(false);
      }
    }
    document.addEventListener("pointerdown", handlePointerDown);
    return () => document.removeEventListener("pointerdown", handlePointerDown);
  }, []);

  return (
    <div className="multi-select" ref={rootRef}>
      <div className="multi-select-control">
        <input
          value={query}
          onChange={(event) => {
            setQuery(event.target.value);
            setOpen(true);
          }}
          onFocus={() => setOpen(true)}
          onKeyDown={(event) => {
            if (event.key === "Escape") setOpen(false);
          }}
          placeholder={placeholder}
        />
        <button type="button" className="mini-action" onClick={() => {
          onChange([]);
          setOpen(false);
          setQuery("");
        }}>Any</button>
      </div>
      {values.length ? (
        <div className="selected-values">
          {values.map((value) => (
            <button type="button" key={value} onClick={() => onChange(values.filter((item) => item !== value))}>
              {value} <span>×</span>
            </button>
          ))}
        </div>
      ) : <p className="field-hint">No location selected. The coach can decide.</p>}
      {open ? (
        <div className="multi-select-menu">
          <div className="menu-actions">
            <span>{filtered.length} options</span>
            <button type="button" onMouseDown={(event) => {
              event.preventDefault();
              setOpen(false);
            }}>Done</button>
          </div>
          {filtered.length ? filtered.map((option) => {
            const selected = values.includes(option);
            return (
              <button
                type="button"
                className={selected ? "selected" : ""}
                key={option}
                onMouseDown={(event) => {
                  event.preventDefault();
                  onChange(toggleValue(values, option));
                  setQuery("");
                }}
              >
                <span>{option}</span>
                {selected ? <Check size={15} weight="bold" /> : null}
              </button>
            );
          }) : <div className="no-options">No matching location</div>}
        </div>
      ) : null}
    </div>
  );
}

function CoachQuestionBubble({ questions }: { questions: string[] }) {
  if (!questions.length) return null;
  return (
    <div className="message assistant prompt-bubble">
      <strong>Before I lock the search, I need:</strong>
      <ul>
        {questions.map((question) => <li key={question}>{question}</li>)}
      </ul>
    </div>
  );
}

function ChatText({ text }: { text: string }) {
  const cleaned = text.replace(/\*\*/g, "").replace(/#+\s*/g, "");
  const lines = cleaned.split("\n").map((line) => line.trim()).filter(Boolean);
  if (!lines.length) return null;
  return (
    <>
      {lines.map((line) => {
        const normalized = line.replace(/^[-*]\s*/, "");
        return <p key={line}>{normalized}</p>;
      })}
    </>
  );
}

function chatMessagesForDisplay(messages: ChatMessage[], questions: string[]) {
  if (!questions.length) return messages;
  const firstAssistant = messages.findIndex((message) => message.role === "assistant");
  if (firstAssistant < 0) return messages;
  return messages.filter((_, index) => index !== firstAssistant);
}

function Segmented({ label, value, options, onChange }: { label: string; value: string; options: string[][]; onChange: (value: string) => void }) {
  return (
    <div className="segmented-wrap">
      <span>{label}</span>
      <div className="segmented">{options.map(([key, text]) => <button type="button" className={value === key ? "selected" : ""} key={key} onClick={() => onChange(key)}>{text}</button>)}</div>
    </div>
  );
}

function Toggle({ label, checked, onChange }: { label: string; checked: boolean; onChange: (checked: boolean) => void }) {
  return <button className={checked ? "toggle on" : "toggle"} onClick={() => onChange(!checked)}><span />{label}</button>;
}

function Notice({ text, tone }: { text: string; tone: "danger" | "warn" }) {
  return <div className={`notice ${tone}`}><WarningCircle size={18} />{text}</div>;
}

function Loading({ label }: { label: string }) {
  return <div className="loading"><SpinnerGap className="spin" size={19} />{label}</div>;
}

function ChipGroup({ title, values = [] }: { title: string; values?: string[] }) {
  return <div className="chip-group"><h4>{title}</h4><div>{values.length ? values.map((item) => <span key={item}>{item}</span>) : <span>None yet</span>}</div></div>;
}

function Markdownish({ text }: { text: string }) {
  return (
    <div className="markdownish">
      {text.split("\n").filter(Boolean).map((line) => {
        const clean = line.replace(/\*\*/g, "");
        return clean.startsWith("###")
          ? <h3 key={line}>{clean.replace(/^###\s*/, "")}</h3>
          : <p key={line}>{clean.replace(/^-\s*/, "")}</p>;
      })}
    </div>
  );
}

async function api<T>(path: string, body?: unknown): Promise<T> {
  if (STATIC_DEMO) return staticDemoResponse(path, body) as T;
  const response = await fetch(`${API_BASE}${path}`, {
    method: body ? "POST" : "GET",
    headers: body ? { "Content-Type": "application/json" } : undefined,
    credentials: "include",
    body: body ? JSON.stringify(body) : undefined
  });
  if (!response.ok) throw new Error(await errorText(response));
  return response.json();
}

async function savePreferencesAndBrief(state: GraphState, preferences: Preferences) {
  const saved = await api<GraphState>("/api/preferences", { state, preferences });
  return api<GraphState>("/api/coach-brief", { state: saved });
}

async function errorText(response: Response) {
  try {
    const payload = await response.json();
    return payload.detail || "Request failed.";
  } catch {
    return response.statusText || "Request failed.";
  }
}

function loadLocalState(): GraphState {
  try {
    const saved = localStorage.getItem("career-search-state");
    if (saved) return JSON.parse(saved);
    return STATIC_DEMO ? freshDemoState() as GraphState : {};
  } catch {
    return STATIC_DEMO ? freshDemoState() as GraphState : {};
  }
}

function isUnlocked(step: Step, complete: Record<Step, boolean>) {
  if (step === "preferences") return complete.resume;
  if (step === "brief") return complete.resume && complete.preferences;
  if (step === "strategy") return complete.brief;
  if (step === "results") return complete.results;
  return true;
}

function hasPreferences(preferences?: Preferences) {
  return Boolean(preferences);
}

function hasMeaningfulBrief(brief?: CareerBrief) {
  if (!brief) return false;
  return Boolean(
    (brief.positioning || "").trim()
    || (brief.search_thesis || "").trim()
    || (brief.scoring_guidance || "").trim()
    || (brief.target_role_lanes || []).length
    || (brief.adjacent_role_lanes || []).length
    || (brief.unresolved_questions || []).length
  );
}

function formatStrategyType(value?: string) {
  const labels: Record<string, string> = {
    target_role: "Primary lane",
    adjacent_role: "Adjacent lane",
    broadened_repair: "Broadened search",
    sponsorship_probe: "Sponsorship check",
  };
  return labels[value || ""] || "Search lane";
}

function split(value: string) {
  return value.split(/[,;\n]/).map((item) => item.trim()).filter(Boolean);
}

function join(value?: string[]) {
  return (value || []).join(", ");
}

function toggleValue(values: string[], value: string) {
  return values.includes(value) ? values.filter((item) => item !== value) : [...values, value];
}

function sponsorshipValue(prefs: Preferences) {
  if (prefs.sponsorship_timing) return prefs.sponsorship_timing;
  return prefs.requires_sponsorship ? "future" : "unknown";
}

function parseLanes(text: string, base: SearchQuery[]) {
  return text.split("\n").map((line, index) => {
    const [query, location] = line.split("|").map((item) => item.trim());
    return { ...(base[Math.min(index, base.length - 1)] || {}), query, location: location || null };
  }).filter((item) => item.query);
}

async function downloadCsv(state: GraphState) {
  if (STATIC_DEMO) {
    const jobs = hydrateScoredJobs(state);
    const columns: (keyof ScoredJob)[] = ["rank", "title", "company", "location", "overall_fit_score", "recommended_action", "sponsorship_risk", "url"];
    const rows = [columns.join(","), ...jobs.map((job) => columns.map((column) => csvCell(job[column])).join(","))];
    const blob = new Blob([rows.join("\n")], { type: "text/csv;charset=utf-8" });
    downloadBlob(blob, "rolefit-scout-demo.csv");
    return;
  }
  const response = await fetch(`${API_BASE}/api/export`, {
    method: "POST",
    headers: { "Content-Type": "application/json" },
    credentials: "include",
    body: JSON.stringify({ state })
  });
  if (!response.ok) throw new Error(await errorText(response));
  const blob = await response.blob();
  downloadBlob(blob, "career_search_tracker.csv");
}

function downloadBlob(blob: Blob, filename: string) {
  const url = URL.createObjectURL(blob);
  const anchor = document.createElement("a");
  anchor.href = url;
  anchor.download = filename;
  anchor.click();
  URL.revokeObjectURL(url);
}

function csvCell(value: unknown) {
  const text = value == null ? "" : String(value);
  return `"${text.replace(/"/g, '""')}"`;
}

function staticDemoResponse(path: string, body?: unknown): unknown {
  const payload = (body || {}) as { state?: GraphState; preferences?: Preferences; career_brief?: CareerBrief; feedback?: Record<string, any> };
  const current = payload.state || freshDemoState() as GraphState;
  if (path === "/api/health") return { demo: true, openai_configured: false, serpapi_configured: false };
  if (path === "/api/runs") return { runs: [{ id: "rolefit-demo", label: "Fictional product candidate · demo" }], latest: { id: "rolefit-demo", label: "Fictional product candidate · demo" } };
  if (path.startsWith("/api/runs/load")) return freshDemoState();
  if (path === "/api/profile") return { ...current, candidate_profile: demoState.candidate_profile, demo_mode: true, live_search_enabled: false };
  if (path === "/api/preferences") return { ...current, inferred_preferences: payload.preferences || current.inferred_preferences };
  if (path === "/api/coach-brief") return { ...current, career_brief: demoState.career_brief, open_questions: [] };
  if (path === "/api/coach-brief/apply") return { ...current, career_brief: payload.career_brief || current.career_brief };
  if (path === "/api/strategy") return { ...current, search_strategy: demoState.search_strategy };
  if (path === "/api/search") return {
    ...current,
    scored_jobs: demoState.scored_jobs,
    query_diagnostics: demoState.query_diagnostics,
    coach_summary: demoState.coach_summary,
    cache_run_id: "rolefit-demo",
    cache_run_label: "Fictional product candidate · demo"
  };
  if (path === "/api/feedback") return { ...current, user_feedback: [...(current.user_feedback || []), payload.feedback].filter(Boolean) };
  throw new Error("This action is unavailable in the hosted demo.");
}

createRoot(document.getElementById("root")!).render(<App />);
