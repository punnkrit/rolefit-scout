import React, { useEffect, useMemo, useState } from "react";
import { createRoot } from "react-dom/client";
import { ArrowSquareOut, Briefcase, DownloadSimple, FileText, MagnifyingGlass, MapPin, ShieldCheck, SpinnerGap } from "@phosphor-icons/react";
import "./styles.css";
import "./admin.css";

const API_BASE = import.meta.env.VITE_ADMIN_API_BASE || "";

type RunMetadata = {
  run_id: string;
  browser_hash: string;
  created_at?: string;
  updated_at?: string;
  candidate_name: string;
  candidate_headline?: string;
  latest_step: string;
  preferred_locations: string[];
  target_lanes: string[];
  scored_jobs_count: number;
  top_matches: TopMatch[];
};

type TopMatch = {
  title: string;
  company: string;
  location: string;
  score: number;
  recommended_action: string;
};

type AdminRunDetail = {
  metadata: RunMetadata;
  state: GraphState;
};

type GraphState = {
  resume_text?: string;
  candidate_profile?: Record<string, any>;
  inferred_preferences?: Record<string, any>;
  career_brief?: Record<string, any>;
  search_strategy?: Record<string, any>;
  query_diagnostics?: Record<string, any>[];
  scored_jobs?: ScoredJob[];
  errors?: string[];
};

type ScoredJob = TopMatch & {
  rank?: number;
  job_id: string;
  overall_fit_score: number;
  key_matches?: string[];
  key_gaps?: string[];
  explanation?: string;
  url?: string | null;
};

function AdminApp() {
  const [runs, setRuns] = useState<RunMetadata[]>([]);
  const [selectedKey, setSelectedKey] = useState("");
  const [detail, setDetail] = useState<AdminRunDetail | null>(null);
  const [query, setQuery] = useState("");
  const [loading, setLoading] = useState(true);
  const [detailLoading, setDetailLoading] = useState(false);
  const [error, setError] = useState("");

  useEffect(() => {
    api<{ runs: RunMetadata[] }>("/api/admin/runs")
      .then((payload) => {
        setRuns(payload.runs);
        setSelectedKey(runKey(payload.runs[0]));
      })
      .catch((err) => setError(String(err.message || err)))
      .finally(() => setLoading(false));
  }, []);

  useEffect(() => {
    const selected = runs.find((run) => runKey(run) === selectedKey);
    if (!selected) {
      setDetail(null);
      return;
    }
    setDetailLoading(true);
    api<AdminRunDetail>(`/api/admin/runs/${encodeURIComponent(selected.browser_hash)}/${encodeURIComponent(selected.run_id)}`)
      .then(setDetail)
      .catch((err) => setError(String(err.message || err)))
      .finally(() => setDetailLoading(false));
  }, [runs, selectedKey]);

  const filtered = useMemo(() => {
    const needle = query.trim().toLowerCase();
    if (!needle) return runs;
    return runs.filter((run) => searchableText(run).includes(needle));
  }, [runs, query]);

  const selected = detail?.metadata || runs.find((run) => runKey(run) === selectedKey);

  return (
    <main className="admin-shell">
      <div className="grain" />
      <header className="admin-topbar">
        <div>
          <h1>Replay admin</h1>
          <p>Local-only review of browser-scoped cached career-search runs.</p>
        </div>
        <span><ShieldCheck size={18} /> localhost only</span>
      </header>

      {error ? <div className="notice danger">{error}</div> : null}

      <section className="admin-layout">
        <aside className="panel admin-sidebar">
          <div className="admin-search">
            <MagnifyingGlass size={18} />
            <input value={query} onChange={(event) => setQuery(event.target.value)} placeholder="Search name, date, run, location" />
          </div>
          <div className="admin-count">{loading ? "Loading runs..." : `${filtered.length} runs`}</div>
          <div className="admin-run-list">
            {filtered.map((run) => (
              <button key={runKey(run)} className={runKey(run) === selectedKey ? "active" : ""} onClick={() => setSelectedKey(runKey(run))}>
                <b>{run.candidate_name || "Unknown candidate"}</b>
                <span>{formatDate(run.updated_at || run.created_at)} · {run.scored_jobs_count} matches</span>
                <small>{run.latest_step} · {run.run_id}</small>
              </button>
            ))}
            {!loading && !filtered.length ? <p className="muted-copy">No cached browser runs found.</p> : null}
          </div>
        </aside>

        <section className="panel admin-detail">
          {detailLoading ? <Loading /> : null}
          {selected && detail ? <RunDetail detail={detail} /> : !detailLoading ? <EmptyDetail /> : null}
        </section>
      </section>
    </main>
  );
}

