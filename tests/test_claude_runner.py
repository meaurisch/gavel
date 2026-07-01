from __future__ import annotations

import json
import shutil
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.models import CostRecord, MethodologySpec, RepoContextSpec, RunResult, TaskSpec, Trial
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
    return Trial(id="t-cc", task_id="t", methodology_id="off", repo_context_id="none", model="claude-sonnet-4-20250514", runner="claude_code", rep=0)


_FIXTURES = Path(__file__).parent / "fixtures"


def _load_fixture(name: str) -> str:
    return (_FIXTURES / name).read_text(encoding="utf-8")


def _valid_claude_json(result: str = "Done", cost: float = 0.05, input_t: int = 1000, output_t: int = 500, cache_t: int = 200) -> str:
    # modelUsage uses camelCase keys, matching the real `claude --output-format
    # json` shape (verified against captured fixtures). It carries the same
    # totals as top-level `usage` here, so the parser can prefer either.
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
                "inputTokens": input_t,
                "outputTokens": output_t,
                "cacheReadInputTokens": cache_t,
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
    # No top-level `usage` — tokens come from modelUsage (real camelCase shape).
    data = {
        "total_cost_usd": 0.08,
        "result": "Done",
        "modelUsage": {
            "claude-sonnet-4-20250514": {"inputTokens": 600, "outputTokens": 300, "cacheReadInputTokens": 100},
            "claude-haiku-4-5-20251001": {"inputTokens": 400, "outputTokens": 200, "cacheReadInputTokens": 50},
        },
    }
    result = parse_claude_output(data)
    assert result.input_tokens == 1000
    assert result.output_tokens == 500
    assert result.cache_read_tokens == 150
    assert result.is_error is False


def test_parse_single_agent_fixture_uses_real_totals():
    """Common path: a non-delegating run reports correct tokens. Guards the fix
    from regressing single-agent trials. Real captured payload."""
    result = parse_claude_output(_load_fixture("claude_usage_single.json"))
    assert result.input_tokens == 9
    assert result.output_tokens == 79
    assert result.cache_read_tokens == 15157
    assert result.total_cost_usd == 0.0203097
    assert result.is_error is False


def test_parse_multiagent_fixture_aggregates_modelusage():
    """Delegating run: top-level `usage` reports only the orchestrator's final
    message (10 in / 93 out), but the real per-model totals — including the
    subagent — live in `modelUsage`. The parser must aggregate modelUsage:
    sonnet 40/667 + haiku 1700/4 = 1740/671. Real captured payload."""
    result = parse_claude_output(_load_fixture("claude_usage_multiagent.json"))
    assert result.input_tokens == 1740
    assert result.output_tokens == 671
    assert result.cache_read_tokens == 91819
    assert result.total_cost_usd == 0.1620787


# --- Runner protocol ---

def test_claude_code_runner_conforms_to_protocol():
    assert isinstance(ClaudeCodeRunner(_make_task()), Runner)


def test_default_max_turns_matches_settled_cap():
    """IMPLEMENTATION_PLAN §7 settled the per-trial turn cap at 60. A too-low
    default truncates cross-layer tasks (both non-haiku shakedown runs exited 1
    on the 25-turn cap). The runner default must match the settled value."""
    assert ClaudeCodeRunner(_make_task())._max_turns == 60


# --- Runner execute with mocked subprocess ---

def test_execute_success_mock(tiny_repo):
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        task = _make_task()
        trial = _make_trial()
        runner = ClaudeCodeRunner(task)
        methodology = MethodologySpec(id="off", files={})
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))

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
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))

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
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))

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


def test_execute_passes_instruction_via_stdin(tiny_repo):
    """Multi-line instructions must go through stdin, not argv.

    A newline inside a -p argument is treated as a command terminator by the
    Windows cmd.exe batch shim (claude.CMD), truncating the prompt at the first
    newline and dropping every flag after it. Delivering the prompt on stdin
    sidesteps all command-line escaping/length/newline issues.
    """
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        task = TaskSpec(
            id="t", repo_url="x", base_commit="x",
            instruction="line one ends here\nsecond line with detail",
            run_cmd="echo ok", held_out_tests_path="x", reference_diff_path="x",
        )
        trial = _make_trial()
        runner = ClaudeCodeRunner(task)
        methodology = MethodologySpec(id="off", files={})
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = _valid_claude_json()
        mock_proc.stderr = ""

        with patch("runners.claude_code.subprocess.run", return_value=mock_proc) as m:
            runner.execute(trial, wt)

        # The global subprocess.run patch also captures collect()'s git call;
        # find the claude invocation specifically.
        claude_calls = [c for c in m.call_args_list if "-p" in (c.args[0] if c.args else c.kwargs.get("args", []))]
        assert len(claude_calls) == 1
        cmd = claude_calls[0].args[0]
        kwargs = claude_calls[0].kwargs
        assert task.instruction not in cmd, "instruction must not be a CLI argument"
        assert kwargs.get("input") == task.instruction, "instruction must be passed via stdin"
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
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "not json at all"
        mock_proc.stderr = ""

        with patch("runners.claude_code.subprocess.run", return_value=mock_proc):
            result = runner.execute(trial, wt)

        assert runner.last_cost is None
    finally:
        destroy_worktree(wt)


def test_execute_parse_failure_sets_error(tiny_repo):
    """Unparseable stdout yields RunResult with error set and last_cost None."""
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        task = _make_task()
        trial = _make_trial()
        runner = ClaudeCodeRunner(task)
        methodology = MethodologySpec(id="off", files={})
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = "not json at all"
        mock_proc.stderr = ""

        with patch("runners.claude_code.subprocess.run", return_value=mock_proc):
            result = runner.execute(trial, wt)

        assert runner.last_cost is None
        assert result.error is not None
    finally:
        destroy_worktree(wt)


def test_usd_equiv_falls_back_to_self_reported_when_api_zero(tiny_repo):
    """If token-based pricing computes $0 (zero tokens) but the run self-reports a
    non-zero total_cost_usd, usd_equiv must use the self-reported value, not $0.

    Uses a priced model (claude-haiku-4-5) so compute_api_rate_usd returns 0.0
    (not None) on zero tokens — exactly the case that silently zeroed real cost.
    """
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        task = _make_task()
        trial = Trial(id="t-cc", task_id="t", methodology_id="off", repo_context_id="none", model="claude-haiku-4-5", runner="claude_code", rep=0)
        runner = ClaudeCodeRunner(task)
        methodology = MethodologySpec(id="off", files={})
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))

        mock_proc = MagicMock()
        mock_proc.returncode = 0
        mock_proc.stdout = json.dumps({
            "result": "Done",
            "is_error": False,
            "total_cost_usd": 2.03,
            "usage": {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0},
        })
        mock_proc.stderr = ""

        with patch("runners.claude_code.subprocess.run", return_value=mock_proc):
            runner.execute(trial, wt)

        assert runner.last_cost is not None
        assert runner.last_cost.usd_equiv == 2.03
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
        trial = Trial(id="t-smoke", task_id="smoke", methodology_id="off", repo_context_id="none", model="claude-sonnet-4-20250514", runner="claude_code", rep=0)
        methodology = MethodologySpec(id="off", files={})
        runner = ClaudeCodeRunner(task, max_turns=5)
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))
        result = runner.execute(trial, wt)

        assert runner.last_cost is not None
        assert runner.last_cost.input_tokens > 0
        assert runner.last_cost.output_tokens > 0
        assert result.wall_seconds > 0
    finally:
        destroy_worktree(wt)
