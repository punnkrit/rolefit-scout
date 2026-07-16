from __future__ import annotations

from pathlib import Path

import pandas as pd
import streamlit as st

from src.cache import latest_cache_dir, list_run_cache_dirs, load_graph_state, save_graph_state
from src.config import load_config
from src.export import dataframe_to_csv, jobs_to_dataframe
from src.graph import run_approved_search, run_coach_brief, run_resume_profile, run_search_strategy
from src.memory import load_memory, save_memory, update_memory_from_feedback
from src.resume_parser import ResumeParseError, parse_resume_file
from src.schemas import (
    CareerBrief,
    FeedbackRecord,
    RemotePreference,
    ReviewLabel,
    ScoredJob,
    SearchQuery,
    SearchStrategyPlan,
    SponsorshipTiming,
    UserPreferences,
)
from src.utils import split_csvish, truncate


st.set_page_config(page_title="Career Search Coach", page_icon="CA", layout="wide")

WORKFLOW_STEPS = [
    ("resume", "Resume", "Resume profile"),
    ("preferences", "Preferences", "Preferences"),
    ("coach_brief", "Coach Brief", "Coach brief"),
    ("strategy", "Strategy", "Strategy"),
    ("results", "Results", "Jobs scored"),
]

REMOTE_LABELS = {
    "Any": RemotePreference.any,
    "On-site": RemotePreference.onsite,
    "Hybrid": RemotePreference.hybrid,
    "Fully Remote": RemotePreference.remote,
}

SPONSORSHIP_LABELS = {
    "Either way": (False, SponsorshipTiming.unknown),
    "Now": (True, SponsorshipTiming.now),
    "In future": (True, SponsorshipTiming.future),
    "Not needed": (False, SponsorshipTiming.not_needed),
}

ANY_VALUES = {"", "any", "open", "flexible", "no preference", "coach decide", "coach decides"}
NONE_VALUES = {"", "none", "no", "n/a", "na", "no exclusions", "nothing"}

CITY_LOCATION_LOOKUP = {
    "new york": "New York, NY",
    "nyc": "New York, NY",
    "san francisco": "San Francisco, CA",
    "sf": "San Francisco, CA",
    "los angeles": "Los Angeles, CA",
    "la": "Los Angeles, CA",
    "seattle": "Seattle, WA",
    "chicago": "Chicago, IL",
    "boston": "Boston, MA",
    "austin": "Austin, TX",
    "portland": "Portland, OR",
}

STATE_LOCATION_LOOKUP = {
    "california": "California, United States",
    "ca": "California, United States",
    "oregon": "Oregon, United States",
    "or": "Oregon, United States",
    "washington": "Washington, United States",
    "wa": "Washington, United States",
    "new york state": "New York, United States",
    "ny": "New York, United States",
    "illinois": "Illinois, United States",
    "il": "Illinois, United States",
    "massachusetts": "Massachusetts, United States",
    "ma": "Massachusetts, United States",
    "texas": "Texas, United States",
    "tx": "Texas, United States",
}

US_STATE_OPTIONS = [
    "United States",
    "Alabama, United States",
    "Alaska, United States",
    "Arizona, United States",
    "Arkansas, United States",
    "California, United States",
    "Colorado, United States",
    "Connecticut, United States",
    "Delaware, United States",
    "Florida, United States",
    "Georgia, United States",
    "Hawaii, United States",
    "Idaho, United States",
    "Illinois, United States",
    "Indiana, United States",
    "Iowa, United States",
    "Kansas, United States",
    "Kentucky, United States",
    "Louisiana, United States",
    "Maine, United States",
    "Maryland, United States",
    "Massachusetts, United States",
    "Michigan, United States",
    "Minnesota, United States",
    "Mississippi, United States",
    "Missouri, United States",
    "Montana, United States",
    "Nebraska, United States",
    "Nevada, United States",
    "New Hampshire, United States",
    "New Jersey, United States",
    "New Mexico, United States",
    "New York, United States",
    "North Carolina, United States",
    "North Dakota, United States",
    "Ohio, United States",
    "Oklahoma, United States",
    "Oregon, United States",
    "Pennsylvania, United States",
    "Rhode Island, United States",
    "South Carolina, United States",
    "South Dakota, United States",
    "Tennessee, United States",
    "Texas, United States",
    "Utah, United States",
    "Vermont, United States",
    "Virginia, United States",
    "Washington, United States",
    "Washington, DC",
    "West Virginia, United States",
    "Wisconsin, United States",
    "Wyoming, United States",
]

