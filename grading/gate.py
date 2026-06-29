"""Held-out-test gate: copies tests into a worktree, runs them, cleans up."""

import shutil
import subprocess
from pathlib import Path

from core.models import GateResult, TaskSpec, Trial
from core.toolchain import needs_wsl, wsl_argv


def _iter_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file():
            yield p, p.relative_to(root)


def _run_command(cmd: str, cwd: Path, task: TaskSpec) -> tuple[bool, str]:
    if needs_wsl(task):
        result = subprocess.run(
            wsl_argv(cmd, cwd),
            capture_output=True,
            text=True,
            timeout=900,
        )
    else:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            shell=True,
            capture_output=True,
            text=True,
        )
    return (result.returncode == 0, result.stdout + result.stderr)


def _run_hidden_tests(trial: Trial, worktree_path: Path, task: TaskSpec) -> tuple[bool, str]:
    src = Path(task.held_out_tests_path).resolve()
    dest_root = worktree_path / "tests"

    files = list(_iter_files(src))

    for _, rel in files:
        dest = dest_root / rel
        assert not dest.exists(), f"held-out test already present in worktree: {dest}"

    created: list[Path] = []
    try:
        for abs_src, rel in files:
            dest = dest_root / rel
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(abs_src, dest)
            created.append(dest)

        passed, output = _run_command(task.run_cmd, worktree_path, task)
    finally:
        for f in created:
            f.unlink(missing_ok=True)

    return (passed, output)


def apply(trial: Trial, worktree_path: Path, task: TaskSpec) -> GateResult:
    result = GateResult(trial_id=trial.id, passed=False)

    if task.build_cmd:
        ok, out = _run_command(task.build_cmd, worktree_path, task)
        result.compile_passed, result.compile_output = ok, out
        if not ok:
            return result

    if task.visible_test_cmd:
        ok, out = _run_command(task.visible_test_cmd, worktree_path, task)
        result.visible_passed, result.visible_output = ok, out

    hidden_ok, hidden_out = _run_hidden_tests(trial, worktree_path, task)
    result.hidden_passed, result.hidden_output = hidden_ok, hidden_out
    result.passed = hidden_ok

    return result
