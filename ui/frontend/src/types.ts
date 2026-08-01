// API payload types — mirror ui/server.py's pydantic models.

export type Axis = "methodology" | "model" | "repo_context" | "runner";

export const AXES: Axis[] = ["methodology", "model", "repo_context", "runner"];

export const AXIS_LABELS: Record<Axis, string> = {
  methodology: "Methodology",
  model: "Model",
  repo_context: "Repo context",
  runner: "Runner",
};

// cell dicts use trial column names
export const AXIS_CELL_KEYS: Record<Axis, string> = {
  methodology: "methodology_id",
  model: "model",
  repo_context: "repo_context_id",
  runner: "runner",
};

export interface DbInfo {
  name: string;
  is_default: boolean;
  n_trials: number;
  n_passers: number;
  n_judgments: number;
  n_sessions: number;
  total_usd: number;
  modified_at: number;
}

export interface TaskEntry {
  id: string;
  available_locally: boolean;
  instruction: string | null;
  difficulty: string | null;
  repo: string | null;
  build_cmd: string | null;
  run_cmd: string | null;
  visible_test_cmd: string | null;
  n_trials: number;
  n_passers: number;
}

export interface SpecEntry {
  id: string;
  available_locally: boolean;
  description: string | null;
  noop: boolean;
  source: { repo: string; commit: string } | null;
  harnesses: Record<string, string[]>;
  task_affinity: string[];
  n_trials: number;
  n_passers: number;
}

export interface ModelEntry {
  id: string;
  pricing: {
    vendor: string;
    input_per_mtok: number;
    output_per_mtok: number;
    cache_read_per_mtok: number;
  } | null;
  n_trials: number;
  n_passers: number;
}

export interface RunnerEntry {
  id: string;
  paid: boolean;
  browser_launchable: boolean;
  description: string;
  n_trials: number;
  n_passers: number;
}

export interface Catalog {
  tasks: TaskEntry[];
  methodologies: SpecEntry[];
  repo_contexts: SpecEntry[];
  models: ModelEntry[];
  model_aliases: Record<string, string>;
  runners: RunnerEntry[];
}

export interface GradingStatus {
  total_hidden_gate_passers: number;
  axes: Record<string, { distinct_passing_values: number; gradeable_cells: number }>;
}

export interface Cell {
  task_id: string;
  methodology_id?: string;
  repo_context_id?: string;
  model?: string;
  runner?: string;
  n_values: number;
  n_pairs: number;
}

export interface DiffProxy {
  lines_added: number;
  lines_removed: number;
  files_touched: number;
  file_list: string[];
  new_deps: string[];
}

export interface TierDetail {
  passed: boolean | null;
  output: string | null;
  truncated: boolean;
}

export interface GateDetail {
  passed: boolean;
  compile: TierDetail;
  visible: TierDetail;
  hidden: TierDetail;
}

// During blind judging sides carry NO cost/token/time fields — spend
// metrics bias judgment (user decision 2026-07-05). `metrics` is populated
// only once the session has been revealed (closed + values public).
export interface BlindSide {
  label: "A" | "B";
  diff: string;
  proxy: DiffProxy;
  gate: {
    compile_passed: boolean | null;
    visible_passed: boolean | null;
    hidden_passed: boolean | null;
  };
  gate_detail: GateDetail | null;
  metrics: {
    usd: number | null;
    input_tokens: number | null;
    output_tokens: number | null;
    wall_seconds: number | null;
  } | null;
}

export interface Pair {
  pair_index: number;
  total_pairs: number;
  left: BlindSide;
  right: BlindSide;
}

export type GradingMode = "human" | "llm";

export interface Session {
  session_id: string;
  axis: Axis;
  cell: Record<string, string>;
  total_pairs: number;
  pairs: Pair[];
  judged: { pair_index: number; choice: string }[];
  created_at: string | null;
  revealed_at: string | null;
  mode: GradingMode;
  judge_provider: string | null;
  judge_model: string | null;
}

export interface SessionSummary {
  session_id: string;
  axis: Axis;
  cell: Record<string, string>;
  total_pairs: number;
  n_judged: number;
  created_at: string;
  revealed_at: string | null;
  mode: GradingMode;
  judge_provider: string | null;
  judge_model: string | null;
}

export interface OriginalFile {
  path: string;
  status: "ok" | "new" | "unavailable" | "differs";
  content: string | null;
  left_content: string | null;
  right_content: string | null;
}

export interface OriginalsResponse {
  pair_index: number;
  files: OriginalFile[];
  note: string | null;
}

export interface RevealPairInfo {
  pair_index: number;
  left_value: string;
  right_value: string;
  choice: string | null;
  rationale: string | null;
  confidence: number | null;
  position_consistent: boolean | null;
  truncated: boolean | null;
  // E2.1: true marks a consistency probe (side-swapped repeat pair) —
  // measured the judge, excluded from the ranking. Post-reveal only.
  is_probe: boolean | null;
}

// E2.1 judge-consistency numbers from the session's repeat probes.
export interface ProbeStats {
  n_probes: number;
  n_evaluated: number;
  n_agree: number;
  n_flips: number;
  self_agreement: number | null;
  flip_rate: number | null;
}

export interface JudgeSessionStats {
  provider: string | null;
  model: string | null;
  passes: number | null;
  n_calls: number;
  input_tokens: number;
  output_tokens: number;
  usd_equiv: number;
  wall_seconds: number;
  n_errors: number;
  n_consistent: number;
  n_inconsistent: number;
}

