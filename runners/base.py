from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol, runtime_checkable

from core.models import RunResult, SetupSpec, Trial


@runtime_checkable
class Runner(Protocol):
    def prepare(self, trial: Trial, worktree_path: Path, setup: SetupSpec) -> None: ...
    def execute(self, trial: Trial, worktree_path: Path) -> RunResult: ...


def collect(worktree_path: Path) -> str:
    subprocess.run(
        ["git", "add", "-A"],
        cwd=str(worktree_path),
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["git", "diff", "HEAD"],
        cwd=str(worktree_path),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def lay_down_setup_files(worktree_path: Path, setup: SetupSpec) -> None:
    for file_path, lines in setup.files.items():
        target = worktree_path / file_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n")
    subprocess.run(
        ["git", "add", "-A"],
        cwd=str(worktree_path),
        check=True,
        capture_output=True,
    )
    subprocess.run(
        ["git", "commit", "-m", "setup-bench: lay down setup files", "--allow-empty"],
        cwd=str(worktree_path),
        check=True,
        capture_output=True,
        text=True,
    )