US_CITY_OPTIONS = [
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
    "Minneapolis, MN",
]

LOCATION_OPTIONS = US_STATE_OPTIONS + US_CITY_OPTIONS


def main() -> None:
    _init_session()
    config = load_config()

    with st.sidebar:
        st.subheader("Workflow")
        _render_stepper()
        st.divider()
        st.subheader("Run Controls")
        st.toggle("Demo mode", key="demo_mode", help="Use local sample resume/jobs without live API spend.")
        st.toggle("Live SerpApi search", key="live_search_enabled", value=True, help="Requires SERPAPI_API_KEY.")
        st.caption(f"OpenAI: {'configured' if config.has_openai_key else 'missing'}")
        st.caption(f"SerpApi: {'configured' if config.has_serpapi_key else 'missing'}")
        _render_replay_controls()

    st.title("Career Search Coach")
    _render_status()
    current_step = _current_workflow_step()

    if current_step == "resume":
        input_col, profile_col = st.columns([0.42, 0.58])
        with input_col:
            _render_resume_panel()
            if st.button("Extract Resume Profile", type="primary", width="stretch"):
                _run_workflow_step("Extracting resume profile...", lambda state: run_resume_profile(state, config), next_step="preferences")
        with profile_col:
            _render_profile_panel()
    elif current_step == "preferences":
        form_col, summary_col = st.columns([0.55, 0.45])
        with form_col:
            _render_preferences_panel(config)
        with summary_col:
            _render_preferences_summary()
    elif current_step == "coach_brief":
        brief_col, coach_col = st.columns([0.58, 0.42])
        with brief_col:
            if not st.session_state.graph_state.get("career_brief"):
                st.subheader("Coach Brief")
                st.write("Generate the coach interpretation from the resume profile and saved user constraints.")
                if st.button("Generate Coach Brief", type="primary", width="stretch"):
                    _run_workflow_step("Generating coach brief...", lambda state: run_coach_brief(state, config))
            else:
                _render_editable_career_brief_panel()
                if st.button("Build Search Strategy", type="primary", width="stretch"):
                    _run_workflow_step("Building search strategy...", lambda state: run_search_strategy(state, config), next_step="strategy")
        with coach_col:
            _render_coach_refinement_panel(config)
    elif current_step == "strategy":
        _render_strategy_panel()
        if st.button("Run Approved Search", type="primary", width="stretch"):
            _run_approved_search(config, next_step="results")
        _render_diagnostics_panel()
    elif current_step == "results":
        summary_col, feedback_col = st.columns([0.58, 0.42])
        with summary_col:
            _render_summary_panel()
        with feedback_col:
            _render_feedback_panel()
        _render_tracker_panel()
    with st.expander("Debug", expanded=False):
        _render_debug_panel()


def _init_session() -> None:
    defaults = {
        "graph_state": {},
        "resume_text": "",
        "messages": [],
        "demo_mode": False,
        "live_search_enabled": True,
        "manual_preferences": {},
        "edited_strategy_rows": [],
        "workflow_step": "resume",
    }
    for key, value in defaults.items():
        st.session_state.setdefault(key, value)


def _base_state() -> dict:
    state = dict(st.session_state.graph_state)
    state["resume_text"] = st.session_state.resume_text
    state["messages"] = st.session_state.messages
    state["demo_mode"] = st.session_state.demo_mode
    state["live_search_enabled"] = st.session_state.live_search_enabled
    if st.session_state.manual_preferences:
        state["inferred_preferences"] = st.session_state.manual_preferences
    return state


def _run_workflow_step(spinner_text: str, runner, next_step: str | None = None) -> None:
    state = _base_state()
    state["approved_strategy"] = {"approved": False, "edited_queries": []}
    with st.spinner(spinner_text):
        result = runner(state)
    _sync_result(result, next_step=next_step)


