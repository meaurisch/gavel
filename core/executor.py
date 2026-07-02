"""Trial executor — runs the per-trial pipeline."""

import logging
import sqlite3
import time
from pathlib import Path

from core.db import persist_trial_result, trial_exists
from core.matrix import HARNESS_MAP
from core.models import CostRecord, GateResult, Trial
from core.methodology_loader import load_methodology
from core.repo_context_loader import load_repo_context
from core.task_loader import load_task, resolve_repo_path
from core.worktree import create_worktree, destroy_worktree
from grading.gate import apply as gate_apply
from runners.claude_code import ClaudeCodeRunner
from runners.manual import ManualRunner
from runners.nop import NopRunner
from runners.oracle import OracleRunner

logger = logging.getLogger(__name__)


def make_runner(runner_name: str, task):
    match runner_name:
        case "claude-code":
            return ClaudeCodeRunner(task)
        case "oracle":
            return OracleRunner(task)
        case "nop":
            return NopRunner()
        case "manual":
            return ManualRunner(task)
        case _:
            raise ValueError(f"Unknown runner: {runner_name}")


def execute_trial(trial: Trial, conn: sqlite3.Connection, keep_worktree: bool = False) -> dict:
    trial_start = time.monotonic()
    summary = {
        "passed": None,
        "usd": 0.0,
        "tokens": 0,
        "wall_seconds": 0.0,
        "error": None,
        "worktree": None,
    }

    task = load_task(trial.task_id)
    harness = HARNESS_MAP.get(trial.runner, "claude-code")
    methodology = load_methodology(trial.methodology_id, harness)
    repo_context = load_repo_context(trial.repo_context_id, harness)
    repo_path = resolve_repo_path(task)

    wt_path = None
    try:
        wt_path = create_worktree(repo_path, task.base_commit)
        summary["worktree"] = str(wt_path)

        runner = make_runner(trial.runner, task)
        runner.prepare(trial, wt_path, methodology, repo_context)
        run_result = runner.execute(trial, wt_path)
        if run_result.error:
            summary["error"] = run_result.error

        cost: CostRecord | None = None
        if isinstance(runner, ClaudeCodeRunner) and runner.last_cost is not None:
            cost = runner.last_cost
            summary["usd"] = cost.usd_equiv
            summary["tokens"] = cost.input_tokens + cost.output_tokens

        # The gate can raise (e.g. the agent wrote a file at the held-out test
        # path, tripping the leakage assertion). A gate crash must never discard
        # the trial and its already-billed cost — record it as a FAIL instead.
        try:
            gate_result = gate_apply(trial, wt_path, task)
        except Exception as e:
            logger.error("Trial %s: gate crashed, recording as FAIL: %s", trial.id, e, exc_info=True)
            gate_result = GateResult(trial_id=trial.id, passed=False, hidden_output=f"gate error: {e}")
            summary["error"] = summary["error"] or f"gate error: {e}"
        summary["passed"] = gate_result.passed

        persist_trial_result(conn, trial, run_result, cost, gate_result)

    except Exception as e:
        summary["error"] = str(e)
        logger.error("Trial %s failed: %s", trial.id, e, exc_info=True)
    finally:
        summary["wall_seconds"] = time.monotonic() - trial_start
        if keep_worktree:
            if wt_path is not None:
                logger.info("Keeping worktree for %s at %s", trial.id, wt_path)
        elif wt_path is not None and wt_path.exists():
            try:
                destroy_worktree(wt_path)
            except Exception as e:
                logger.warning("Failed to destroy worktree %s: %s", wt_path, e)

    return summary


def execute_all(
    trials: list[Trial],
    conn: sqlite3.Connection,
    delay: float = 0.0,
    on_progress=None,
    keep_worktree: bool = False,
) -> list[dict]:
    results = []
    for i, trial in enumerate(trials):
        if trial_exists(conn, trial.id):
            logger.info("Skipping %s (already exists)", trial.id)
            summary = {"skipped": True}
            results.append(summary)
            if on_progress:
                on_progress(i, trial, summary)
            continue

        logger.info("Running trial %d/%d: %s", i + 1, len(trials), trial.id)
        summary = execute_trial(trial, conn, keep_worktree=keep_worktree)
        results.append(summary)

        if on_progress:
            on_progress(i, trial, summary)

        if delay > 0 and i < len(trials) - 1:
            time.sleep(delay)

    return results