export interface RevealResponse {
  revealed: boolean;
  pairs: RevealPairInfo[];
  summary: Record<string, { wins: number; losses: number; ties: number }>;
  axis: Axis;
  cell: Record<string, string>;
  n_judged: number;
  n_unjudged: number;
  total_pairs: number;
  revealed_at: string | null;
  bt_scores: { axis_value: string; elo: number; ci_lower: number; ci_upper: number }[] | null;
  analyzer_flags: {
    non_discriminating_tasks: string[];
    flaky_tasks: string[];
    cost_quality_notes: string[];
  } | null;
  pass_rates: Record<string, number> | null;
  mode: GradingMode;
  judge_stats: JudgeSessionStats | null;
  probe_stats: ProbeStats | null;
}

export interface TrialRow {
  id: string;
  task_id: string;
  methodology_id: string;
  repo_context_id: string;
  model: string;
  runner: string;
  rep: number;
  passed: boolean | null;
  compile_passed: boolean | null;
  visible_passed: boolean | null;
  hidden_passed: boolean | null;
  usd_equiv: number | null;
  input_tokens: number | null;
  output_tokens: number | null;
  cache_read_tokens: number | null;
  wall_seconds: number | null;
  exit_status: number | null;
  error: string | null;
}

export interface TrialDetail {
  trial: {
    id: string;
    task_id: string;
    methodology_id: string;
    repo_context_id: string;
    model: string;
    runner: string;
    rep: number;
  };
  run_result: {
    diff: string;
    exit_status: number;
    wall_seconds: number;
    error: string | null;
  } | null;
  gate_result: {
    passed: boolean;
    compile_passed: boolean | null;
    compile_output: string | null;
    visible_passed: boolean | null;
    visible_output: string | null;
    hidden_passed: boolean | null;
    hidden_output: string | null;
  } | null;
  cost_record: {
    usd_equiv: number;
    native_amount: number;
    native_unit: string;
    input_tokens: number;
    output_tokens: number;
    cache_read_tokens: number;
  } | null;
}

export interface ReportSummary {
  value: string;
  n_trials: number;
  n_gated: number;
  gate_pass_rate: number | null;
  tier_pass_rates: Record<string, number | null>;
  total_usd: number;
  mean_usd: number | null;
  n_comparisons: number;
  bt_strength: number | null;
  bt_ci: [number, number] | null;
  bt_ci_elo: [number, number] | null;
  elo: number | null;
  on_frontier: boolean;
}

export interface AgreementBlock {
  n_shared: number;
  n_agree: number;
  rate: number | null;
  kappa: number | null;
}

export interface Report {
  axis: Axis;
  cell: Record<string, string>;
  summaries: ReportSummary[];
  picks: { high_stakes: string | null; routine: string | null };
  flag_lines: string[];
  n_judgments: number;
  n_sessions: number;
  grader: "all" | "human" | "llm";
  agreement: AgreementBlock;
  probe_stats: ProbeStats | null;
  orphan_judgments: number;
  ignored_pin: string | null;
  artifacts: { name: string; modified_at: number; url: string }[];
}

export interface PlannedTrial {
  id: string;
  task_id: string;
  methodology_id: string;
  repo_context_id: string;
  model: string;
  runner: string;
  rep: number;
}

export interface RunPlan {
  trials: PlannedTrial[];
  n_trials: number;
  runner: string;
  paid: boolean;
  launchable: boolean;
  launch_blocked_reason: string | null;
  confirm_phrase: string | null;
  estimate: {
    n_trials: number;
    n_with_estimate: number;
    estimated_total_usd: number | null;
    estimate_covers_all_trials: boolean;
    per_trial: { trial_id: string; est_usd: number | null; basis: string | null }[];
    pricing_rates: Record<
      string,
      { input_per_mtok: number; output_per_mtok: number; cache_read_per_mtok: number }
    > | null;
  } | null;
}

export interface RunEvent {
  type: "progress" | "status" | "end";
  index?: number;
  trial_id?: string;
  summary?: {
    passed?: boolean | null;
    usd?: number;
    tokens?: number;
    wall_seconds?: number;
    error?: string | null;
    skipped?: boolean;
  };
  status?: string;
  error?: string | null;
  ts?: number;
}

export interface RunSnapshot {
  id: string;
  params: Record<string, unknown>;
  db: string;
  status: "running" | "done" | "error" | "cancelled";
  error: string | null;
  trials?: PlannedTrial[];
  n_trials: number;
  n_done: number;
  events?: RunEvent[];
  created_at: number;
  finished_at: number | null;
}

// --- LLM judge -------------------------------------------------------------

export interface JudgeProviderInfo {
  id: string;
  label: string;
  billing: "subscription" | "metered" | "free";
  available: boolean;
  reason: string | null;
  models: string[];
  default_model: string;
  confirm_phrase: string | null;
}

export interface JudgePlan {
  axis: string;
  provider: string;
  judge_model: string;
  passes: number;
  billing: "subscription" | "metered" | "free";
  available: boolean;
  reason: string | null;
  n_pairs: number;
  n_calls: number;
  est_input_tokens: number;
  est_output_tokens: number;
  est_usd: number | null;
  confirm_phrase: string | null;
}

export interface JudgeEvent {
  type: "pair" | "status" | "end";
  index?: number;
  choice?: string;
  position_consistent?: boolean | null;
  truncated?: boolean;
  status?: string;
  error?: string | null;
  ts?: number;
}

export interface JudgeRunSnapshot {
  id: string;
  session_id: string;
  db: string;
  provider: string;
  model: string;
  passes: number;
  status: "running" | "done" | "error" | "cancelled";
  error: string | null;
  n_pairs: number;
  n_done: number;
  n_consistent: number;
  events?: JudgeEvent[];
  created_at: number;
  finished_at: number | null;
}
