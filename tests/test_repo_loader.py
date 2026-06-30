from pathlib import Path

from core.repo_loader import get_repo_visible_test_cmd, load_repos


def _write_repos(tmp_path: Path) -> Path:
    p = tmp_path / "repos.yaml"
    p.write_text("cosmos:\n  visible_test_cmd: 'dotnet test x.csproj'\n")
    return p


def test_load_repos_returns_mapping(tmp_path):
    repos = load_repos(_write_repos(tmp_path))
    assert repos["cosmos"]["visible_test_cmd"] == "dotnet test x.csproj"


def test_load_repos_missing_file_is_empty(tmp_path):
    assert load_repos(tmp_path / "nope.yaml") == {}


def test_get_visible_test_cmd_declared(tmp_path):
    assert get_repo_visible_test_cmd("cosmos", _write_repos(tmp_path)) == "dotnet test x.csproj"


def test_get_visible_test_cmd_undeclared_repo(tmp_path):
    assert get_repo_visible_test_cmd("pyvrp", _write_repos(tmp_path)) is None


def test_real_repos_yaml_declares_cosmos():
    # The shipped repos.yaml opts cosmos into repo-level visible tests.
    assert get_repo_visible_test_cmd("cosmos") is not None
    assert get_repo_visible_test_cmd("pyvrp") is None
