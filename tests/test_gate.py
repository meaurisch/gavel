import subprocess
from pathlib import Path
from unittest.mock import MagicMock, patch

import pytest

from core.models import MethodologySpec, RepoContextSpec, TaskSpec, Trial
from core.worktree import create_worktree, destroy_worktree
from grading.gate import apply
from grading.leakage import scan
from runners.nop import NopRunner
from runners.oracle import OracleRunner


@pytest.fixture()
def tiny_repo(tmp_path: Path) -> Path:
    repo = tmp_path / "repo"
    repo.mkdir()
    subprocess.run(["git", "init"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "config", "user.email", "test@test.com"],
        cwd=str(repo), check=True, capture_output=True,
    )
    subprocess.run(
        ["git", "config", "user.name", "Test"],
        cwd=str(repo), check=True, capture_output=True,
    )
    (repo / "hello.txt").write_text("hello\n")
    subprocess.run(["git", "add", "hello.txt"], cwd=str(repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "initial"], cwd=str(repo), check=True, capture_output=True)
    return repo


def _head_commit(repo: Path) -> str:
    result = subprocess.run(
        ["git", "rev-parse", "HEAD"],
        cwd=str(repo), check=True, capture_output=True, text=True,
    )
    return result.stdout.strip()


@pytest.fixture()
def held_out_dir(tmp_path: Path) -> Path:
    d = tmp_path / "held_out"
    d.mkdir()
    (d / "check_hello.py").write_text(
        "import pathlib, sys\n"
        "text = pathlib.Path('hello.txt').read_text()\n"
        "sys.exit(0 if 'hello world' in text else 1)\n"
    )
    return d


def _make_task(tiny_repo, held_out_dir, tmp_path) -> TaskSpec:
    ref_diff = tmp_path / "reference.diff"
    ref_diff.write_text(
        "--- a/hello.txt\n"
        "+++ b/hello.txt\n"
        "@@ -1 +1 @@\n"
        "-hello\n"
        "+hello world\n"
    )
    return TaskSpec(
        id="test-task",
        repo_url="file://" + str(tiny_repo).replace("\\", "/"),
        base_commit=_head_commit(tiny_repo),
        instruction="Add world to hello",
        run_cmd="python tests/check_hello.py",
        held_out_tests_path=str(held_out_dir),
        reference_diff_path=str(ref_diff),
    )


METHODOLOGY = MethodologySpec(id="off", files={})
REPO_CONTEXT = RepoContextSpec(id="none", files={})


# --- gate tests ---


def test_gate_passes_for_oracle(tiny_repo, held_out_dir, tmp_path):
    task = _make_task(tiny_repo, held_out_dir, tmp_path)
    trial = Trial(id="t-oracle", task_id="test-task", methodology_id="off", repo_context_id="none", model="none", runner="oracle", rep=0)
    wt = create_worktree(tiny_repo, task.base_commit)
    try:
        runner = OracleRunner(task)
        runner.prepare(trial, wt, METHODOLOGY, REPO_CONTEXT)
        runner.execute(trial, wt)
        result = apply(trial, wt, task)
        assert result.passed is True
        assert result.trial_id == "t-oracle"
        assert not (wt / "tests" / "check_hello.py").exists()
    finally:
        destroy_worktree(wt)


def test_gate_fails_for_nop(tiny_repo, held_out_dir, tmp_path):
    task = _make_task(tiny_repo, held_out_dir, tmp_path)
    trial = Trial(id="t-nop", task_id="test-task", methodology_id="off", repo_context_id="none", model="none", runner="nop", rep=0)
    wt = create_worktree(tiny_repo, task.base_commit)
    try:
        runner = NopRunner()
        runner.prepare(trial, wt, METHODOLOGY, REPO_CONTEXT)
        runner.execute(trial, wt)
        result = apply(trial, wt, task)
        assert result.passed is False
        assert result.trial_id == "t-nop"
        assert not (wt / "tests" / "check_hello.py").exists()
    finally:
        destroy_worktree(wt)


def test_gate_asserts_held_out_absent(tiny_repo, held_out_dir, tmp_path):
    task = _make_task(tiny_repo, held_out_dir, tmp_path)
    trial = Trial(id="t-cheat", task_id="test-task", methodology_id="off", repo_context_id="none", model="none", runner="nop", rep=0)
    wt = create_worktree(tiny_repo, task.base_commit)
    try:
        (wt / "tests").mkdir()
        (wt / "tests" / "check_hello.py").write_text("# planted")
        with pytest.raises(AssertionError, match="held-out test already present"):
            apply(trial, wt, task)
    finally:
        destroy_worktree(wt)