function RunDetail({ detail }: { detail: AdminRunDetail }) {
  const { metadata, state } = detail;
  const profile = state.candidate_profile || {};
  const prefs = state.inferred_preferences || {};
  const brief = state.career_brief || {};
  const strategy = state.search_strategy || {};
  const jobs = state.scored_jobs || [];
  return (
    <>
      <div className="admin-detail-head">
        <div>
          <p className="eyebrow">{metadata.latest_step}</p>
          <h2>{metadata.candidate_name}</h2>
          <p>{metadata.candidate_headline || profile.current_status || "No extracted headline."}</p>
        </div>
        <a className="primary" href={`${API_BASE}/api/admin/runs/${encodeURIComponent(metadata.browser_hash)}/${encodeURIComponent(metadata.run_id)}/export`}>
          <DownloadSimple size={18} /> Export CSV
        </a>
      </div>

      <div className="admin-summary-grid">
        <Fact label="Run" value={metadata.run_id} />
        <Fact label="Browser hash" value={metadata.browser_hash.slice(0, 12)} />
        <Fact label="Updated" value={formatDate(metadata.updated_at || metadata.created_at)} />
        <Fact label="Matches" value={String(metadata.scored_jobs_count)} />
      </div>

      <Section title="Profile">
        <p>{profile.positioning_summary || profile.current_status || metadata.candidate_headline || "No profile summary available."}</p>
        <ChipList title="Target functions" values={profile.target_functions || metadata.target_lanes} />
        <ChipList title="Strengths" values={profile.strengths || []} />
      </Section>

      <Section title="Preferences and brief">
        <div className="admin-columns">
          <div>
            <h4>Preferences</h4>
            <ChipList title="Locations" values={prefs.preferred_locations || metadata.preferred_locations} />
            <ChipList title="Industries" values={prefs.target_industries || []} />
            <p>Remote: {prefs.remote_preference || "not specified"} · Sponsorship: {prefs.sponsorship_timing || "not specified"}</p>
          </div>
          <div>
            <h4>Coach brief</h4>
            <p>{brief.search_thesis || brief.positioning || "No brief generated."}</p>
            <ChipList title="Target lanes" values={brief.target_role_lanes || metadata.target_lanes} />
          </div>
        </div>
      </Section>

      <Section title="Strategy">
        <p>{strategy.strategy_summary || "No strategy generated."}</p>
        <div className="admin-lanes">
          {(strategy.queries || []).slice(0, 10).map((query: any, index: number) => (
            <article key={`${query.query}-${index}`}>
              <b>{query.query}</b>
              <span><MapPin size={14} /> {query.location || "Any location"}</span>
            </article>
          ))}
        </div>
      </Section>

      <Section title="Top matches">
        <div className="admin-jobs">
          {jobs.slice(0, 12).map((job) => <JobRow key={job.job_id} job={job} />)}
          {!jobs.length ? <p className="muted-copy">No scored jobs for this run.</p> : null}
        </div>
      </Section>

      <Section title="Diagnostics">
        <div className="admin-diagnostics">
          {(state.query_diagnostics || []).map((item, index) => (
            <span key={`${item.query}-${index}`}>{item.query || "Query"}: {item.result_count ?? item.results_count ?? 0} results</span>
          ))}
          {!(state.query_diagnostics || []).length ? <p className="muted-copy">No query diagnostics saved.</p> : null}
        </div>
      </Section>

      <details className="admin-resume">
        <summary><FileText size={18} /> Resume text</summary>
        <pre>{state.resume_text || "No resume text saved."}</pre>
      </details>
    </>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return <section className="admin-section"><h3>{title}</h3>{children}</section>;
}

function Fact({ label, value }: { label: string; value: string }) {
  return <span className="admin-fact"><small>{label}</small><b>{value || "None"}</b></span>;
}

function ChipList({ title, values = [] }: { title: string; values?: string[] }) {
  const clean = values.filter(Boolean).slice(0, 10);
  if (!clean.length) return null;
  return (
    <div className="admin-chip-list">
      <span>{title}</span>
      <div>{clean.map((value) => <b key={value}>{value}</b>)}</div>
    </div>
  );
}

function JobRow({ job }: { job: ScoredJob }) {
  const score = job.overall_fit_score ?? job.score ?? 0;
  return (
    <article className="admin-job-row">
      <div>
        <b>{job.title}</b>
        <span>{job.company} · {job.location}</span>
        <p>{job.explanation || (job.key_matches || []).slice(0, 2).join("; ")}</p>
      </div>
      <strong>{score}%</strong>
      {job.url ? <a className="secondary" href={job.url} target="_blank" rel="noreferrer">Open <ArrowSquareOut size={15} /></a> : null}
    </article>
  );
}

function EmptyDetail() {
  return <div className="empty-state"><Briefcase size={42} /><h2>No run selected</h2><p>Select a cached run to review its profile, strategy, and match outputs.</p></div>;
}

function Loading() {
  return <div className="loading"><SpinnerGap className="spin" size={19} />Loading run</div>;
}

function runKey(run?: RunMetadata) {
  return run ? `${run.browser_hash}/${run.run_id}` : "";
}

function searchableText(run: RunMetadata) {
  return [
    run.candidate_name,
    run.candidate_headline,
    run.run_id,
    run.browser_hash,
    run.latest_step,
    run.created_at,
    run.updated_at,
    ...(run.preferred_locations || []),
    ...(run.target_lanes || []),
    ...(run.top_matches || []).flatMap((job) => [job.title, job.company, job.location]),
  ].filter(Boolean).join(" ").toLowerCase();
}

function formatDate(value?: string) {
  if (!value) return "Unknown date";
  const date = new Date(value);
  if (Number.isNaN(date.getTime())) return value;
  return date.toLocaleString(undefined, { month: "short", day: "numeric", hour: "numeric", minute: "2-digit" });
}

async function api<T>(path: string): Promise<T> {
  const response = await fetch(`${API_BASE}${path}`);
  if (!response.ok) throw new Error(await response.text());
  return response.json();
}

createRoot(document.getElementById("root")!).render(<AdminApp />);
