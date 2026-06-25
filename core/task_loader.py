"""Task loader — reads tasks/{task_id}/task.yaml into TaskSpec."""

from pathlib import Path
import yaml
from core.models import TaskSpec

TASKS_DIR = Path(__file__).parent.parent / "tasks"


def load_task(task_id: str, tasks_dir: Path = TASKS_DIR) -> TaskSpec:
    task_path = tasks_dir / task_id / "task.yaml"
    if not task_path.exists():
        raise FileNotFoundError(f"No task.yaml for task '{task_id}' at {task_path}")
    raw = yaml.safe_load(task_path.read_text(encoding="utf-8"))
    return TaskSpec(**raw)


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