# --- leakage tests ---


def test_leakage_finds_planted_reference(tiny_repo):
    (tiny_repo / "module.py").write_text(
        "# TODO: remove old_feature_flag()\n"
        "result = old_feature_flag()\n"
    )
    subprocess.run(["git", "add", "module.py"], cwd=str(tiny_repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add module with old_feature_flag"],
        cwd=str(tiny_repo), check=True, capture_output=True,
    )
    report = scan(tiny_repo, ["old_feature_flag"])
    assert report.any_found is True
    assert len(report.hits) >= 2
    working_tree_hits = [h for h in report.hits if not h.startswith("git-log:")]
    assert any("module.py" in h for h in working_tree_hits)
    assert any(h.startswith("comment ") for h in report.hits)
    git_log_hits = [h for h in report.hits if h.startswith("git-log:")]
    assert len(git_log_hits) >= 1


def test_leakage_clean_when_no_terms(tiny_repo):
    report = scan(tiny_repo, ["nonexistent_symbol_xyz"])
    assert report.any_found is False
    assert report.hits == []


def test_leakage_survives_undecodable_git_log_bytes(tiny_repo):
    """`git log -p` may contain bytes that aren't valid in the platform default
    codec (real repos like PyVRP have them). scan() must not crash decoding them.
    """
    # 0x9d is undefined in cp1252 and an invalid lone byte in utf-8 — but no NUL,
    # so git treats the file as text and shows the byte in `git log -p`.
    (tiny_repo / "weird.txt").write_bytes(b"a line with a high byte \x9d in it\n")
    subprocess.run(["git", "add", "weird.txt"], cwd=str(tiny_repo), check=True, capture_output=True)
    subprocess.run(
        ["git", "commit", "-m", "add file with non-codec byte"],
        cwd=str(tiny_repo), check=True, capture_output=True,
    )
    # Must return a report rather than raising on the git-log decode.
    report = scan(tiny_repo, ["nonexistent_symbol_xyz"])
    assert report.any_found is False


# --- WSL dispatch tests (mocked subprocess, no real build) ---


def _mock_ok() -> MagicMock:
    m = MagicMock()
    m.returncode = 0
    m.stdout = ""
    m.stderr = ""
    return m


def test_gate_dispatches_pyvrp_build_to_wsl(tmp_path, monkeypatch):
    """On Windows with an editable pip install, compile tier must call wsl."""
    monkeypatch.setattr("core.toolchain.platform.system", lambda: "Windows")

    held_out = tmp_path / "held_out"
    held_out.mkdir()

    task = TaskSpec(
        id="pyvrp-X",
        repo_url="x",
        base_commit="x",
        instruction="add something",
        run_cmd="pytest tests/search/test_ReplaceGroup.py -v",
        held_out_tests_path=str(held_out),
        reference_diff_path="x",
        build_cmd="pip install -e . 2>&1",
    )
    trial = Trial(
        id="t-pyvrp", task_id="pyvrp-X", methodology_id="off",
        repo_context_id="none", model="none", runner="nop", rep=0,
    )

    with patch("grading.gate.subprocess.run", return_value=_mock_ok()) as mock_run:
        apply(trial, tmp_path, task)

    # First call is compile tier (build_cmd).
    first_arg = mock_run.call_args_list[0].args[0]
    assert isinstance(first_arg, list)
    assert first_arg[0] == "wsl"
    script = first_arg[-1]
    assert "pip install -e . --no-build-isolation" in script


def test_gate_dispatches_dotnet_to_shell(tmp_path, monkeypatch):
    """Cosmos/dotnet tasks must use shell=True, never wsl."""
    monkeypatch.setattr("core.toolchain.platform.system", lambda: "Windows")

    held_out = tmp_path / "held_out"
    held_out.mkdir()

    task = TaskSpec(
        id="cosmos-A",
        repo_url="x",
        base_commit="x",
        instruction="add something",
        run_cmd="dotnet test CleanArchitectureCosmosDB.sln",
        held_out_tests_path=str(held_out),
        reference_diff_path="x",
        build_cmd="dotnet build CleanArchitectureCosmosDB.sln",
    )
    trial = Trial(
        id="t-cosmos", task_id="cosmos-A", methodology_id="off",
        repo_context_id="none", model="none", runner="nop", rep=0,
    )

    with patch("grading.gate.subprocess.run", return_value=_mock_ok()) as mock_run:
        apply(trial, tmp_path, task)

    for call in mock_run.call_args_list:
        first_arg = call.args[0]
        assert isinstance(first_arg, str), f"Expected str cmd, got {type(first_arg)}"
        assert call.kwargs.get("shell") is True
