import subprocess
from pathlib import Path

import pytest

from core.models import MethodologySpec, RepoContextSpec, RunResult, TaskSpec, Trial
from core.worktree import create_worktree, destroy_worktree
from runners.base import Runner, capture_baseline, collect
from runners.claude_code import ClaudeCodeRunner
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
        baseline = capture_baseline(wt)
        (wt / "new_file.py").write_text("print('hello')\n")
        diff = collect(wt, baseline)
        assert "new_file.py" in diff
        assert "+print('hello')" in diff
    finally:
        destroy_worktree(wt)


def test_collect_requires_explicit_baseline(tiny_repo: Path):
    """collect() has no silent default. A runner whose harness COMMITS must pass a
    baseline captured before the agent ran, or its diff is erased (5fb9787). With
    no default, forgetting the baseline fails loudly at call time instead."""
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        with pytest.raises(TypeError):
            collect(wt)  # type: ignore[call-arg]
    finally:
        destroy_worktree(wt)


def test_capture_baseline_returns_head(tiny_repo: Path):
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        assert capture_baseline(wt) == head_commit(wt)
    finally:
        destroy_worktree(wt)


def test_collect_survives_undecodable_diff_bytes(tiny_repo: Path):
    """`git diff` output may contain bytes that aren't valid in the platform
    default codec (cp1252 on Windows) — e.g. UTF-8 content the agent wrote into
    a file. Without an explicit encoding, Python's subprocess reader thread
    swallows the decode error and communicate() silently returns None for that
    stream, so `result.stdout` becomes None and callers crash on `.strip()` etc.
    collect() must decode as UTF-8 (errors ignored) and always return a string.
    """
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        baseline = capture_baseline(wt)
        # 0x9d is undefined in cp1252 and an invalid lone byte in utf-8 — but no
        # NUL, so git still treats the file as text and shows the byte in the diff.
        (wt / "weird.txt").write_bytes(b"a line with a high byte \x9d in it\n")
        diff = collect(wt, baseline)
        assert diff is not None
        assert "weird.txt" in diff
    finally:
        destroy_worktree(wt)


def test_collect_captures_committed_changes(tiny_repo: Path):
    """An agent may COMMIT its work mid-session. collect() must diff against the
    setup baseline captured before the agent ran, not against the live HEAD — a
    commit advances HEAD, so `git diff HEAD` returns empty and silently discards
    the agent's entire (already-billed) diff. This is exactly what erased the
    sonnet trial's $1.84 of work on the cosmos-A shakedown."""
    commit = head_commit(tiny_repo)
    wt = create_worktree(tiny_repo, commit)
    try:
        baseline = head_commit(wt)  # post-setup baseline, before the "agent" runs
        (wt / "feature.py").write_text("def feature():\n    return 42\n")
        subprocess.run(["git", "add", "-A"], cwd=str(wt), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "agent work"], cwd=str(wt), check=True, capture_output=True)
        diff = collect(wt, baseline)
        assert "feature.py" in diff
        assert "+    return 42" in diff
    finally:
        destroy_worktree(wt)


# --- nop ---

def test_nop_produces_empty_diff(tiny_repo: Path):
    commit = head_commit(tiny_repo)
    methodology = MethodologySpec(id="off", files={})
    trial = Trial(id="t-nop", task_id="test-task", methodology_id="off", repo_context_id="none", model="none", runner="nop", rep=0)
    wt = create_worktree(tiny_repo, commit)
    try:
        runner = NopRunner()
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))
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
    trial = Trial(id="t-oracle", task_id="test-task", methodology_id="off", repo_context_id="none", model="none", runner="oracle", rep=0)
    wt = create_worktree(tiny_repo, commit)
    try:
        runner = OracleRunner(task)
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))
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
    trial = Trial(id="t-methodology", task_id="test-task", methodology_id="vanilla", repo_context_id="none", model="none", runner="nop", rep=0)
    wt = create_worktree(tiny_repo, commit)
    try:
        runner = NopRunner()
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))
        assert (wt / "CLAUDE.md").exists()
        content = (wt / "CLAUDE.md").read_text()
        assert "# Instructions" in content
        assert "Do the thing" in content
        result = runner.execute(trial, wt)
        assert result.diff == ""
    finally:
        destroy_worktree(wt)


def test_prepare_lays_down_unicode_methodology_files(tiny_repo: Path):
    """Methodology files routinely contain non-Latin-1 chars (→, emoji). Laydown
    must write UTF-8, not the platform default codec (cp1252 on Windows)."""
    commit = head_commit(tiny_repo)
    methodology = MethodologySpec(
        id="uni", files={"CLAUDE.md": ["# Rules", "plan → build → ship ✅"]}
    )
    trial = Trial(id="t-uni", task_id="test-task", methodology_id="uni", repo_context_id="none", model="none", runner="nop", rep=0)
    wt = create_worktree(tiny_repo, commit)
    try:
        runner = NopRunner()
        runner.prepare(trial, wt, methodology, RepoContextSpec(id="none", files={}))
        content = (wt / "CLAUDE.md").read_text(encoding="utf-8")
        assert "plan → build → ship ✅" in content
    finally:
        destroy_worktree(wt)


