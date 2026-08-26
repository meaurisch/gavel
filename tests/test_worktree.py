import subprocess
from pathlib import Path

from core.worktree import create_worktree, list_kept_worktrees, prune_worktrees


def head_commit(repo: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo), check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


def _repos_dir(tmp_path: Path, tiny_repo: Path, name: str = "example") -> Path:
    repos_dir = tmp_path / "repos"
    repos_dir.mkdir()
    dest = repos_dir / name
    tiny_repo.rename(dest)
    return repos_dir


def test_list_kept_worktrees_empty_when_no_repos_dir(tmp_path):
    assert list_kept_worktrees(tmp_path / "nope") == []


def test_list_kept_worktrees_empty_when_no_worktrees(tmp_path, tiny_repo):
    repos_dir = _repos_dir(tmp_path, tiny_repo)
    assert list_kept_worktrees(repos_dir) == []


def test_list_kept_worktrees_finds_kept_worktree(tmp_path, tiny_repo):
    repos_dir = _repos_dir(tmp_path, tiny_repo)
    repo = repos_dir / "example"
    wt = create_worktree(repo, head_commit(repo))

    rows = list_kept_worktrees(repos_dir)

    assert len(rows) == 1
    assert rows[0]["repo"] == "example"
    assert rows[0]["path"] == wt
    assert rows[0]["exists"] is True


def test_list_kept_worktrees_reports_gone_directory(tmp_path, tiny_repo):
    """If the worktree dir was deleted by hand (the old manual workflow) but
    is still registered, it should show up as prunable, not vanish."""
    repos_dir = _repos_dir(tmp_path, tiny_repo)
    repo = repos_dir / "example"
    wt = create_worktree(repo, head_commit(repo))
    import shutil
    shutil.rmtree(wt)

    rows = list_kept_worktrees(repos_dir)

    assert len(rows) == 1
    assert rows[0]["exists"] is False


def test_prune_worktrees_removes_dir_and_deregisters(tmp_path, tiny_repo):
    repos_dir = _repos_dir(tmp_path, tiny_repo)
    repo = repos_dir / "example"
    wt = create_worktree(repo, head_commit(repo))
    assert wt.exists()

    cleaned = prune_worktrees(repos_dir)

    assert len(cleaned) == 1
    assert cleaned[0]["path"] == wt
    assert "error" not in cleaned[0]
    assert not wt.exists()
    assert list_kept_worktrees(repos_dir) == []


def test_prune_worktrees_clears_stale_admin_entry(tmp_path, tiny_repo):
    """A worktree already deleted by hand still needs `git worktree prune`
    to clear its administrative entry — prune must handle that path too."""
    repos_dir = _repos_dir(tmp_path, tiny_repo)
    repo = repos_dir / "example"
    wt = create_worktree(repo, head_commit(repo))
    import shutil
    shutil.rmtree(wt)

    cleaned = prune_worktrees(repos_dir)

    assert len(cleaned) == 1
    assert list_kept_worktrees(repos_dir) == []


def test_prune_worktrees_noop_when_nothing_kept(tmp_path, tiny_repo):
    repos_dir = _repos_dir(tmp_path, tiny_repo)
    assert prune_worktrees(repos_dir) == []