def _run_approved_search(config, next_step: str | None = None) -> None:
    state = _base_state()
    queries = _edited_strategy_queries()
    state["approved_strategy"] = {"approved": True, "edited_queries": [query.model_dump(mode="json") for query in queries]}
    with st.spinner("Running approved search and scoring..."):
        result = run_approved_search(state, config)
    _sync_result(result, next_step=next_step)


def _sync_result(result: dict, next_step: str | None = None) -> None:
    st.session_state.graph_state = result
    st.session_state.messages = result.get("messages", st.session_state.messages)
    st.session_state.manual_preferences = result.get("inferred_preferences", st.session_state.manual_preferences)
    if next_step and _workflow_unlocked(result).get(next_step):
        st.session_state.workflow_step = next_step
    st.success(f"Run cached at {result.get('cache_run_path')}")
    st.rerun()


def _render_stepper() -> None:
    state = st.session_state.graph_state
    unlocked = _workflow_unlocked(state)
    complete = _workflow_complete(state)
    current = _current_workflow_step()
    unlocked_options = [key for key, _, _ in WORKFLOW_STEPS if unlocked[key]]
    labels = {key: f"{'✓' if complete[key] else '○'} {label}" for key, label, _ in WORKFLOW_STEPS}
    selected = st.radio(
        "Workflow",
        unlocked_options,
        index=unlocked_options.index(current)
        if current in unlocked_options
        else 0,
        format_func=lambda key: labels[key],
        label_visibility="collapsed",
    )
    if selected != current:
        st.session_state.workflow_step = selected
        st.rerun()
    for key, label, completion_label in WORKFLOW_STEPS:
        if not unlocked[key]:
            st.markdown(f"<span style='opacity:0.42'>○ {label}</span>", unsafe_allow_html=True)


def _workflow_complete(state: dict | None = None) -> dict[str, bool]:
    state = state or st.session_state.graph_state
    return {
        "resume": bool(state.get("candidate_profile")),
        "preferences": bool(st.session_state.manual_preferences or state.get("inferred_preferences")),
        "coach_brief": bool(state.get("career_brief")),
        "strategy": bool(state.get("search_strategy", {}).get("queries")),
        "results": bool(state.get("scored_jobs")),
    }


def _workflow_unlocked(state: dict | None = None) -> dict[str, bool]:
    complete = _workflow_complete(state)
    return {
        "resume": True,
        "preferences": complete["resume"],
        "coach_brief": complete["resume"] and complete["preferences"],
        "strategy": complete["coach_brief"],
        "results": complete["results"],
    }


def _current_workflow_step() -> str:
    current = st.session_state.get("workflow_step", "resume")
    if current == "debug":
        current = "resume"
        st.session_state.workflow_step = current
    unlocked = _workflow_unlocked()
    if unlocked.get(current):
        return current
    for key, _, _ in WORKFLOW_STEPS:
        if unlocked[key] and not _workflow_complete()[key]:
            st.session_state.workflow_step = key
            return key
    st.session_state.workflow_step = "resume"
    return "resume"


def _render_resume_panel() -> None:
    st.subheader("Resume")
    uploaded = st.file_uploader("Upload PDF, DOCX, or TXT", type=["pdf", "docx", "txt"])
    pasted = st.text_area("Or paste resume text", value=st.session_state.get("resume_text", ""), height=220)
    if uploaded:
        try:
            st.session_state.resume_text = parse_resume_file(uploaded, uploaded.name)
            st.success("Resume parsed.")
        except ResumeParseError as exc:
            st.error(str(exc))
    elif pasted.strip():
        st.session_state.resume_text = pasted.strip()
    elif st.session_state.demo_mode and not st.session_state.resume_text:
        sample = Path("tests/sample_resume.txt")
        if sample.exists():
            st.session_state.resume_text = sample.read_text(encoding="utf-8")
    if st.session_state.resume_text:
        st.text_area("Preview", value=truncate(st.session_state.resume_text, 3000), height=260, disabled=True)


