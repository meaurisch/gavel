"""Task loader — reads tasks/{task_id}/task.yaml into TaskSpec."""

from pathlib import Path
import yaml
from core.models import TaskSpec
from core.repo_loader import REPOS_YAML, get_repo_visible_test_cmd

TASKS_DIR = Path(__file__).parent.parent / "tasks"

# Sentinel a task can set to force-skip the visible tier even when its repo
# declares a suite in repos.yaml.
_FORCE_SKIP = "none"


def _repo_id(task: TaskSpec) -> str:
    return task.repo or task.repo_url.rstrip("/").split("/")[-1].lower()


def resolve_visible_test_cmd(task: TaskSpec, repos_yaml: Path = REPOS_YAML) -> str | None:
    """The effective visible_test_cmd for a task, applied to task.visible_test_cmd.

    - an explicit string  -> use it (task overrides the repo)
    - null / unset        -> the repo's repos.yaml cmd if it declares one, else None
    - the "none" sentinel -> None (force-skip even if the repo declares a suite)
    """
    cmd = task.visible_test_cmd
    if cmd == _FORCE_SKIP:
        return None
    if cmd:
        return cmd
    return get_repo_visible_test_cmd(_repo_id(task), repos_yaml)


def load_task(task_id: str, tasks_dir: Path = TASKS_DIR, repos_yaml: Path = REPOS_YAML) -> TaskSpec:
    task_path = tasks_dir / task_id / "task.yaml"
    if not task_path.exists():
        raise FileNotFoundError(f"No task.yaml for task '{task_id}' at {task_path}")
    raw = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    task = TaskSpec(**raw)
    # Bake the repo/override resolution into the effective field so the gate and
    # validator read a single value and need no repos.yaml awareness themselves.
    task.visible_test_cmd = resolve_visible_test_cmd(task, repos_yaml)
    return task


def list_tasks(tasks_dir: Path = TASKS_DIR) -> list[str]:
    if not tasks_dir.exists():
        return []
    return sorted(
        d.name for d in tasks_dir.iterdir()
        if d.is_dir() and (d / "task.yaml").exists()
    )


def resolve_repo_path(task: TaskSpec) -> Path:
    # An explicit `repo:` field wins (e.g. a vendored repo whose local dir name
    # differs from its URL basename); otherwise fall back to the URL basename.
    repo_name = task.repo or task.repo_url.rstrip("/").split("/")[-1].lower()
    return Path(__file__).parent.parent / "repos" / repo_name
