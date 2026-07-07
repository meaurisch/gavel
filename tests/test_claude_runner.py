from __future__ import annotations

import json
import shutil
import subprocess
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


def test_parse_captures_cache_creation_tokens():
    """Real CLI shape (captured 2026-07-07): a one-shot `claude -p` call puts
    nearly the whole prompt into cache_creation_input_tokens — input_tokens
    alone says 9 for a ~24k-token call. The parser must expose it."""
    data = {
        "total_cost_usd": 0.0189295,
        "result": "OK",
        "usage": {
            "input_tokens": 9, "output_tokens": 64,
            "cache_read_input_tokens": 15305,
            "cache_creation_input_tokens": 8535,
        },
        "modelUsage": {
            "claude-haiku-4-5": {
                "inputTokens": 9, "outputTokens": 64,
                "cacheReadInputTokens": 15305,
                "cacheCreationInputTokens": 8535,
                "costUSD": 0.0189295,
            }
        },
    }
    result = parse_claude_output(data)
    assert result.cache_creation_tokens == 8535
    assert result.input_tokens == 9
    assert result.cache_read_tokens == 15305


def test_parse_cache_creation_from_model_usage_fallback():
    data = {
        "total_cost_usd": 0.02,
        "result": "Done",
        "modelUsage": {
            "claude-haiku-4-5": {"inputTokens": 5, "outputTokens": 10,
                                 "cacheReadInputTokens": 0,
                                 "cacheCreationInputTokens": 7000},
        },
    }
    result = parse_claude_output(data)
    assert result.cache_creation_tokens == 7000


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


def test_execute_claude_call_uses_utf8_encoding(tiny_repo):
    """The `claude` subprocess call must decode stdout/stderr as UTF-8 (errors
    ignored), not the platform default codec (cp1252 on Windows). Claude's
    `--output-format json` output can contain bytes outside cp1252's range;
    without an explicit encoding, Python's reader thread swallows the decode
    error and communicate() silently returns None, crashing later `.strip()`
    calls (AttributeError: 'NoneType' object has no attribute 'strip')."""
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

        with patch("runners.claude_code.subprocess.run", return_value=mock_proc) as m:
            runner.execute(trial, wt)

        claude_calls = [c for c in m.call_args_list if "-p" in (c.args[0] if c.args else c.kwargs.get("args", []))]
        assert len(claude_calls) == 1
        kwargs = claude_calls[0].kwargs
        assert kwargs.get("encoding") == "utf-8"
        assert kwargs.get("errors") == "ignore"
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


def test_execute_empty_diff_sets_error(tiny_repo):
    """A parseable, billed run that leaves NO changes in the worktree is a real
    signal (since 5fb9787 an empty diff is no longer a false negative). It must
    surface as an explicit error so an all-no-op trial is distinguishable in the DB.
    """
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        task = _make_task()
        trial = _make_trial()
        runner = ClaudeCodeRunner(task)
        methodology = MethodologySpec(id="off", files={})
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))

        def fake_run(cmd, *a, **k):
            m = MagicMock()
            m.returncode = 0
            m.stderr = ""
            if cmd[:2] == ["git", "diff"]:
                m.stdout = ""          # agent produced no changes
            elif cmd[:2] == ["git", "rev-parse"]:
                m.stdout = "BASELINE"
            else:
                m.stdout = _valid_claude_json()  # the claude call
            return m

        with patch("runners.claude_code.subprocess.run", side_effect=fake_run):
            result = runner.execute(trial, wt)

        assert result.diff == ""
        assert result.error is not None
        assert "empty diff" in result.error.lower()
        # a clean, billed run still records its cost
        assert runner.last_cost is not None
    finally:
        destroy_worktree(wt)


def test_execute_timeout_sets_error(tiny_repo):
    """A timed-out trial must never look like a clean $0 run: the RunResult
    carries an explicit error so the DB row is flagged."""
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        task = _make_task()
        trial = _make_trial()
        runner = ClaudeCodeRunner(task)
        methodology = MethodologySpec(id="off", files={})
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))

        def fake_run(cmd, *a, **k):
            if cmd[0] not in ("git",):
                raise subprocess.TimeoutExpired(cmd, 7200)
            m = MagicMock()
            m.returncode = 0
            m.stderr = ""
            m.stdout = "BASELINE" if cmd[:2] == ["git", "rev-parse"] else "some diff"
            return m

        with patch("runners.claude_code.subprocess.run", side_effect=fake_run):
            result = runner.execute(trial, wt)

        assert result.exit_status == 1
        assert result.error is not None
        assert "timed out" in result.error
    finally:
        destroy_worktree(wt)