def _render_profile_panel() -> None:
    st.subheader("Resume Profile")
    profile = st.session_state.graph_state.get("candidate_profile")
    if not profile:
        st.info("Upload or paste a resume, then extract the profile.")
        return
    st.write(f"**{profile.get('name') or 'Candidate'}**")
    st.write(truncate(profile.get("experience_summary", ""), 900))
    _write_chip_line("Likely role families", profile.get("target_functions", []))
    _write_chip_line("Strengths", profile.get("strengths_for_search", []))
    _write_chip_line("Skills", profile.get("skills", []))
    _write_chip_line("Tools", profile.get("tools", []))
    _write_chip_line("Potential gaps", profile.get("potential_gaps", []))
    evidence = profile.get("evidence_notes", [])
    if evidence:
        with st.expander("Resume evidence"):
            for item in evidence:
                st.write(f"- {item}")
    with st.expander("Full profile JSON"):
        st.json(profile)


def _write_chip_line(label: str, values: list[str]) -> None:
    text = ", ".join(values) if values else "None yet"
    st.write(f"**{label}:** {truncate(text, 700)}")


def _render_preferences_panel(config) -> None:
    st.subheader("User Preferences")
    st.caption("Tell the coach your hard constraints. Use 'Any' when you want the coach to decide.")
    raw = st.session_state.manual_preferences or st.session_state.graph_state.get("inferred_preferences") or {}
    prefs = UserPreferences.model_validate(raw or {})
    with st.form("preferences_form"):
        primary_goal = st.text_input("Primary goal / aspiration", prefs.primary_goal or "Any")
        target_titles = st.text_area("Target titles", _list_or_any(prefs.target_job_titles), height=70)
        adjacent = st.text_area("Acceptable adjacent roles", _list_or_any(prefs.acceptable_adjacent_roles), height=70)
        locations = st.multiselect(
            "Locations",
            LOCATION_OPTIONS,
            default=_valid_location_choices(prefs.preferred_locations),
            placeholder="Search US states or cities",
            help="Pick broad states like California, United States, or specific cities like Los Angeles, CA.",
        )
        remote_label = _remote_label_for_value(prefs.remote_preference)
        remote = st.radio("Remote preference", list(REMOTE_LABELS), index=list(REMOTE_LABELS).index(remote_label), horizontal=True)
        sponsorship_label = _sponsorship_label_for_value(prefs.requires_sponsorship, prefs.sponsorship_timing)
        sponsorship = st.radio(
            "Sponsorship timing",
            list(SPONSORSHIP_LABELS),
            index=list(SPONSORSHIP_LABELS).index(sponsorship_label),
            horizontal=True,
        )
        industries = st.text_input("Target industries", _list_or_any(prefs.target_industries), placeholder="Technology, SaaS, Healthcare")
        _render_value_tokens(_clean_any_list(industries), empty_label="Coach decides")
        exclusions = st.text_area(
            "Hard exclusions",
            _list_or_none([*prefs.role_families_to_avoid, *prefs.excluded_companies, *prefs.exclude_keywords]),
            height=70,
            help="Role families, companies, industries, or keywords to avoid.",
        )
        _render_value_tokens(_clean_none_list(exclusions), empty_label="No exclusions", tone="danger")
        if st.form_submit_button("Save Preferences"):
            requires_sponsorship, sponsorship_timing = SPONSORSHIP_LABELS[sponsorship]
            updated = prefs.model_copy(
                update={
                    "primary_goal": "" if _is_any_text(primary_goal) else primary_goal.strip(),
                    "target_job_titles": _clean_any_list(target_titles),
                    "acceptable_adjacent_roles": _clean_any_list(adjacent),
                    "preferred_locations": list(locations),
                    "target_industries": _clean_any_list(industries),
                    "role_families_to_avoid": _clean_none_list(exclusions),
                    "remote_preference": REMOTE_LABELS[remote],
                    "requires_sponsorship": requires_sponsorship,
                    "sponsorship_timing": sponsorship_timing,
                    "max_searches": config.max_searches_per_run,
                }
            )
            st.session_state.manual_preferences = updated.model_dump(mode="json")
            state = dict(st.session_state.graph_state)
            state["inferred_preferences"] = updated.model_dump(mode="json")
            st.session_state.graph_state = state
            st.success("Preferences saved.")


