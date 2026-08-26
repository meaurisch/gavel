from pathlib import Path
import yaml
import pytest
from core.task_loader import list_tasks, load_task, resolve_repo_path, resolve_visible_test_cmd
from core.models import TaskSpec


def _repos_yaml(tmp_path: Path) -> Path:
    p = tmp_path / "repos.yaml"
    p.write_text("cosmos:\n  visible_test_cmd: 'dotnet test x.csproj'\n")
    return p


def _task(visible_test_cmd, repo="cosmos") -> TaskSpec:
    return TaskSpec(
        id="t", repo_url="https://github.com/x/y", base_commit="abc",
        instruction="x", run_cmd="x", held_out_tests_path="x",
        reference_diff_path="x", repo=repo, visible_test_cmd=visible_test_cmd,
    )


def test_resolve_explicit_override(tmp_path):
    task = _task("pytest visible.py")
    assert resolve_visible_test_cmd(task, _repos_yaml(tmp_path)) == "pytest visible.py"


def test_resolve_inherits_repo_cmd_when_unset(tmp_path):
    task = _task(None)
    assert resolve_visible_test_cmd(task, _repos_yaml(tmp_path)) == "dotnet test x.csproj"


def test_resolve_none_sentinel_force_skips(tmp_path):
    task = _task("none")
    assert resolve_visible_test_cmd(task, _repos_yaml(tmp_path)) is None


def test_resolve_unset_with_undeclared_repo(tmp_path):
    task = _task(None, repo="pyvrp")
    assert resolve_visible_test_cmd(task, _repos_yaml(tmp_path)) is None


def test_resolve_unset_with_no_repos_yaml(tmp_path):
    task = _task(None)
    assert resolve_visible_test_cmd(task, tmp_path / "missing.yaml") is None


def test_load_task_bakes_resolved_visible_cmd(tmp_path):
    task_dir = tmp_path / "tasks" / "cosmos-Z"
    task_dir.mkdir(parents=True)
    data = {
        "id": "cosmos-Z", "repo": "cosmos",
        "repo_url": "https://github.com/x/y", "base_commit": "abc",
        "instruction": "Do something real here for the loader",
        "run_cmd": "dotnet test", "held_out_tests_path": "h",
        "reference_diff_path": "d", "visible_test_cmd": None,
    }
    (task_dir / "task.yaml").write_text(yaml.dump(data))
    task = load_task("cosmos-Z", tasks_dir=tmp_path / "tasks", repos_yaml=_repos_yaml(tmp_path))
    assert task.visible_test_cmd == "dotnet test x.csproj"


def test_list_tasks():
    tasks = list_tasks()
    assert set(tasks) == {
        "pyvrp-A", "pyvrp-B", "pyvrp-C",
        "cosmos-A", "cosmos-B",
        "moreiter-A",
        "studio-A", "studio-B", "studio-C",
    }


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


def test_resolve_repo_path_honors_explicit_repo_field():
    task = TaskSpec(
        id="cosmos-A", repo_url="https://github.com/ShawnShiSS/clean-architecture-azure-cosmos-db",
        base_commit="abc", instruction="x", run_cmd="x",
        held_out_tests_path="x", reference_diff_path="x", repo="cosmos",
    )
    assert resolve_repo_path(task).name == "cosmos"


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
