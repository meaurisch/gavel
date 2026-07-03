"""Reconstruct pre-agent ("original") file content for the three-way diff view.

A trial's starting point is fully determined by its task's base_commit plus the
repo-context and methodology manifests laid down on top (worktrees are torn
down after a trial, so nothing is persisted — but nothing needs to be). The
comparison axis is never the task (see grading.pairwise.AXIS_FIELDS), so both
sides of a pair share the same base commit; only laid-down instruction files
could differ, and those are stripped from served diffs anyway.

Resolution precedence mirrors the runner's prepare() order, last write wins:
methodology files > repo-context files > task visible tests > base commit.
Content is returned RAW here — callers must redact axis ids (via
grading.pairwise.redact_axis_ids) before serving anything during comparison.
"""

from __future__ import annotations

import subprocess
from functools import lru_cache
from pathlib import Path

from core.matrix import HARNESS_MAP
from core.methodology_loader import load_methodology
from core.repo_context_loader import load_repo_context
from core.task_loader import load_task, resolve_repo_path

ROOT = Path(__file__).resolve().parent.parent


def diff_file_entries(diff: str) -> list[tuple[str | None, str | None]]:
    """(old_path, new_path) for every file in a unified git diff.

    None on a side means /dev/null (file created / deleted). Entries without
    ---/+++ lines (mode-only changes, binary stubs) are skipped — there is no
    content to show for them.
    """
    entries: list[tuple[str | None, str | None]] = []
    old: str | None = None
    new: str | None = None
    seen_content = False

    def flush() -> None:
        nonlocal old, new, seen_content
        if seen_content:
            entries.append((old, new))
        old = new = None
        seen_content = False

    for line in diff.splitlines():
        if line.startswith("diff --git "):
            flush()
        elif line.startswith("--- "):
            p = line[4:].split("\t")[0]
            old = None if p == "/dev/null" else (p[2:] if p.startswith("a/") else p)
            seen_content = True
        elif line.startswith("+++ "):
            p = line[4:].split("\t")[0]
            new = None if p == "/dev/null" else (p[2:] if p.startswith("b/") else p)
            seen_content = True
    flush()
    return entries


class OriginalResolver:
    """Resolves pre-agent content of worktree paths for one trial's setup
    (task, repo-context, methodology, runner-harness)."""

    def __init__(self, task_id: str, methodology_id: str, repo_context_id: str, runner: str):
        self.available = True
        self.reason: str | None = None
        self._cache: dict[str, str | None] = {}
        self._laid_down: dict[str, str] = {}
        self._visible_tests_dir: Path | None = None
        self._repo_path: Path | None = None
        self._base_commit: str | None = None

        try:
            task = load_task(task_id)
        except Exception as e:
            self.available = False
            self.reason = f"task spec for {task_id!r} not available locally ({e.__class__.__name__})"
            return

        self._base_commit = task.base_commit
        repo_path = resolve_repo_path(task)
        if (repo_path / ".git").exists():
            self._repo_path = repo_path
        else:
            self.available = False
            self.reason = f"task repo not cloned locally (expected at {repo_path}) — run `python cli.py setup`"
            return

        if task.visible_tests_path:
            vt = (ROOT / task.visible_tests_path).resolve()
            if vt.is_dir():
                self._visible_tests_dir = vt

        harness = HARNESS_MAP.get(runner, "claude-code")
        # Lay-down order: visible tests, then repo-context, then methodology —
        # later writes win, so apply in the same order.
        for kind, loader, spec_id in (
            ("repo_context", load_repo_context, repo_context_id),
            ("methodology", load_methodology, methodology_id),
        ):
            try:
                spec = loader(spec_id, harness)
            except Exception:
                continue  # unknown/demo id lays down nothing we can know about
            for dest, lines in spec.files.items():
                self._laid_down[dest] = "\n".join(lines) + "\n"

    def content(self, path: str) -> str | None:
        """Pre-agent content of `path` (worktree-relative, forward slashes);
        None when the file did not exist before the agent ran."""
        if not self.available:
            return None
        if path in self._cache:
            return self._cache[path]

        result: str | None = None
        if path in self._laid_down:
            result = self._laid_down[path]
        elif self._visible_tests_dir is not None:
            candidate = (self._visible_tests_dir / path).resolve()
            if candidate.is_file() and candidate.is_relative_to(self._visible_tests_dir):
                result = candidate.read_text(encoding="utf-8", errors="replace")
        if result is None:
            result = self._git_show(path)

        self._cache[path] = result
        return result

    def _git_show(self, path: str) -> str | None:
        proc = subprocess.run(
            ["git", "show", f"{self._base_commit}:{path}"],
            cwd=str(self._repo_path),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
        )
        return proc.stdout if proc.returncode == 0 else None


@lru_cache(maxsize=64)
def get_resolver(task_id: str, methodology_id: str, repo_context_id: str, runner: str) -> OriginalResolver:
    return OriginalResolver(task_id, methodology_id, repo_context_id, runner)
