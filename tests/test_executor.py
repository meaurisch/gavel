from pathlib import Path
import pytest
from core.executor import make_runner
from core.models import TaskSpec, Trial
from core.db import connect, insert_trial, trial_exists
from core.executor import execute_all
from runners.claude_code import ClaudeCodeRunner
from runners.nop import NopRunner
from runners.oracle import OracleRunner
from runners.manual import ManualRunner


def _make_task():
    return TaskSpec(
        id="t", repo_url="https://github.com/Example/Repo",
        base_commit="abc", instruction="x", run_cmd="echo ok",
        held_out_tests_path="tests/", reference_diff_path="ref.diff",
    )


def test_make_runner_claude():
    assert isinstance(make_runner("claude-code", _make_task()), ClaudeCodeRunner)


def test_make_runner_oracle():
    assert isinstance(make_runner("oracle", _make_task()), OracleRunner)


def test_make_runner_nop():
    assert isinstance(make_runner("nop", _make_task()), NopRunner)


def test_make_runner_manual():
    assert isinstance(make_runner("manual", _make_task()), ManualRunner)


def test_make_runner_unknown():
    with pytest.raises(ValueError, match="Unknown runner"):
        make_runner("nonexistent", _make_task())


def test_execute_all_skips_existing(tmp_path):
    conn = connect(tmp_path / "test.db")
    trial = Trial(id="t-1", task_id="t", methodology_id="s", repo_context_id="none", model="m", runner="nop", rep=0)
    insert_trial(conn, trial)

    results = execute_all([trial], conn)
    assert len(results) == 1
    assert results[0].get("skipped") is True


def test_execute_trial_propagates_run_result_error(tmp_path):
    """A runner returning RunResult(error=...) propagates it to summary["error"]."""
    from unittest.mock import MagicMock, patch
    from core.executor import execute_trial
    from core.models import GateResult, MethodologySpec, RepoContextSpec, RunResult

    trial = Trial(id="t-err", task_id="t", methodology_id="s", repo_context_id="none", model="m", runner="nop", rep=0)
    conn = connect(tmp_path / "test.db")

    stub_run_result = RunResult(
        trial_id="t-err", diff="", exit_status=0, wall_seconds=0.1, error="parse failed"
    )

    class StubRunner:
        last_cost = None
        def prepare(self, *args, **kwargs): pass
        def execute(self, *args, **kwargs): return stub_run_result

    stub_gate = GateResult(trial_id="t-err", passed=False)

    with patch("core.executor.load_task"), \
         patch("core.executor.HARNESS_MAP", {}), \
         patch("core.executor.load_methodology", return_value=MethodologySpec(id="s", files={})), \
         patch("core.executor.load_repo_context", return_value=RepoContextSpec(id="none", files={})), \
         patch("core.executor.resolve_repo_path", return_value=tmp_path), \
         patch("core.executor.create_worktree", return_value=tmp_path), \
         patch("core.executor.destroy_worktree"), \
         patch("core.executor.make_runner", return_value=StubRunner()), \
         patch("core.executor.gate_apply", return_value=stub_gate), \
         patch("core.executor.persist_trial_result"):
        summary = execute_trial(trial, conn)

    assert summary["error"] == "parse failed"


def test_execute_trial_keeps_worktree_when_requested(tmp_path):
    """keep_worktree=True must skip teardown and surface the worktree path so the
    laid-down commits can be inspected after the run."""
    from unittest.mock import patch
    from core.executor import execute_trial
    from core.models import GateResult, MethodologySpec, RepoContextSpec, RunResult

    trial = Trial(id="t-keep", task_id="t", methodology_id="s", repo_context_id="none", model="m", runner="nop", rep=0)
    conn = connect(tmp_path / "test.db")
    wt = tmp_path / "wt"
    wt.mkdir()

    stub_run_result = RunResult(trial_id="t-keep", diff="", exit_status=0, wall_seconds=0.1, error=None)

    class StubRunner:
        last_cost = None
        def prepare(self, *args, **kwargs): pass
        def execute(self, *args, **kwargs): return stub_run_result

    with patch("core.executor.load_task"), \
         patch("core.executor.HARNESS_MAP", {}), \
         patch("core.executor.load_methodology", return_value=MethodologySpec(id="s", files={})), \
         patch("core.executor.load_repo_context", return_value=RepoContextSpec(id="none", files={})), \
         patch("core.executor.resolve_repo_path", return_value=tmp_path), \
         patch("core.executor.create_worktree", return_value=wt), \
         patch("core.executor.destroy_worktree") as mock_destroy, \
         patch("core.executor.make_runner", return_value=StubRunner()), \
         patch("core.executor.gate_apply", return_value=GateResult(trial_id="t-keep", passed=True)), \
         patch("core.executor.persist_trial_result"):
        summary = execute_trial(trial, conn, keep_worktree=True)

    mock_destroy.assert_not_called()
    assert summary["worktree"] == str(wt)


