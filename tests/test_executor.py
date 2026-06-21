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
    trial = Trial(id="t-1", task_id="t", setup_id="s", model="m", runner="nop", rep=0)
    insert_trial(conn, trial)

    results = execute_all([trial], conn)
    assert len(results) == 1
    assert results[0].get("skipped") is True
