import subprocess
from pathlib import Path

from core.worktree import create_worktree, destroy_worktree
from tests.conftest import head_commit


def _write_commit(repo: Path, filename: str, content: str, message: str) -> str:
    (repo / filename).write_text(content)
    subprocess.run(["git", "add", filename], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", message], cwd=str(repo), check=True, capture_output=True)
    return head_commit(repo)


def test_reference_branch_not_reachable_from_worktree(tiny_repo: Path):
    base_commit = head_commit(tiny_repo)

    # Simulate a reference-solution branch living in the task repo clone,
    # e.g. the anchor commit carrying the gold patch for a task.
    reference_commit = _write_commit(tiny_repo, "secret.txt", "gold answer\n", "gold fix")
    subprocess.run(
        ["git", "update-ref", "refs/remotes/origin/gavel/x-reference", reference_commit],
        cwd=str(tiny_repo), check=True, capture_output=True,
    )
    # Move the repo's checked-out branch back so base_commit stays the trial's base.
    subprocess.run(["git", "reset", "--hard", base_commit], cwd=str(tiny_repo), check=True, capture_output=True)

    wt = create_worktree(tiny_repo, base_commit)
    try:
        refs = subprocess.run(
            ["git", "for-each-ref", "--format=%(refname)"],
            cwd=str(wt), check=True, capture_output=True, text=True,
        ).stdout
        assert "gavel/x-reference" not in refs
        assert "-reference" not in refs

        log_all = subprocess.run(
            ["git", "log", "--all", "--format=%H"],
            cwd=str(wt), check=True, capture_output=True, text=True,
        ).stdout
        assert reference_commit not in log_all.split()
    finally:
        destroy_worktree(wt)


def test_ancestor_refs_survive_scrub(tiny_repo: Path):
    base_commit = head_commit(tiny_repo)
    subprocess.run(
        ["git", "branch", "task-base-marker", base_commit],
        cwd=str(tiny_repo), check=True, capture_output=True,
    )

    wt = create_worktree(tiny_repo, base_commit)
    try:
        refs = subprocess.run(
            ["git", "for-each-ref", "--format=%(refname)"],
            cwd=str(wt), check=True, capture_output=True, text=True,
        ).stdout
        assert "refs/heads/task-base-marker" in refs
    finally:
        destroy_worktree(wt)