def _render_preferences_summary() -> None:
    st.subheader("Saved Constraints")
    raw = st.session_state.manual_preferences or st.session_state.graph_state.get("inferred_preferences")
    if not raw:
        st.info("Save preferences to unlock the Coach Brief step.")
        return
    prefs = UserPreferences.model_validate(raw)
    st.write(f"**Goal:** {prefs.primary_goal or 'Coach decides'}")
    _write_chip_line("Targets", prefs.target_job_titles or ["Coach decides"])
    _write_chip_line("Adjacent", prefs.acceptable_adjacent_roles or ["Coach decides"])
    _write_chip_line("Locations", prefs.preferred_locations or ["Coach decides"])
    _write_chip_line("Industries", prefs.target_industries or ["Coach decides"])
    _write_chip_line("Exclusions", prefs.role_families_to_avoid + prefs.excluded_companies + prefs.exclude_keywords or ["None"])
    st.write(f"**Remote:** {_remote_label_for_value(prefs.remote_preference)}")
    st.write(f"**Sponsorship:** {_sponsorship_label_for_value(prefs.requires_sponsorship, prefs.sponsorship_timing)}")
    if st.button("Continue to Coach Brief", type="primary", width="stretch"):
        st.session_state.workflow_step = "coach_brief"
        st.rerun()


def _list_or_any(values: list[str]) -> str:
    return ", ".join(values) if values else "Any"


def _list_or_none(values: list[str]) -> str:
    return ", ".join(values) if values else "None"


def _valid_location_choices(values: list[str]) -> list[str]:
    valid = []
    option_keys = {normalize_pref_text(option): option for option in LOCATION_OPTIONS}
    for value in values:
        exact = option_keys.get(normalize_pref_text(value))
        if exact:
            valid.append(exact)
    return _dedupe_keep_order(valid)


def _is_any_text(text: str | None) -> bool:
    return normalize_pref_text(text) in ANY_VALUES


def normalize_pref_text(text: str | None) -> str:
    return " ".join((text or "").strip().lower().replace(".", "").split())


def _clean_any_list(text: str) -> list[str]:
    values = split_csvish(text)
    if not values or all(normalize_pref_text(value) in ANY_VALUES for value in values):
        return []
    return [value for value in values if normalize_pref_text(value) not in ANY_VALUES]


def _clean_none_list(text: str) -> list[str]:
    values = split_csvish(text)
    if not values or all(normalize_pref_text(value) in NONE_VALUES for value in values):
        return []
    return [value for value in values if normalize_pref_text(value) not in NONE_VALUES]


def _parse_location_text(text: str) -> list[str]:
    if _is_any_text(text):
        return []
    raw_tokens = [token.strip() for token in text.replace(";", ",").replace("\n", ",").split(",") if token.strip()]
    locations: list[str] = []
    index = 0
    while index < len(raw_tokens):
        token = raw_tokens[index]
        key = normalize_pref_text(token)
        next_key = normalize_pref_text(raw_tokens[index + 1]) if index + 1 < len(raw_tokens) else ""
        if len(next_key) == 2 and next_key in STATE_LOCATION_LOOKUP and key not in STATE_LOCATION_LOOKUP:
            locations.append(_title_city_state(token, next_key.upper()))
            index += 2
            continue
        if next_key == "united states" and key in STATE_LOCATION_LOOKUP:
            locations.append(STATE_LOCATION_LOOKUP[key])
            index += 2
            continue
        if key in CITY_LOCATION_LOOKUP:
            locations.append(CITY_LOCATION_LOOKUP[key])
        elif key in STATE_LOCATION_LOOKUP:
            locations.append(STATE_LOCATION_LOOKUP[key])
        else:
            locations.append(token)
        index += 1
    return _dedupe_keep_order(locations)


def _title_city_state(city: str, state: str) -> str:
    return f"{city.strip().title()}, {state}"


def _dedupe_keep_order(values: list[str]) -> list[str]:
    seen = set()
    deduped = []
    for value in values:
        key = normalize_pref_text(value)
        if key and key not in seen:
            seen.add(key)
            deduped.append(value)
    return deduped


def _remote_label_for_value(value: RemotePreference) -> str:
    for label, enum_value in REMOTE_LABELS.items():
        if enum_value == value:
            return label
    return "Any"


def _sponsorship_label_for_value(requires_sponsorship: bool, timing: SponsorshipTiming) -> str:
    if timing == SponsorshipTiming.now:
        return "Now"
    if timing == SponsorshipTiming.future:
        return "In future"
    if timing == SponsorshipTiming.not_needed:
        return "Not needed"
    return "Either way" if not requires_sponsorship else "In future"