# --- repo context + methodology layering ---

def _commit_count(repo: Path) -> int:
    out = subprocess.run(
        ["git", "rev-list", "--count", "HEAD"],
        cwd=str(repo), check=True, capture_output=True, text=True,
    )
    return int(out.stdout.strip())


def test_prepare_lays_context_under_methodology(tiny_repo: Path):
    commit = head_commit(tiny_repo)
    methodology = MethodologySpec(id="vanilla", files={"CLAUDE.md": ["# Methodology"]})
    repo_context = RepoContextSpec(id="pyvrp-instructions", files={"README-rules.md": ["# Repo rules"]})
    trial = Trial(id="t-layer", task_id="test-task", methodology_id="vanilla", repo_context_id="pyvrp-instructions", model="none", runner="nop", rep=0)
    wt = create_worktree(tiny_repo, commit)
    try:
        before = _commit_count(wt)
        runner = NopRunner()
        runner.prepare(trial, wt, methodology, repo_context)
        # both files present
        assert (wt / "CLAUDE.md").read_text().strip() == "# Methodology"
        assert (wt / "README-rules.md").read_text().strip() == "# Repo rules"
        # two separate commits: context first, methodology second
        assert _commit_count(wt) == before + 2
    finally:
        destroy_worktree(wt)


# --- task visible-tests laydown ---

def _git_log_subjects(repo: Path) -> list[str]:
    out = subprocess.run(
        ["git", "log", "--format=%s"],
        cwd=str(repo), check=True, capture_output=True, text=True,
    )
    return out.stdout.splitlines()


def _visible_tests_task(tiny_repo: Path, visible_dir: Path) -> TaskSpec:
    return TaskSpec(
        id="vis-task",
        repo_url="file://" + str(tiny_repo).replace("\\", "/"),
        base_commit=head_commit(tiny_repo),
        instruction="Do the thing",
        run_cmd="echo ok",
        held_out_tests_path="tests/",
        reference_diff_path="x",
        visible_tests_path=str(visible_dir),
    )


def test_prepare_lays_down_task_visible_tests(tiny_repo: Path, tmp_path: Path):
    visible = tmp_path / "visible"
    (visible / "tests" / "search").mkdir(parents=True)
    (visible / "tests" / "search" / "test_visible.py").write_text(
        "def test_seen():\n    assert True\n"
    )
    task = _visible_tests_task(tiny_repo, visible)
    trial = Trial(id="t-vis", task_id="vis-task", methodology_id="off", repo_context_id="none", model="none", runner="claude-code", rep=0)
    wt = create_worktree(tiny_repo, task.base_commit)
    try:
        before = _commit_count(wt)
        runner = ClaudeCodeRunner(task)
        runner.prepare(trial, wt, MethodologySpec(id="off", files={}), RepoContextSpec(id="none", files={}))
        baseline = capture_baseline(wt)
        # File present in the worktree, mirroring the source layout.
        injected = wt / "tests" / "search" / "test_visible.py"
        assert injected.exists()
        # Its own commit, laid down before repo-context + methodology (3 total).
        assert _commit_count(wt) == before + 3
        subjects = _git_log_subjects(wt)
        assert subjects[2] == "setup-bench: lay down task visible tests"
        assert subjects[1] == "setup-bench: lay down repo context files"
        assert subjects[0] == "setup-bench: lay down methodology files"
        # Committed => NOT part of the model's diff.
        diff = collect(wt, baseline)
        assert "test_visible.py" not in diff
    finally:
        destroy_worktree(wt)


def test_prepare_skips_visible_tests_when_unset(tiny_repo: Path):
    task = TaskSpec(
        id="vis-task", repo_url="x", base_commit=head_commit(tiny_repo),
        instruction="x", run_cmd="echo ok", held_out_tests_path="tests/",
        reference_diff_path="x",
    )
    trial = Trial(id="t-novis", task_id="vis-task", methodology_id="off", repo_context_id="none", model="none", runner="claude-code", rep=0)
    wt = create_worktree(tiny_repo, task.base_commit)
    try:
        before = _commit_count(wt)
        runner = ClaudeCodeRunner(task)
        runner.prepare(trial, wt, MethodologySpec(id="off", files={}), RepoContextSpec(id="none", files={}))
        # Only the repo-context + methodology commits, no visible-tests commit.
        assert _commit_count(wt) == before + 2
        assert "lay down task visible tests" not in _git_log_subjects(wt)
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
