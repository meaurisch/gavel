import subprocess
from pathlib import Path

import pytest

from core.models import MethodologySpec, RunResult, TaskSpec, Trial
from core.worktree import create_worktree, destroy_worktree
from runners.base import Runner, collect
from runners.nop import NopRunner
from runners.oracle import OracleRunner
from tests.conftest import head_commit


# --- worktree lifecycle ---

def test_worktree_create_destroy(tiny_repo: Path):
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    assert wt.exists()
    assert (wt / "hello.txt").read_text() == "hello\n"
    destroy_worktree(wt)
    assert not wt.exists()


def test_worktree_at_base_commit(tiny_repo: Path):
    (tiny_repo / "hello.txt").write_text("modified\n")
    subprocess.run(["git", "add", "hello.txt"], cwd=str(tiny_repo), check=True, capture_output=True)
    subprocess.run(["git", "commit", "-m", "modify"], cwd=str(tiny_repo), check=True, capture_output=True)
    first = subprocess.run(
        ["git", "rev-list", "--max-parents=0", "HEAD"],
        cwd=str(tiny_repo), check=True, capture_output=True, text=True,
    ).stdout.strip()
    wt = create_worktree(tiny_repo, first)
    try:
        assert (wt / "hello.txt").read_text() == "hello\n"
    finally:
        destroy_worktree(wt)


# --- collect ---

def test_collect_captures_new_files(tiny_repo: Path):
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        (wt / "new_file.py").write_text("print('hello')\n")
        diff = collect(wt)
        assert "new_file.py" in diff
        assert "+print('hello')" in diff
    finally:
        destroy_worktree(wt)


# --- nop ---

def test_nop_produces_empty_diff(tiny_repo: Path):
    commit = head_commit(tiny_repo)
    methodology = MethodologySpec(id="off", files={})
    trial = Trial(id="t-nop", task_id="test-task", methodology_id="off", model="none", runner="nop", rep=0)
    wt = create_worktree(tiny_repo, commit)
    try:
        runner = NopRunner()
        runner.prepare(trial, wt, methodology)
        result = runner.execute(trial, wt)
        assert result.exit_status == 0
        assert result.diff == ""
        assert result.trial_id == "t-nop"
    finally:
        destroy_worktree(wt)


# --- oracle ---

def test_oracle_produces_expected_diff(tiny_repo: Path, tmp_path: Path):
    commit = head_commit(tiny_repo)
    ref_diff = tmp_path / "reference.diff"
    ref_diff.write_text(
        "--- a/hello.txt\n"
        "+++ b/hello.txt\n"
        "@@ -1 +1 @@\n"
        "-hello\n"
        "+hello world\n"
    )
    task = TaskSpec(
        id="test-task",
        repo_url="file://" + str(tiny_repo).replace("\\", "/"),
        base_commit=commit,
        instruction="Add world to hello",
        run_cmd="echo ok",
        held_out_tests_path="tests/",
        reference_diff_path=str(ref_diff),
    )
    methodology = MethodologySpec(id="off", files={})
    trial = Trial(id="t-oracle", task_id="test-task", methodology_id="off", model="none", runner="oracle", rep=0)
    wt = create_worktree(tiny_repo, commit)
    try:
        runner = OracleRunner(task)
        runner.prepare(trial, wt, methodology)
        result = runner.execute(trial, wt)
        assert result.exit_status == 0
        assert "-hello" in result.diff
        assert "+hello world" in result.diff
        assert result.trial_id == "t-oracle"
        assert result.wall_seconds >= 0
    finally:
        destroy_worktree(wt)


# --- methodology files ---

def test_prepare_lays_down_methodology_files(tiny_repo: Path):
    commit = head_commit(tiny_repo)
    methodology = MethodologySpec(id="vanilla", files={"CLAUDE.md": ["# Instructions", "Do the thing"]})
    trial = Trial(id="t-methodology", task_id="test-task", methodology_id="vanilla", model="none", runner="nop", rep=0)
    wt = create_worktree(tiny_repo, commit)
    try:
        runner = NopRunner()
        runner.prepare(trial, wt, methodology)
        assert (wt / "CLAUDE.md").exists()
        content = (wt / "CLAUDE.md").read_text()
        assert "# Instructions" in content
        assert "Do the thing" in content
        result = runner.execute(trial, wt)
        assert result.diff == ""
    finally:
        destroy_worktree(wt)


# --- protocol conformance ---

def test_oracle_conforms_to_runner_protocol():
    task = TaskSpec(
        id="t", repo_url="x", base_commit="x", instruction="x",
        run_cmd="x", held_out_tests_path="x", reference_diff_path="x",
    )
    assert isinstance(OracleRunner(task), Runner)


def test_nop_conforms_to_runner_protocol():
    assert isinstance(NopRunner(), Runner)
