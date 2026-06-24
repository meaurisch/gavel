from __future__ import annotations

import subprocess
from pathlib import Path
from typing import Protocol, runtime_checkable

from core.models import MethodologySpec, RunResult, Trial


@runtime_checkable
class Runner(Protocol):
    def prepare(self, trial: Trial, worktree_path: Path, methodology: MethodologySpec) -> None: ...
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


def lay_down_files(worktree_path: Path, files: dict[str, list[str]], commit_message: str) -> None:
    for file_path, lines in files.items():
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
        ["git", "commit", "-m", commit_message, "--allow-empty"],
        cwd=str(worktree_path),
        check=True,
        capture_output=True,
        text=True,
    )
