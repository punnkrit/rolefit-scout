const demoResume = `Jordan Lee
MBA candidate with experience in product strategy, analytics, and AI workflow design.

Experience
- Led product strategy for an AI workflow prototype.
- Built SQL and Python dashboards to identify adoption trends.
- Partnered with engineering, design, and sales on product requirements.
- Supported market research and go-to-market planning.

Skills
Product management, product strategy, analytics, SQL, Python, Tableau, stakeholder management, AI products.`;

const demoProfile = {
  name: "Jordan Lee",
  experience_summary: "MBA candidate combining product strategy, analytics, and cross-functional execution across AI and SaaS products.",
  target_functions: ["AI product management", "Product strategy", "Product operations", "AI solutions"],
  strengths_for_search: ["Translates ambiguous needs into roadmaps", "Pairs business judgment with analytics", "Works fluently across technical and commercial teams"],
  skills: ["Product strategy", "SQL", "Python", "Analytics", "Go-to-market", "Stakeholder management"],
  potential_gaps: ["Direct ownership of a scaled product", "Enterprise implementation depth"]
};

const demoPreferences = {
  primary_goal: "Move into an AI product role with strategy and analytics ownership",
  target_job_titles: ["AI Product Manager", "Product Strategy Manager"],
  acceptable_adjacent_roles: ["Product Operations Manager", "AI Solutions Consultant"],
  role_families_to_avoid: ["Defense products", "Pure sales roles"],
  preferred_locations: ["Los Angeles, CA", "San Francisco, CA", "Seattle, WA", "Remote"],
  remote_preference: "hybrid",
  target_industries: ["AI software", "B2B SaaS", "Marketplaces"],
  requires_sponsorship: true,
  sponsorship_timing: "future",
  max_searches: 6
};

const demoBrief = {
  positioning: "An analytically strong product strategist who can connect customer needs, commercial priorities, and technical delivery for AI-enabled products.",
  search_thesis: "Prioritize AI product and product-strategy roles where analytics, roadmap judgment, and cross-functional leadership matter more than deep model-building experience.",
  target_role_lanes: ["AI Product Manager", "Product Strategy Manager"],
  adjacent_role_lanes: ["Product Operations", "AI Solutions Consulting"],
  excluded_lanes: ["Defense AI", "Quota-carrying sales"],
  target_industries: ["AI software", "B2B SaaS", "Marketplaces"],
  location_scope: ["California", "Seattle", "Remote"],
  sponsorship_stance: "Prioritize employers with explicit sponsorship evidence and flag ambiguous postings for verification.",
  seniority_calibration: "Target post-MBA individual-contributor and early-manager roles; avoid director-level requirements.",
  scoring_guidance: "Weight product ownership, analytics, AI workflow exposure, and cross-functional leadership. Apply a meaningful penalty for explicit work-authorization restrictions.",
  unresolved_questions: [],
  readiness: "ready_to_search",
  confidence: 0.88
};

const demoStrategy = {
  strategy_summary: "Six focused lanes balance direct AI product roles with credible strategy and solutions adjacencies.",
  job_families: ["Product management", "Product strategy", "Product operations", "AI solutions"],
  queries: [
    { query: "AI Product Manager workflow software", location: "Los Angeles, CA", rationale: "Best direct fit for AI workflow and product strategy experience.", priority: 1, strategy_type: "target_role" },
    { query: "Product Strategy Manager AI SaaS", location: "San Francisco, CA", rationale: "Uses market analysis, roadmap, and MBA toolkit.", priority: 2, strategy_type: "target_role" },
    { query: "Product Operations Manager AI", location: "Remote", rationale: "Credible adjacency with strong cross-functional execution.", priority: 3, strategy_type: "adjacent_role" },
    { query: "AI Solutions Consultant product", location: "Seattle, WA", rationale: "Pairs technical translation with client problem framing.", priority: 4, strategy_type: "adjacent_role" }
  ]
};

