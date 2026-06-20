"""Held-out-test gate: copies tests into a worktree, runs them, cleans up."""

import shutil
import subprocess
from pathlib import Path

from core.models import GateResult, TaskSpec, Trial


def _iter_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file():
            yield p, p.relative_to(root)


def apply(trial: Trial, worktree_path: Path, task: TaskSpec) -> GateResult:
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

        result = subprocess.run(
            task.run_cmd,
            cwd=str(worktree_path),
            shell=True,
            capture_output=True,
            text=True,
        )
        passed = result.returncode == 0
        output = result.stdout + result.stderr
    finally:
        for f in created:
            f.unlink(missing_ok=True)

    return GateResult(trial_id=trial.id, passed=passed, test_output=output)
