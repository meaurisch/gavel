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
    test_output: str


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
class LeakageReport:
    hits: list[str]
    any_found: bool


ALL_MODELS = (TaskSpec, MethodologySpec, RepoContextSpec, Trial, RunResult, CostRecord, GateResult, Judgment, LeakageReport)
