from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.models import CostRecord, MethodologySpec, RunResult, TaskSpec, Trial
from core.worktree import create_worktree, destroy_worktree
from cost.claude_usage import ClaudeUsageParseError, ClaudeUsageResult, parse_claude_output
from runners.base import Runner
from runners.claude_code import ClaudeCodeRunner
from tests.conftest import head_commit


def _make_task() -> TaskSpec:
    return TaskSpec(
        id="t", repo_url="x", base_commit="x", instruction="say hello",
        run_cmd="echo ok", held_out_tests_path="x", reference_diff_path="x",
    )


def _make_trial() -> Trial:
    return Trial(id="t-cc", task_id="t", methodology_id="off", model="claude-sonnet-4-20250514", runner="claude_code", rep=0)


def _valid_claude_json(result: str = "Done", cost: float = 0.05, input_t: int = 1000, output_t: int = 500, cache_t: int = 200) -> str:
    return json.dumps({
        "result": result,
        "is_error": False,
        "total_cost_usd": cost,
        "usage": {
            "input_tokens": input_t,
            "output_tokens": output_t,
            "cache_read_input_tokens": cache_t,
        },
        "modelUsage": {
            "claude-sonnet-4-20250514": {
                "input_tokens": input_t,
                "output_tokens": output_t,
                "cache_read_input_tokens": cache_t,
            }
        },
        "num_turns": 2,
    })


# --- Parser unit tests ---

def test_parse_success_json():
    result = parse_claude_output(_valid_claude_json())
    assert result.total_cost_usd == 0.05
    assert result.input_tokens == 1000
    assert result.output_tokens == 500
    assert result.cache_read_tokens == 200
    assert result.result_text == "Done"
    assert result.is_error is False


def test_parse_error_field():
    data = {"total_cost_usd": 0.01, "result": "", "is_error": True, "error": "Something failed", "usage": {"input_tokens": 100, "output_tokens": 0, "cache_read_input_tokens": 0}}
    result = parse_claude_output(data)
    assert result.is_error is True
    assert result.error_message == "Something failed"


def test_parse_empty_result_with_tokens():
    data = {"total_cost_usd": 0.03, "result": "", "usage": {"input_tokens": 500, "output_tokens": 200, "cache_read_input_tokens": 100}}
    result = parse_claude_output(data)
    assert result.is_error is True
    assert "Empty result" in result.error_message


def test_parse_malformed_json_raises():
    with pytest.raises(ClaudeUsageParseError, match="Invalid JSON"):
        parse_claude_output("not json at all {{{")


def test_parse_missing_cost_raises():
    with pytest.raises(ClaudeUsageParseError, match="Missing total_cost_usd"):
        parse_claude_output({"result": "hi", "usage": {"input_tokens": 1}})


def test_parse_model_usage_fallback():
    data = {
        "total_cost_usd": 0.08,
        "result": "Done",
        "modelUsage": {
            "claude-sonnet-4-20250514": {"input_tokens": 600, "output_tokens": 300, "cache_read_input_tokens": 100},
            "claude-haiku-4-5-20251001": {"input_tokens": 400, "output_tokens": 200, "cache_read_input_tokens": 50},
        },
    }
    result = parse_claude_output(data)
    assert result.input_tokens == 1000
    assert result.output_tokens == 500
    assert result.cache_read_tokens == 150
    assert result.is_error is False


# --- Runner protocol ---

def test_claude_code_runner_conforms_to_protocol():
    assert isinstance(ClaudeCodeRunner(_make_task()), Runner)


# --- Runner execute with mocked subprocess ---

def test_execute_success_mock(tiny_repo):
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        task = _make_task()
        trial = _make_trial()
        runner = ClaudeCodeRunner(task)
        methodology = MethodologySpec(id="off", files={})
        runner.prepare(trial, wt, methodology)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = _valid_claude_json()
        mock_proc.stderr = ""

        with patch("runners.claude_code.subprocess.run", return_value=mock_proc):
            result = runner.execute(trial, wt)

        assert result.exit_status == 0
        assert result.trial_id == "t-cc"
        assert result.wall_seconds >= 0
        assert runner.last_cost is not None
        assert runner.last_cost.input_tokens == 1000
        assert runner.last_cost.native_unit == "usd_self_reported"
    finally:
        destroy_worktree(wt)


def test_execute_nonzero_exit_mock(tiny_repo):
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        task = _make_task()
        trial = _make_trial()
        runner = ClaudeCodeRunner(task)
        methodology = MethodologySpec(id="off", files={})
        runner.prepare(trial, wt, methodology)

        mock_proc = MagicMock()
        mock_proc.returncode = 1
        mock_proc.stdout = _valid_claude_json()
        mock_proc.stderr = "some error"

        with patch("runners.claude_code.subprocess.run", return_value=mock_proc):
            result = runner.execute(trial, wt)

        assert result.exit_status == 1
        assert runner.last_cost is not None
    finally:
        destroy_worktree(wt)


def test_execute_empty_result_overrides_exit(tiny_repo):
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        task = _make_task()
        trial = _make_trial()
        runner = ClaudeCodeRunner(task)
        methodology = MethodologySpec(id="off", files={})
        runner.prepare(trial, wt, methodology)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = _valid_claude_json(result="", input_t=500)
        mock_proc.stderr = ""

        with patch("runners.claude_code.subprocess.run", return_value=mock_proc):
            result = runner.execute(trial, wt)

        assert result.exit_status == 1
        assert runner.last_cost is not None
        assert runner.last_cost.input_tokens == 500
    finally:
        destroy_worktree(wt)


def test_last_cost_none_on_parse_failure(tiny_repo):
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        task = _make_task()
        trial = _make_trial()
        runner = ClaudeCodeRunner(task)
        methodology = MethodologySpec(id="off", files={})
        runner.prepare(trial, wt, methodology)

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "not json at all"
        mock_proc.stderr = ""

        with patch("runners.claude_code.subprocess.run", return_value=mock_proc):
            result = runner.execute(trial, wt)

        assert runner.last_cost is None
    finally:
        destroy_worktree(wt)


# --- Integration smoke test ---

@pytest.mark.integration
def test_smoke_real_claude(tiny_repo):
    if shutil.which("claude") is None:
        pytest.skip("claude CLI not found on PATH")
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        task = TaskSpec(
            id="smoke", repo_url="local", base_commit=commit,
            instruction="Create a file called output.txt containing the word 'done'",
            run_cmd="echo ok", held_out_tests_path="x", reference_diff_path="x",
        )
        trial = Trial(id="t-smoke", task_id="smoke", methodology_id="off", model="claude-sonnet-4-20250514", runner="claude_code", rep=0)
        methodology = MethodologySpec(id="off", files={})
        runner = ClaudeCodeRunner(task, max_turns=5)
        runner.prepare(trial, wt, methodology)
        result = runner.execute(trial, wt)

        assert runner.last_cost is not None
        assert runner.last_cost.input_tokens > 0
        assert runner.last_cost.output_tokens > 0
        assert result.wall_seconds > 0
    finally:
        destroy_worktree(wt)
