from __future__ import annotations

import shutil
import subprocess
from pathlib import Path
from typing import Protocol, runtime_checkable

from core.models import MethodologySpec, RepoContextSpec, RunResult, Trial
from grading.gate import _iter_files


@runtime_checkable
class Runner(Protocol):
    def prepare(
        self,
        trial: Trial,
        worktree_path: Path,
        methodology: MethodologySpec,
        repo_context: RepoContextSpec,
    ) -> None: ...
    def execute(self, trial: Trial, worktree_path: Path) -> RunResult: ...


def collect(worktree_path: Path, baseline_ref: str = "HEAD") -> str:
    """Capture the agent's changes as a diff against `baseline_ref`.

    `baseline_ref` should be the worktree HEAD captured *before* the agent ran
    (the post-prepare setup commit). Diffing against a fixed baseline — not the
    live `HEAD` — is essential: an agent that COMMITS its work advances HEAD, so
    `git diff HEAD` would return empty and silently discard the whole diff (this
    erased the sonnet trial on the cosmos-A shakedown). Runners that never commit
    (nop/oracle/manual) can rely on the "HEAD" default.
    """
    subprocess.run(
        ["git", "add", "-A"],
        cwd=str(worktree_path),
        check=True,
        capture_output=True,
    )
    result = subprocess.run(
        ["git", "diff", baseline_ref],
        cwd=str(worktree_path),
        check=True,
        capture_output=True,
        text=True,
    )
    return result.stdout


def lay_down_dir(worktree_path: Path, src_dir: Path, commit_message: str) -> None:
    """Copy a directory tree into the worktree (paths mirror repo layout) and
    commit it as its own setup commit. Used for a task's EXTRA visible tests:
    committing them makes them visible to the model while keeping them out of
    the model's own diff. Reuses the gate's _iter_files walk.
    """
    src_dir = Path(src_dir).resolve()
    for abs_src, rel in _iter_files(src_dir):
        dest = worktree_path / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(abs_src, dest)
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


def lay_down_files(worktree_path: Path, files: dict[str, list[str]], commit_message: str) -> None:
    for file_path, lines in files.items():
        target = worktree_path / file_path
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text("\n".join(lines) + "\n", encoding="utf-8")
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
