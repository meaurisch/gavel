"""Repo-level defaults loader — reads repos.yaml at the project root.

repos.yaml maps a repo id (the repos/<repo> dir name) to a small dict of shared
defaults. Today the only key is `visible_test_cmd`: a repo that declares one is
opting in to having its own unit suite serve as the visible tier for every task
that targets it (see core/task_loader.resolve_visible_test_cmd).

This file lives at the project root, never inside a checkout, so it can't leak
into a worktree and become visible to the model.
"""

from pathlib import Path
import yaml

REPOS_YAML = Path(__file__).parent.parent / "repos.yaml"


def load_repos(repos_yaml: Path = REPOS_YAML) -> dict[str, dict]:
    if not repos_yaml.exists():
        return {}
    raw = yaml.safe_load(repos_yaml.read_text(encoding="utf-8"))
    return raw or {}


def get_repo_visible_test_cmd(repo_id: str, repos_yaml: Path = REPOS_YAML) -> str | None:
    """The visible_test_cmd a repo declares, or None if it declares none."""
    entry = load_repos(repos_yaml).get(repo_id)
    if not entry:
        return None
    return entry.get("visible_test_cmd")
