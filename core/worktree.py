import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4


def create_worktree(repo_path: Path, base_commit: str) -> Path:
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
