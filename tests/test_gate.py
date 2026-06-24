import subprocess
from pathlib import Path

import pytest

from core.models import MethodologySpec, TaskSpec, Trial
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


# --- gate tests ---


def test_gate_passes_for_oracle(tiny_repo, held_out_dir, tmp_path):
    task = _make_task(tiny_repo, held_out_dir, tmp_path)
    trial = Trial(id="t-oracle", task_id="test-task", methodology_id="off", model="none", runner="oracle", rep=0)
    wt = create_worktree(tiny_repo, task.base_commit)
    try:
        runner = OracleRunner(task)
        runner.prepare(trial, wt, METHODOLOGY)
        runner.execute(trial, wt)
        result = apply(trial, wt, task)
        assert result.passed is True
        assert result.trial_id == "t-oracle"
        assert not (wt / "tests" / "check_hello.py").exists()
    finally:
        destroy_worktree(wt)


def test_gate_fails_for_nop(tiny_repo, held_out_dir, tmp_path):
    task = _make_task(tiny_repo, held_out_dir, tmp_path)
    trial = Trial(id="t-nop", task_id="test-task", methodology_id="off", model="none", runner="nop", rep=0)
    wt = create_worktree(tiny_repo, task.base_commit)
    try:
        runner = NopRunner()
        runner.prepare(trial, wt, METHODOLOGY)
        runner.execute(trial, wt)
        result = apply(trial, wt, task)
        assert result.passed is False
        assert result.trial_id == "t-nop"
        assert not (wt / "tests" / "check_hello.py").exists()
    finally:
        destroy_worktree(wt)


def test_gate_asserts_held_out_absent(tiny_repo, held_out_dir, tmp_path):
    task = _make_task(tiny_repo, held_out_dir, tmp_path)
    trial = Trial(id="t-cheat", task_id="test-task", methodology_id="off", model="none", runner="nop", rep=0)
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