def _render_value_tokens(values: list[str], empty_label: str, tone: str = "neutral") -> None:
    if not values:
        return
    palette = {
        "neutral": ("#1f2a37", "#4b5563", "#d1d5db"),
        "danger": ("#3a1f24", "#7f1d1d", "#fecaca"),
    }[tone]
    html = " ".join(
        f"<span style='display:inline-block;margin:0 6px 8px 0;padding:5px 10px;border:1px solid {palette[1]};"
        f"border-radius:6px;background:{palette[0]};color:{palette[2]};font-size:13px'>{item}</span>"
        for item in values
    )
    st.markdown(html, unsafe_allow_html=True)


def _render_editable_career_brief_panel() -> None:
    st.subheader("Coach Brief")
    st.caption("See what your coach thinks about you before building the job search strategy.")
    raw = st.session_state.graph_state.get("career_brief") or {}
    if not raw:
        st.info("Generate the coach brief from Resume + User Preferences.")
        return
    brief = CareerBrief.model_validate(raw)
    with st.form("coach_brief_form"):
        st.markdown("**Search Direction**")
        positioning = st.text_area(
            "Candidate positioning",
            brief.positioning,
            height=90,
            help="The short narrative the coach should optimize the search around.",
        )
        search_thesis = st.text_area(
            "What the search should optimize for",
            brief.search_thesis,
            height=95,
            help="Plain-English guidance for which roles should rise to the top.",
        )
        seniority = st.text_input("Seniority / level calibration", brief.seniority_calibration)

        lane_col, scoring_col = st.columns(2)
        with lane_col:
            st.markdown("**Role Lanes**")
            target_lanes = st.text_area("Primary lanes", ", ".join(brief.target_role_lanes), height=95)
            adjacent_lanes = st.text_area("Good adjacent lanes", ", ".join(brief.adjacent_role_lanes), height=95)
            excluded_lanes = st.text_area("Avoid these lanes", ", ".join(brief.excluded_lanes), height=95)
        with scoring_col:
            st.markdown("**Judgment Rules**")
            scoring = st.text_area(
                "How jobs should be scored",
                brief.scoring_guidance,
                height=150,
                help="Guidance the LLM scorer uses after search results come back.",
            )
            unresolved = st.text_area(
                "Open questions before search",
                "\n".join(brief.unresolved_questions),
                height=140,
                help="Keep only questions that would materially change search targeting.",
            )
        if st.form_submit_button("Apply Coach Brief"):
            updated = brief.model_copy(
                update={
                    "positioning": positioning,
                    "search_thesis": search_thesis,
                    "target_role_lanes": split_csvish(target_lanes),
                    "adjacent_role_lanes": split_csvish(adjacent_lanes),
                    "excluded_lanes": split_csvish(excluded_lanes),
                    "seniority_calibration": seniority,
                    "scoring_guidance": scoring,
                    "unresolved_questions": [line.strip() for line in unresolved.splitlines() if line.strip()],
                    "readiness": "ready_to_search" if not unresolved.strip() else "needs_more_info",
                }
            )
            state = dict(st.session_state.graph_state)
            state["career_brief"] = updated.model_dump(mode="json")
            state["interview_complete"] = updated.readiness == "ready_to_search"
            state["open_questions"] = updated.unresolved_questions
            st.session_state.graph_state = state
            save_graph_state(state, state.get("cache_run_path"))
            st.success("Coach brief applied.")


def _render_coach_refinement_panel(config) -> None:
    st.subheader("Coach Notes")
    brief = st.session_state.graph_state.get("career_brief") or {}
    questions = st.session_state.graph_state.get("open_questions") or brief.get("unresolved_questions", [])
    if questions:
        st.write("**Questions to resolve:**")
        for question in questions:
            st.write(f"- {question}")
    else:
        st.info("Use chat here to refine the coach brief or clarify tradeoffs.")
    with st.container(height=340, border=False):
        for message in st.session_state.messages:
            with st.chat_message(message.get("role", "user")):
                st.write(message.get("content", ""))
    user_message = st.chat_input("Refine the coach brief...")
    if user_message:
        st.session_state.messages.append({"role": "user", "content": user_message})
        state = _base_state()
        state["messages"] = st.session_state.messages
        state["conversation_updated"] = True
        with st.spinner("Updating coach brief..."):
            result = run_coach_brief(state, config)
        _sync_result(result)


