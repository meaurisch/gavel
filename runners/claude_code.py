from __future__ import annotations

import logging
import shutil
import subprocess
import time
from pathlib import Path

from core.models import CostRecord, MethodologySpec, RepoContextSpec, RunResult, TaskSpec, Trial
from cost.claude_usage import ClaudeUsageParseError, parse_claude_output
from cost.pricing import compute_api_rate_usd
from runners.base import collect, lay_down_dir, lay_down_files

logger = logging.getLogger(__name__)

_DEFAULT_MAX_TURNS = 25


class ClaudeCodeRunner:
    def __init__(self, task: TaskSpec, *, max_turns: int = _DEFAULT_MAX_TURNS) -> None:
        self._task = task
        self._max_turns = max_turns
        self.last_cost: CostRecord | None = None

    def prepare(
        self,
        trial: Trial,
        worktree_path: Path,
        methodology: MethodologySpec,
        repo_context: RepoContextSpec,
    ) -> None:
        # Task-supplied extra visible tests go down first, in their own commit,
        # before the repo-context and methodology commits — so they're visible to
        # the model but stay out of its diff. (No-op unless the task sets it.)
        if self._task.visible_tests_path:
            lay_down_dir(
                worktree_path,
                Path(self._task.visible_tests_path),
                "setup-bench: lay down task visible tests",
            )
        lay_down_files(worktree_path, repo_context.files, "setup-bench: lay down repo context files")
        lay_down_files(worktree_path, methodology.files, "setup-bench: lay down methodology files")

    def execute(self, trial: Trial, worktree_path: Path) -> RunResult:
        self.last_cost = None
        start = time.monotonic()

        # Baseline for the diff: the worktree HEAD as it stands after prepare()
        # and before the agent touches anything. The agent may commit its own
        # work, which advances HEAD — so we must diff against this fixed ref, not
        # the live HEAD, or a committing agent's entire diff vanishes.
        baseline = subprocess.run(
            ["git", "rev-parse", "HEAD"],
            cwd=str(worktree_path),
            check=True,
            capture_output=True,
            text=True,
        ).stdout.strip()

        claude_bin = shutil.which("claude")
        if claude_bin is None:
            raise FileNotFoundError("claude CLI not found on PATH")

        # The instruction is delivered on stdin, not as a -p argument. On Windows
        # `claude` resolves to claude.CMD, a batch shim run through cmd.exe; a
        # newline inside an argument is treated as a command terminator, so a
        # multi-line -p prompt is truncated at the first newline and every flag
        # after it is dropped. stdin sidesteps all argv escaping/length issues.
        cmd = [
            claude_bin,
            "-p",
            "--output-format", "json",
            "--model", trial.model,
            "--dangerously-skip-permissions",
            "--max-turns", str(self._max_turns),
        ]

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(worktree_path),
                input=self._task.instruction,
                capture_output=True,
                text=True,
                timeout=self._max_turns * 120,
            )
            exit_status = proc.returncode
            stdout = proc.stdout
            stderr = proc.stderr
        except subprocess.TimeoutExpired:
            logger.error("Trial %s: claude timed out after %d seconds", trial.id, self._max_turns * 120)
            wall_seconds = time.monotonic() - start
            diff = collect(worktree_path, baseline)
            return RunResult(trial_id=trial.id, diff=diff, exit_status=1, wall_seconds=wall_seconds)

        wall_seconds = time.monotonic() - start

        usage = None
        parse_error: str | None = None
        try:
            usage = parse_claude_output(stdout)
        except ClaudeUsageParseError as e:
            parse_error = str(e)
            logger.error("Trial %s: failed to parse Claude output: %s", trial.id, e)

        if usage is not None:
            api_usd = compute_api_rate_usd(
                trial.model,
                usage.input_tokens,
                usage.output_tokens,
                usage.cache_read_tokens,
            )
            # api_usd can be 0.0 (priced model, but 0 tokens parsed) — that must
            # NOT clobber a real self-reported cost. Use the token-based rate only
            # when it actually computed something; otherwise fall back to the
            # self-reported total.
            if api_usd:
                usd_equiv = api_usd
            else:
                usd_equiv = usage.total_cost_usd
            self.last_cost = CostRecord(
                trial_id=trial.id,
                native_unit="usd_self_reported",
                native_amount=usage.total_cost_usd,
                usd_equiv=usd_equiv,
                input_tokens=usage.input_tokens,
                output_tokens=usage.output_tokens,
                cache_read_tokens=usage.cache_read_tokens,
            )

        if exit_status != 0:
            logger.warning("Trial %s: claude exited with code %d. stderr: %s", trial.id, exit_status, stderr[:500])
        elif usage is not None and usage.is_error:
            logger.warning(
                "Trial %s: Claude reported error/empty result despite exit 0. "
                "Tokens billed: in=%d out=%d cache=%d. Error: %s",
                trial.id, usage.input_tokens, usage.output_tokens, usage.cache_read_tokens, usage.error_message,
            )
            exit_status = 1

        diff = collect(worktree_path, baseline)
        return RunResult(trial_id=trial.id, diff=diff, exit_status=exit_status, wall_seconds=wall_seconds, error=parse_error)