const demoJobs = [
  {
    rank: 1, job_id: "demo-001", company: "Northstar AI", title: "Product Manager, AI Workflows", location: "Los Angeles, CA", overall_fit_score: 91,
    recommended_action: "Apply", sponsorship_risk: "Low", sponsorship_evidence: "Posting states that sponsorship is available for qualified candidates.",
    key_matches: ["AI workflow product strategy", "SQL and analytics", "Cross-functional product leadership", "B2B software exposure"],
    key_gaps: ["Role prefers two years of direct PM ownership"], explanation: "The strongest match: it combines AI workflows, analytics, and cross-functional product execution with clear sponsorship language.",
    role_summary: "Own discovery, roadmap, and adoption for an enterprise AI workflow product.", responsibilities: ["Set product strategy and roadmap", "Partner with engineering and design", "Analyze adoption and customer feedback"],
    qualifications: ["Product strategy experience", "SQL or analytics fluency", "Strong stakeholder management"], company_insights: ["Enterprise AI workflow focus", "Explicit sponsorship language", "Cross-functional product model"],
    url: "https://example.com/jobs/northstar-ai-pm", role_fit: 5, skill_fit: 5, experience_fit: 4, location_fit: 5, industry_fit: 5, sponsorship_fit: 5,
    search_query: "AI Product Manager workflow software", source: "Demo data", date_posted: "3 days ago"
  },
  {
    rank: 2, job_id: "demo-004", company: "Helio Systems", title: "AI Solutions Consultant", location: "San Francisco, CA", overall_fit_score: 84,
    recommended_action: "Apply", sponsorship_risk: "Low", sponsorship_evidence: "Posting says the company is open to sponsoring for this role.",
    key_matches: ["AI solution framing", "Technical-to-business translation", "Stakeholder management", "Product adoption"],
    key_gaps: ["Less direct roadmap ownership"], explanation: "A strong adjacent path that rewards product judgment and technical translation, with favorable sponsorship evidence.",
    role_summary: "Scope enterprise AI solutions and guide customers from needs discovery through adoption.", responsibilities: ["Lead discovery workshops", "Translate needs into solution requirements", "Support adoption and value realization"],
    qualifications: ["Client-facing problem solving", "AI product familiarity", "Executive communication"], company_insights: ["Enterprise solutions motion", "Customer-facing role", "Sponsorship explicitly considered"],
    url: "https://example.com/jobs/helio-ai-solutions", role_fit: 4, skill_fit: 5, experience_fit: 4, location_fit: 4, industry_fit: 5, sponsorship_fit: 5,
    search_query: "AI Solutions Consultant product", source: "Demo data", date_posted: "5 days ago"
  },
  {
    rank: 3, job_id: "demo-002", company: "Cascade Cloud", title: "Product Strategy Manager", location: "Seattle, WA", overall_fit_score: 79,
    recommended_action: "Maybe", sponsorship_risk: "Unknown", sponsorship_evidence: "Work-authorization policy is not stated in the posting.",
    key_matches: ["Market research", "Pricing analysis", "Roadmap recommendations", "MBA preferred"],
    key_gaps: ["Sponsorship must be verified", "Limited direct cloud-platform experience"], explanation: "Excellent strategy alignment, but the sponsorship position and cloud-domain depth need confirmation before prioritizing.",
    role_summary: "Shape portfolio strategy, pricing, and roadmap recommendations for a cloud software business.", responsibilities: ["Develop market and competitor insights", "Evaluate pricing opportunities", "Advise product leadership on portfolio choices"],
    qualifications: ["Strategy or product experience", "Advanced analytics", "MBA preferred"], company_insights: ["Cloud SaaS portfolio", "Strategy-heavy mandate", "Sponsorship not disclosed"],
    url: "https://example.com/jobs/cascade-product-strategy", role_fit: 5, skill_fit: 4, experience_fit: 4, location_fit: 4, industry_fit: 4, sponsorship_fit: 2,
    search_query: "Product Strategy Manager AI SaaS", source: "Demo data", date_posted: "1 week ago"
  },
  {
    rank: 4, job_id: "demo-006", company: "Signalworks", title: "Product Operations Manager", location: "Remote", overall_fit_score: 74,
    recommended_action: "Maybe", sponsorship_risk: "Medium", sponsorship_evidence: "Remote within the U.S.; sponsorship is reviewed case by case.",
    key_matches: ["Product analytics", "Operating cadence", "Cross-functional planning", "Remote preference"],
    key_gaps: ["Operations-heavy scope", "Sponsorship is conditional"], explanation: "A practical adjacency with strong analytics fit, though it offers less product discovery and uncertain sponsorship.",
    role_summary: "Build the systems, insights, and planning rhythm that help a distributed product organization scale.", responsibilities: ["Own product operating cadence", "Build KPI reporting", "Improve planning and launch processes"],
    qualifications: ["Product operations experience", "Analytics fluency", "Program leadership"], company_insights: ["Distributed team", "Operational maturity focus", "Case-by-case sponsorship"],
    url: "https://example.com/jobs/signalworks-product-ops", role_fit: 4, skill_fit: 4, experience_fit: 4, location_fit: 5, industry_fit: 4, sponsorship_fit: 3,
    search_query: "Product Operations Manager AI", source: "Demo data", date_posted: "6 days ago"
  },
  {
    rank: 5, job_id: "demo-003", company: "Metro Marketplace", title: "Business Operations Manager", location: "New York, NY", overall_fit_score: 58,
    recommended_action: "Skip", sponsorship_risk: "High", sponsorship_evidence: "Posting requires unrestricted U.S. work authorization without sponsorship.",
    key_matches: ["Marketplace analytics", "Executive reporting", "Business operations"],
    key_gaps: ["Explicit sponsorship restriction", "Outside preferred geography", "Less direct product ownership"], explanation: "The operating skill match is real, but work-authorization language and location make this a low-priority lead.",
    role_summary: "Drive operating analysis and executive planning for a consumer marketplace.", responsibilities: ["Build operating reviews", "Analyze marketplace performance", "Coordinate strategic initiatives"],
    qualifications: ["Business operations experience", "Advanced Excel or SQL", "Executive communication"], company_insights: ["Marketplace business model", "New York office", "No sponsorship"],
    url: "https://example.com/jobs/metro-bizops", role_fit: 3, skill_fit: 4, experience_fit: 4, location_fit: 2, industry_fit: 4, sponsorship_fit: 1,
    search_query: "Business Operations Manager marketplace", source: "Demo data", date_posted: "2 days ago"
  }
];

export const demoState: Record<string, any> = {
  resume_text: demoResume,
  candidate_profile: demoProfile,
  inferred_preferences: demoPreferences,
  career_brief: demoBrief,
  open_questions: [],
  search_strategy: demoStrategy,
  approved_strategy: { approved: true, queries: demoStrategy.queries },
  query_diagnostics: demoStrategy.queries.map((query, index) => ({ ...query, result_count: [18, 14, 11, 9][index] })),
  scored_jobs: demoJobs,
  coach_summary: "Two roles are strong apply-now matches. Verify sponsorship before investing in the strategy and product-operations leads.",
  user_feedback: [],
  cache_run_id: "rolefit-demo",
  cache_run_label: "Fictional product candidate · demo",
  demo_mode: true,
  live_search_enabled: false,
  errors: []
};

export function freshDemoState() {
  return structuredClone(demoState);
}