def _render_strategy_panel() -> None:
    st.subheader("Search Strategy")
    strategy = st.session_state.graph_state.get("search_strategy")
    if not strategy:
        st.info("Build the search strategy from the Coach Brief first.")
        return
    plan = SearchStrategyPlan.model_validate(strategy)
    st.write(plan.strategy_summary)
    rows = [query.model_dump(mode="json") for query in plan.queries]
    display_cols = ["query", "location", "strategy_type", "rationale", "expected_tradeoff"]
    st.dataframe(pd.DataFrame(rows)[display_cols], width="stretch", hide_index=True, height=min(360, 72 + (len(rows) * 36)))
    if not st.session_state.edited_strategy_rows:
        st.session_state.edited_strategy_rows = rows
    with st.expander("Edit lanes", expanded=True):
        lane_text = "\n".join(f"{row.get('query', '')} | {row.get('location') or ''}" for row in st.session_state.edited_strategy_rows or rows)
        edited_text = st.text_area("One lane per line: query | location", lane_text, height=180)
        if st.button("Apply Lane Edits"):
            edited_rows = []
            for line in edited_text.splitlines():
                if not line.strip():
                    continue
                query, _, location = line.partition("|")
                edited_rows.append({"query": query.strip(), "location": location.strip() or None})
            merged = []
            for index, row in enumerate(edited_rows):
                base = dict(rows[min(index, len(rows) - 1)]) if rows else {}
                base.update(row)
                merged.append(base)
            st.session_state.edited_strategy_rows = merged
            st.success("Lane edits staged for approved search.")


def _edited_strategy_queries() -> list[SearchQuery]:
    rows = st.session_state.get("edited_strategy_rows") or st.session_state.graph_state.get("search_strategy", {}).get("queries", [])
    return [SearchQuery.model_validate(row) for row in rows if str(row.get("query", "")).strip()]


def _render_diagnostics_panel() -> None:
    st.subheader("Search Diagnostics")
    diagnostics = st.session_state.graph_state.get("query_diagnostics", [])
    if diagnostics:
        df = pd.DataFrame(diagnostics)
        if "error" in df:
            df["error"] = df["error"].fillna("").map(lambda value: truncate(str(value), 120))
        st.dataframe(df, width="stretch", hide_index=True, height=min(320, 72 + (len(df) * 36)))
    else:
        st.info("Diagnostics appear after approved search.")


def _render_tracker_panel() -> None:
    st.subheader("Ranked Tracker")
    scored = [ScoredJob.model_validate(item) for item in st.session_state.graph_state.get("scored_jobs", [])]
    if not scored:
        st.info("Run approved search to score jobs.")
        return
    df = jobs_to_dataframe(scored)
    min_score = st.slider("Minimum fit score", 0, 100, 50)
    actions = st.multiselect("Recommended action", ["Apply", "Maybe", "Skip"], default=["Apply", "Maybe"])
    filtered = df[(df["overall_fit_score"] >= min_score) & (df["recommended_action"].isin(actions))].copy()
    filtered["apply_link"] = filtered["url"].map(_markdown_link)
    filtered["key_gaps"] = filtered["key_gaps"].replace("", "No major gap from available posting text")
    visible_cols = [
        "rank",
        "recommended_action",
        "overall_fit_score",
        "sponsorship_risk",
        "company",
        "title",
        "location",
        "key_matches",
        "key_gaps",
        "apply_link",
    ]
    st.dataframe(
        filtered[visible_cols],
        width="stretch",
        hide_index=True,
        height=520,
        column_config={"apply_link": st.column_config.LinkColumn("Apply", display_text="Open")},
    )
    with st.expander("Full tracker fields"):
        st.dataframe(df, width="stretch", hide_index=True)
    st.download_button("Export tracker CSV", dataframe_to_csv(df), file_name="career_search_tracker.csv", mime="text/csv")


def _markdown_link(value: str | None) -> str:
    return str(value) if value else ""


def _render_summary_panel() -> None:
    st.subheader("Coach Summary")
    st.markdown(st.session_state.graph_state.get("coach_summary") or "No summary yet.")


