import subprocess
import tempfile
from pathlib import Path
from uuid import uuid4

REPOS_DIR = Path(__file__).parent.parent / "repos"


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


def _task_repos(repos_dir: Path = REPOS_DIR) -> list[Path]:
    if not repos_dir.exists():
        return []
    return sorted(p for p in repos_dir.iterdir() if p.is_dir() and (p / ".git").exists())


def _non_main_entries(repo_path: Path) -> list[dict]:
    """Parse `git worktree list --porcelain`, dropping the repo's own (main)
    worktree — only the ones `--keep-worktree` (or a killed run) can leave
    behind."""
    proc = subprocess.run(
        ["git", "worktree", "list", "--porcelain"],
        cwd=str(repo_path),
        check=True,
        capture_output=True,
        text=True,
    )
    entries: list[dict] = []
    current: dict = {}
    for line in proc.stdout.splitlines():
        if not line:
            if current:
                entries.append(current)
                current = {}
            continue
        key, _, value = line.partition(" ")
        current[key] = value
    if current:
        entries.append(current)
    return entries[1:]  # first entry is always the main worktree


def list_kept_worktrees(repos_dir: Path = REPOS_DIR) -> list[dict]:
    """Every worktree still registered under repos/<repo> other than each
    repo's own checkout — i.e. what `--keep-worktree` (or an interrupted run)
    can leave behind across the whole `repos/` tree."""
    out = []
    for repo_path in _task_repos(repos_dir):
        try:
            entries = _non_main_entries(repo_path)
        except subprocess.CalledProcessError as e:
            out.append({"repo": repo_path.name, "error": (e.stderr or str(e)).strip()})
            continue
        for entry in entries:
            wt_path = Path(entry.get("worktree", ""))
            out.append({
                "repo": repo_path.name,
                "path": wt_path,
                "exists": wt_path.exists(),
                "branch": entry.get("branch", "").removeprefix("refs/heads/") or "detached",
            })
    return out


def prune_worktrees(repos_dir: Path = REPOS_DIR) -> list[dict]:
    """Remove every kept worktree found under repos/<repo>: `git worktree
    remove --force` for ones still on disk (deletes the directory and
    deregisters it in one step), then `git worktree prune` per repo to clear
    any administrative entries left over from ones already deleted by hand."""
    cleaned = []
    for repo_path in _task_repos(repos_dir):
        try:
            entries = _non_main_entries(repo_path)
        except subprocess.CalledProcessError as e:
            cleaned.append({"repo": repo_path.name, "error": (e.stderr or str(e)).strip()})
            continue
        for entry in entries:
            wt_path = Path(entry.get("worktree", ""))
            item = {"repo": repo_path.name, "path": wt_path}
            if wt_path.exists():
                try:
                    subprocess.run(
                        ["git", "worktree", "remove", "--force", str(wt_path)],
                        cwd=str(repo_path),
                        check=True,
                        capture_output=True,
                        text=True,
                    )
                except subprocess.CalledProcessError as e:
                    item["error"] = (e.stderr or str(e)).strip()
            cleaned.append(item)
        if entries:
            subprocess.run(
                ["git", "worktree", "prune"],
                cwd=str(repo_path),
                check=True,
                capture_output=True,
                text=True,
            )
    return cleaned
