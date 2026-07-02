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


@dataclass
class GradingSession:
    """A persisted grading session: which axis was compared, in which cell,
    over which ordered trial pairs. Persisting this (not just the judgments)
    lets the Bradley-Terry ranking be rebuilt after a server restart and lets
    `report` consume past sessions."""
    id: str
    axis: str
    cell: dict[str, str]           # task_id + the pinned axis values
    pairs: list[tuple[str, str]]   # ordered (left_trial_id, right_trial_id)
    created_at: str


@dataclass
class LeakageReport:
    hits: list[str]
    any_found: bool


ALL_MODELS = (TaskSpec, MethodologySpec, RepoContextSpec, Trial, RunResult, CostRecord, GateResult, Judgment, GradingSession, LeakageReport)