def _render_feedback_panel() -> None:
    st.subheader("Feedback")
    scored = st.session_state.graph_state.get("scored_jobs", [])
    if not scored:
        st.info("Feedback is available after scoring.")
        return
    label_to_id = {
        f"{job.get('company', 'Unknown')} | {job.get('title', 'Untitled')} | {job.get('location', 'Unknown')}": job["job_id"]
        for job in scored
    }
    selected = st.selectbox("Job", list(label_to_id.keys()))
    label = st.selectbox("Label", [item.value for item in ReviewLabel])
    notes = st.text_area("Notes", height=80)
    if st.button("Save Feedback"):
        job_id = label_to_id[selected]
        job = next(item for item in scored if item["job_id"] == job_id)
        feedback = FeedbackRecord(
            job_id=job_id,
            label=label,
            notes=notes,
            role_family=job.get("search_query", ""),
            company=job.get("company", ""),
            query=job.get("search_query", ""),
        )
        state = dict(st.session_state.graph_state)
        state.setdefault("user_feedback", []).append(feedback.model_dump(mode="json"))
        memory = update_memory_from_feedback(load_memory(), [feedback])
        save_memory(memory)
        state["search_memory"] = memory.model_dump(mode="json")
        save_graph_state(state, state.get("cache_run_path"))
        st.session_state.graph_state = state
        st.success("Feedback saved and memory updated.")
        st.rerun()


def _render_status() -> None:
    state = st.session_state.graph_state
    if not state:
        st.info("Start with the Resume tab: upload or paste a resume, then extract the profile.")
        return
    chips = [
        f"Profile: {'ready' if state.get('candidate_profile') else 'pending'}",
        f"Preferences: {'saved' if state.get('inferred_preferences') else 'pending'}",
        f"Brief: {'ready' if state.get('career_brief') else 'pending'}",
        f"Strategy: {len(state.get('search_strategy', {}).get('queries', []))} lanes",
        f"Scored: {len(state.get('scored_jobs', []))}",
    ]
    st.caption(" | ".join(chips))
    _render_trace_summary(state)
    if state.get("errors"):
        with st.expander("Warnings"):
            for error in state["errors"]:
                st.warning(error)


def _render_replay_controls() -> None:
    runs = list_run_cache_dirs()
    labels = [str(path) for path in runs]
    selected = st.selectbox("Replay cached run", [""] + labels)
    if st.button("Load Replay", width="stretch") and selected:
        state = load_graph_state(selected)
        _load_state_to_session(state)
        st.success("Loaded cached run.")
    if st.button("Load Latest", width="stretch"):
        latest = latest_cache_dir()
        if latest:
            state = load_graph_state(latest)
            _load_state_to_session(state)
            st.success("Loaded latest cached run.")


def _load_state_to_session(state: dict) -> None:
    st.session_state.graph_state = state
    st.session_state.resume_text = state.get("resume_text", "")
    st.session_state.messages = state.get("messages", [])
    st.session_state.manual_preferences = state.get("inferred_preferences", {})
    st.session_state.edited_strategy_rows = state.get("search_strategy", {}).get("queries", [])


def _render_debug_panel() -> None:
    _render_trace_summary(st.session_state.graph_state, expanded=True)
    with st.expander("Debug and Replay State"):
        st.write(f"Cache path: {st.session_state.graph_state.get('cache_run_path')}")
        st.json(st.session_state.graph_state)


def _render_trace_summary(state: dict, expanded: bool = False) -> None:
    trace = state.get("run_trace", [])
    if not trace:
        return
    rows = []
    for item in trace:
        details = item.get("details") or {}
        rows.append(
            {
                "event": item.get("event"),
                "duration_ms": item.get("duration_ms"),
                "details": truncate(str(details), 240),
            }
        )
    df = pd.DataFrame(rows)
    slow = df.dropna(subset=["duration_ms"]).sort_values("duration_ms", ascending=False).head(8)
    with st.expander("Run timing trace", expanded=expanded):
        st.caption("Slowest measured events")
        st.dataframe(slow, width="stretch", hide_index=True)
        st.caption("Full trace")
        st.dataframe(df, width="stretch", hide_index=True, height=min(420, 72 + (len(df) * 35)))


if __name__ == "__main__":
    main()
