import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4


def _scrub_unreachable_refs(repo_path: Path, base_commit: str) -> None:
    """Delete every ref that isn't an ancestor of base_commit.

    Worktrees share their parent clone's ref store, so `git log --all` /
    `git for-each-ref` inside a trial worktree would otherwise reach
    reference-solution branches (e.g. `refs/remotes/origin/gavel/*-reference`)
    and other anchors living in the same clone, handing the agent the answer.
    Deleting refs here doesn't touch the objects: anything a remote still
    knows about can be re-fetched (`git fetch origin`) when actually needed.
    """
    result = subprocess.run(
        ["git", "for-each-ref", "--no-merged", base_commit, "--format=%(refname)"],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
        text=True,
    )
    for ref in result.stdout.splitlines():
        ref = ref.strip()
        if not ref:
            continue
        subprocess.run(
            ["git", "update-ref", "-d", ref],
            cwd=str(repo_path),
            check=True,
            capture_output=True,
            text=True,
        )


def create_worktree(repo_path: Path, base_commit: str) -> Path:
    _scrub_unreachable_refs(repo_path, base_commit)
    wt_path = Path(tempfile.gettempdir()) / f"sb-wt-{uuid4().hex[:12]}"
    subprocess.run(
        ["git", "worktree", "add", str(wt_path), base_commit],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "clean", "-fdx"],
        cwd=str(wt_path),
        check=True,
        capture_output=True,
        text=True,
    )
    return wt_path


def _find_main_repo(worktree_path: Path) -> Path:
    git_file = worktree_path / ".git"
    text = git_file.read_text().strip()
    gitdir = Path(text.removeprefix("gitdir:").strip())
    # gitdir points to <main_repo>/.git/worktrees/<name>
    return gitdir.parent.parent.parent


def destroy_worktree(worktree_path: Path) -> None:
    main_repo = _find_main_repo(worktree_path)
    subprocess.run(
        ["git", "worktree", "remove", "--force", str(worktree_path)],
        cwd=str(main_repo),
        check=True,
        capture_output=True,
        text=True,
    )
    subprocess.run(
        ["git", "worktree", "prune"],
        cwd=str(main_repo),
        check=True,
        capture_output=True,
        text=True,
    )
