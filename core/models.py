from pydantic.dataclasses import dataclass
from pydantic import TypeAdapter


@dataclass
class TaskSpec:
    id: str
    repo_url: str
    base_commit: str
    instruction: str
    run_cmd: str
    held_out_tests_path: str
    reference_diff_path: str
    build_cmd: str | None = None
    visible_test_cmd: str | None = None
    difficulty: str | None = None        # "easy" | "medium" | "hard"
    repo: str | None = None              # local repos/<repo> dir; else repo_url basename
    visible_tests_path: str | None = None  # dir of EXTRA visible test files to inject


@dataclass
class MethodologySpec:
    id: str
    files: dict[str, list[str]]


@dataclass
class RepoContextSpec:
    id: str
    files: dict[str, list[str]]


@dataclass
class Trial:
    id: str
    task_id: str
    methodology_id: str
    repo_context_id: str
    model: str
    runner: str
    rep: int


@dataclass
class RunResult:
    trial_id: str
    diff: str
    exit_status: int
    wall_seconds: float
    error: str | None = None


@dataclass
class CostRecord:
    trial_id: str
    native_unit: str
    native_amount: float
    usd_equiv: float
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int


@dataclass
class GateResult:
    trial_id: str
    passed: bool
    compile_passed: bool | None = None
    compile_output: str | None = None
    visible_passed: bool | None = None
    visible_output: str | None = None
    hidden_passed: bool | None = None
    hidden_output: str | None = None


@dataclass
class Judgment:
    id: str
    session_id: str
    task_id: str
    model: str
    left_trial_id: str
    right_trial_id: str
    choice: str
    rubric_correctness: str | None
    rubric_minimality: str | None
    rubric_readability: str | None
    rubric_overengineering: str | None
    created_at: str
    # Who judged: "human" or "llm:<provider>:<model>". Human and LLM verdicts
    # are never silently mixed — reports can filter on this.
    grader: str = "human"
    rationale: str | None = None           # LLM judge's reasoning (post-reveal only)
    confidence: float | None = None        # 0-1, LLM self-reported
    position_consistent: bool | None = None  # both swapped passes agreed?
    # True when the judge saw a budget-truncated diff — the verdict covers a
    # prefix of the change and the reveal must say so. None for human mode.
    truncated: bool | None = None
    # E2.1: True when this verdict was on a consistency probe (a deliberate
    # side-swapped repeat pair). Probe verdicts measure the judge and are
    # excluded from Bradley-Terry. None on sessions without probes.
    is_probe: bool | None = None


@dataclass
class GradingSession:
    """A persisted grading session: which axis was compared, in which cell,
    over which ordered trial pairs. Persisting this (not just the judgments)
    lets the Bradley-Terry ranking be rebuilt after a server restart and lets
    `report` consume past sessions.

    revealed_at closes the session: once the grader has seen the unblinded
    pair assignments, further judgments would no longer be blind, so the
    server refuses them permanently."""
    id: str
    axis: str
    cell: dict[str, str]           # task_id + the pinned axis values
    pairs: list[tuple[str, str]]   # ordered (left_trial_id, right_trial_id)
    created_at: str
    revealed_at: str | None = None
    # Grading mode: "human" (blind manual judging) or "llm" (LLM judge).
    mode: str = "human"
    judge_provider: str | None = None   # e.g. "claude-cli" | "gh-models" | "mock"
    judge_model: str | None = None
    judge_passes: int | None = None     # 1 or 2 (position-swapped)
    # E2.1 consistency probes: {probe_pair_index: original_pair_index}. The
    # probe pair is its original with sides swapped. None = session predates
    # probes or was built without them (LLM judge sessions).
    probe_of: dict[int, int] | None = None


@dataclass
class JudgeCallRecord:
    """One LLM-judge provider call — the usage/cost audit trail. Failed calls
    are recorded too: they were billed."""
    id: str
    session_id: str
    pair_index: int
    ordering: str                  # "AB" | "BA"
    provider: str
    model: str
    status: str                    # "ok" | "parse_error" | "provider_error"
    input_tokens: int
    output_tokens: int
    usd_equiv: float | None
    wall_seconds: float
    error: str | None
    created_at: str


@dataclass
class LeakageReport:
    hits: list[str]
    any_found: bool


ALL_MODELS = (TaskSpec, MethodologySpec, RepoContextSpec, Trial, RunResult, CostRecord, GateResult, Judgment, GradingSession, JudgeCallRecord, LeakageReport)
