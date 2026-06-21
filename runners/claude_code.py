from __future__ import annotations

import logging
import subprocess
import time
from pathlib import Path

from core.models import CostRecord, RunResult, SetupSpec, TaskSpec, Trial
from cost.claude_usage import ClaudeUsageParseError, parse_claude_output
from runners.base import collect, lay_down_setup_files

logger = logging.getLogger(__name__)

_DEFAULT_MAX_TURNS = 25


class ClaudeCodeRunner:
    def __init__(self, task: TaskSpec, *, max_turns: int = _DEFAULT_MAX_TURNS) -> None:
        self._task = task
        self._max_turns = max_turns
        self.last_cost: CostRecord | None = None

    def prepare(self, trial: Trial, worktree_path: Path, setup: SetupSpec) -> None:
        lay_down_setup_files(worktree_path, setup)

    def execute(self, trial: Trial, worktree_path: Path) -> RunResult:
        self.last_cost = None
        start = time.monotonic()

        cmd = [
            "claude",
            "-p", self._task.instruction,
            "--output-format", "json",
            "--model", trial.model,
            "--dangerously-skip-permissions",
            "--max-turns", str(self._max_turns),
        ]

        try:
            proc = subprocess.run(
                cmd,
                cwd=str(worktree_path),
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
            diff = collect(worktree_path)
            return RunResult(trial_id=trial.id, diff=diff, exit_status=1, wall_seconds=wall_seconds)

        wall_seconds = time.monotonic() - start

        usage = None
        try:
            usage = parse_claude_output(stdout)
        except ClaudeUsageParseError as e:
            logger.error("Trial %s: failed to parse Claude output: %s", trial.id, e)

        if usage is not None:
            self.last_cost = CostRecord(
                trial_id=trial.id,
                native_unit="usd_imputed",
                native_amount=usage.total_cost_usd,
                usd_equiv=usage.total_cost_usd,
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

        diff = collect(worktree_path)
        return RunResult(trial_id=trial.id, diff=diff, exit_status=exit_status, wall_seconds=wall_seconds)