def test_execute_timeout_salvages_cost_from_partial_stdout(tiny_repo):
    """If the killed process left parseable usage JSON on stdout, the billed
    cost is still recorded rather than silently dropped."""
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        task = _make_task()
        trial = _make_trial()
        runner = ClaudeCodeRunner(task)
        methodology = MethodologySpec(id="off", files={})
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))

        def fake_run(cmd, *a, **k):
            if cmd[0] not in ("git",):
                raise subprocess.TimeoutExpired(cmd, 7200, output=_valid_claude_json())
            m = MagicMock()
            m.returncode = 0
            m.stderr = ""
            m.stdout = "BASELINE" if cmd[:2] == ["git", "rev-parse"] else "some diff"
            return m

        with patch("runners.claude_code.subprocess.run", side_effect=fake_run):
            result = runner.execute(trial, wt)

        assert result.error is not None and "timed out" in result.error
        assert runner.last_cost is not None
        assert runner.last_cost.input_tokens == 1000
    finally:
        destroy_worktree(wt)


def test_execute_no_parseable_output_raises(tiny_repo):
    """A `claude` invocation that exits nonzero with no parseable output (e.g.
    rate-limited, killed before producing any JSON) never actually completed an
    attempt. It must raise so core.executor's existing except-block skips
    insert_trial(), leaving trial_exists() False and the trial naturally
    retryable on the next `cli.py run` — NOT silently persisted as a fake
    "empty diff" trial that permanently burns the trial ID.
    """
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
        mock_proc.stdout = ""
        mock_proc.stderr = ""

        with patch("runners.claude_code.subprocess.run", return_value=mock_proc):
            with pytest.raises(Exception):
                runner.execute(trial, wt)
    finally:
        destroy_worktree(wt)


def test_execute_zero_token_failure_raises(tiny_repo):
    """A `claude` invocation that exits nonzero but DOES produce valid JSON —
    e.g. an immediate rejection formatted as a well-formed error envelope with
    zero billed tokens — is the same "never actually did an attempt" case as
    unparseable stdout, just a different JSON shape. It must also raise so the
    trial ID isn't permanently burned as a fake completed trial.
    """
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
        mock_proc.stdout = json.dumps({
            "result": "",
            "is_error": True,
            "total_cost_usd": 0,
            "usage": {"input_tokens": 0, "output_tokens": 0, "cache_read_input_tokens": 0},
        })
        mock_proc.stderr = ""

        with patch("runners.claude_code.subprocess.run", return_value=mock_proc):
            with pytest.raises(Exception):
                runner.execute(trial, wt)
    finally:
        destroy_worktree(wt)


def test_execute_nonempty_diff_no_empty_error(tiny_repo):
    """Guard: a run that DID produce changes must not get the empty-diff error."""
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        task = _make_task()
        trial = _make_trial()
        runner = ClaudeCodeRunner(task)
        methodology = MethodologySpec(id="off", files={})
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))

        def fake_run(cmd, *a, **k):
            m = MagicMock()
            m.returncode = 0
            m.stderr = ""
            if cmd[:2] == ["git", "diff"]:
                m.stdout = "--- a/x\n+++ b/x\n"
            elif cmd[:2] == ["git", "rev-parse"]:
                m.stdout = "BASELINE"
            else:
                m.stdout = _valid_claude_json()
            return m

        with patch("runners.claude_code.subprocess.run", side_effect=fake_run):
            result = runner.execute(trial, wt)

        assert result.error is None
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


def test_execute_timeout_with_no_output_raises_retryable(tiny_repo):
    """A hang until timeout with no diff and no salvageable cost is a
    transient failure: raise (trial stays retryable) instead of burning the
    trial id with an empty persisted result."""
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        task = _make_task()
        trial = _make_trial()
        runner = ClaudeCodeRunner(task)
        methodology = MethodologySpec(id="off", files={})
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))

        def fake_run(cmd, *a, **k):
            if cmd[0] not in ("git",):
                raise subprocess.TimeoutExpired(cmd, 7200)
            m = MagicMock()
            m.returncode = 0
            m.stderr = ""
            m.stdout = "BASELINE" if cmd[:2] == ["git", "rev-parse"] else ""
            return m

        with patch("runners.claude_code.subprocess.run", side_effect=fake_run):
            with pytest.raises(RuntimeError, match="retryable"):
                runner.execute(trial, wt)
    finally:
        destroy_worktree(wt)


def test_execute_timeout_salvage_survives_garbage_stdout(tiny_repo):
    """Partial stdout can be valid JSON but not an object; the salvage must
    swallow ANY parse surprise, keep the diff, and persist the trial."""
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        task = _make_task()
        trial = _make_trial()
        runner = ClaudeCodeRunner(task)
        methodology = MethodologySpec(id="off", files={})
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))

        def fake_run(cmd, *a, **k):
            if cmd[0] not in ("git",):
                raise subprocess.TimeoutExpired(cmd, 7200, output="42")  # bare number
            m = MagicMock()
            m.returncode = 0
            m.stderr = ""
            m.stdout = "BASELINE" if cmd[:2] == ["git", "rev-parse"] else "some diff"
            return m

        with patch("runners.claude_code.subprocess.run", side_effect=fake_run):
            result = runner.execute(trial, wt)

        assert result.error is not None and "timed out" in result.error
        assert result.diff == "some diff"
    finally:
        destroy_worktree(wt)