def test_execute_trial_persists_cost_when_gate_raises(tmp_path):
    """A gate exception must NOT discard an already-incurred cost. The trial,
    run_result, and cost_record must persist, and the gate is recorded as a FAIL.

    Regression: the shakedown's opus trial crashed in the gate (agent wrote a file
    at the held-out test path) and the whole trial — including its real, billed
    cost — was silently dropped, recording $0 / nothing.
    """
    from unittest.mock import patch
    from core.executor import execute_trial
    from core.db import get_cost_record, get_gate_result, get_run_result, get_trial
    from core.models import CostRecord, MethodologySpec, RepoContextSpec, RunResult
    from runners.claude_code import ClaudeCodeRunner

    trial = Trial(id="t-gate-crash", task_id="t", methodology_id="s", repo_context_id="none", model="claude-opus-4-8", runner="claude-code", rep=0)
    conn = connect(tmp_path / "test.db")

    cost = CostRecord(
        trial_id="t-gate-crash", native_unit="usd_self_reported", native_amount=1.84,
        usd_equiv=1.84, input_tokens=100, output_tokens=200, cache_read_tokens=300,
    )
    stub_run_result = RunResult(trial_id="t-gate-crash", diff="some diff", exit_status=0, wall_seconds=0.1, error=None)

    class StubRunner(ClaudeCodeRunner):
        def __init__(self):
            self.last_cost = cost
        def prepare(self, *a, **k): pass
        def execute(self, *a, **k): return stub_run_result

    with patch("core.executor.load_task"), \
         patch("core.executor.HARNESS_MAP", {}), \
         patch("core.executor.load_methodology", return_value=MethodologySpec(id="s", files={})), \
         patch("core.executor.load_repo_context", return_value=RepoContextSpec(id="none", files={})), \
         patch("core.executor.resolve_repo_path", return_value=tmp_path), \
         patch("core.executor.create_worktree", return_value=tmp_path), \
         patch("core.executor.destroy_worktree"), \
         patch("core.executor.make_runner", return_value=StubRunner()), \
         patch("core.executor.gate_apply", side_effect=AssertionError("held-out test already present")):
        summary = execute_trial(trial, conn)

    # Cost survives the gate crash — the whole point.
    saved = get_cost_record(conn, "t-gate-crash")
    assert saved is not None, "cost_record was discarded when the gate raised"
    assert saved.usd_equiv == pytest.approx(1.84)
    # Trial + run_result persisted (diff captured).
    assert get_trial(conn, "t-gate-crash") is not None
    rr = get_run_result(conn, "t-gate-crash")
    assert rr is not None and rr.diff == "some diff"
    # Gate recorded as a FAIL, not lost.
    gr = get_gate_result(conn, "t-gate-crash")
    assert gr is not None and gr.passed is False
    # Summary still carries the cost and surfaces the gate error.
    assert summary["usd"] == pytest.approx(1.84)
    assert "held-out test already present" in (summary["error"] or "")


def test_execute_trial_wall_covers_whole_trial(tmp_path):
    """summary['wall_seconds'] must span the full execute_trial call (runner + gate),
    not just run_result.wall_seconds."""
    from unittest.mock import MagicMock, patch, call
    from core.executor import execute_trial
    from core.models import GateResult, MethodologySpec, RepoContextSpec, RunResult

    trial = Trial(id="t-wall", task_id="t", methodology_id="s", repo_context_id="none", model="m", runner="nop", rep=0)
    conn = connect(tmp_path / "test.db")

    runner_wall = 1.5  # runner-only time stored in RunResult
    stub_run_result = RunResult(
        trial_id="t-wall", diff="", exit_status=0, wall_seconds=runner_wall, error=None
    )

    class StubRunner:
        last_cost = None
        def prepare(self, *args, **kwargs): pass
        def execute(self, *args, **kwargs): return stub_run_result

    stub_gate = GateResult(trial_id="t-wall", passed=True)

    # time.monotonic sequence: trial_start=10.0, trial_end=17.0 → whole-trial wall=7.0
    monotonic_values = iter([10.0, 17.0])

    with patch("core.executor.load_task"), \
         patch("core.executor.HARNESS_MAP", {}), \
         patch("core.executor.load_methodology", return_value=MethodologySpec(id="s", files={})), \
         patch("core.executor.load_repo_context", return_value=RepoContextSpec(id="none", files={})), \
         patch("core.executor.resolve_repo_path", return_value=tmp_path), \
         patch("core.executor.create_worktree", return_value=tmp_path), \
         patch("core.executor.destroy_worktree"), \
         patch("core.executor.make_runner", return_value=StubRunner()), \
         patch("core.executor.gate_apply", return_value=stub_gate), \
         patch("core.executor.persist_trial_result"), \
         patch("core.executor.time") as mock_time:
        mock_time.monotonic.side_effect = lambda: next(monotonic_values)
        summary = execute_trial(trial, conn)

    assert summary["wall_seconds"] == pytest.approx(7.0), (
        f"Expected whole-trial wall 7.0 but got {summary['wall_seconds']}; "
        f"wall must not be runner-only ({runner_wall})"
    )
