from pathlib import Path
import yaml
import pytest
from core.task_loader import list_tasks, load_task, resolve_repo_path
from core.models import TaskSpec


def test_list_tasks():
    tasks = list_tasks()
    assert set(tasks) == {"pyvrp-A", "pyvrp-B", "pyvrp-C"}


def test_load_task():
    task = load_task("pyvrp-A")
    assert isinstance(task, TaskSpec)
    assert task.id == "pyvrp-A"
    assert "PyVRP" in task.repo_url
    assert task.run_cmd != ""


def test_load_task_missing():
    with pytest.raises(FileNotFoundError, match="No task.yaml"):
        load_task("nonexistent-task")


def test_resolve_repo_path():
    task = TaskSpec(
        id="t", repo_url="https://github.com/PyVRP/PyVRP",
        base_commit="abc", instruction="x", run_cmd="x",
        held_out_tests_path="x", reference_diff_path="x",
    )
    path = resolve_repo_path(task)
    assert path.name == "pyvrp"


def test_load_task_with_custom_dir(tmp_path: Path):
    task_dir = tmp_path / "tasks" / "test-task"
    task_dir.mkdir(parents=True)
    data = {
        "id": "test-task",
        "repo_url": "https://github.com/example/repo",
        "base_commit": "abc123",
        "instruction": "Do something",
        "run_cmd": "pytest",
        "held_out_tests_path": "tests/hidden",
        "reference_diff_path": "diffs/ref.diff",
    }
    (task_dir / "task.yaml").write_text(yaml.dump(data))
    task = load_task("test-task", tasks_dir=tmp_path / "tasks")
    assert task.id == "test-task"
    assert task.repo_url == "https://github.com/example/repo"
