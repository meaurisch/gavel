import subprocess
import sys
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
        # sys.executable, not a bare "python": the studio-job image (and many
        # Linux distros) ship only `python3`, and the gate runs this through
        # the shell — an unversioned `python` fails the hidden tier there.
        run_cmd=f'"{sys.executable}" tests/check_hello.py',
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
    # No baseline ref -> provenance is unprovable -> any collision stays fatal.
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


def _set_baseline_ref(wt: Path, sha: str) -> None:
    subprocess.run(
        ["git", "update-ref", "refs/worktree/setup-bench-baseline", sha],
        cwd=str(wt), check=True, capture_output=True,
    )


def test_gate_fatal_when_held_out_present_via_setup(tiny_repo, held_out_dir, tmp_path):
    """A held-out path present in the baseline tree is a genuine setup leak: the
    model would have seen the oracle. Must stay fatal."""
    task = _make_task(tiny_repo, held_out_dir, tmp_path)
    trial = Trial(id="t-leak", task_id="test-task", methodology_id="off", repo_context_id="none", model="claude-sonnet-4-20250514", runner="claude-code", rep=0)
    wt = create_worktree(tiny_repo, task.base_commit)
    try:
        # Simulate a setup commit that lays a file at the held-out path, then
        # capture the baseline *including* it — i.e. the model would see it.
        (wt / "tests").mkdir()
        (wt / "tests" / "check_hello.py").write_text("# leaked via setup\n")
        subprocess.run(["git", "add", "-A"], cwd=str(wt), check=True, capture_output=True)
        subprocess.run(["git", "commit", "-m", "setup: leak"], cwd=str(wt), check=True, capture_output=True)
        _set_baseline_ref(wt, _head_commit(wt))
        with pytest.raises(AssertionError, match="via setup"):
            apply(trial, wt, task)
    finally:
        destroy_worktree(wt)


def test_gate_overwrites_agent_planted_held_out(tiny_repo, held_out_dir, tmp_path):
    """A held-out path present only in the agent's diff (not the baseline) is NOT
    a leak — the agent never saw the oracle. The gate overwrites it with the true
    oracle and runs that (oracle wins), then restores the agent's file."""
    task = _make_task(tiny_repo, held_out_dir, tmp_path)
    trial = Trial(id="t-agent", task_id="test-task", methodology_id="off", repo_context_id="none", model="claude-sonnet-4-20250514", runner="claude-code", rep=0)
    wt = create_worktree(tiny_repo, task.base_commit)
    try:
        # Baseline = clean base (no tests/); the agent then plants a cheating stub
        # that would always pass if it were the one that ran.
        _set_baseline_ref(wt, _head_commit(wt))
        (wt / "tests").mkdir()
        planted = wt / "tests" / "check_hello.py"
        cheat = "import sys\nsys.exit(0)\n"
        planted.write_text(cheat)

        result = apply(trial, wt, task)

        # The oracle ran, not the stub: hello.txt was never fixed -> real check fails.
        assert result.passed is False
        # The agent's file is restored (leave-no-trace).
        assert planted.read_text() == cheat
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


def test_gate_wsl_command_uses_utf8_encoding(tmp_path, monkeypatch):
    """Hidden-test stdout+stderr can contain agent-written content with bytes
    outside cp1252's range. Without an explicit encoding, Python's subprocess
    reader thread swallows the decode error and communicate() silently returns
    None, crashing the `result.stdout + result.stderr` concat downstream."""
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

    first_call = mock_run.call_args_list[0]
    assert first_call.kwargs.get("encoding") == "utf-8"
    assert first_call.kwargs.get("errors") == "ignore"


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
        # Skip the gate's own git infra calls (e.g. baseline-ref provenance lookup);
        # this test is about how *task* commands dispatch.
        if isinstance(first_arg, list) and first_arg[:1] == ["git"]:
            continue
        assert isinstance(first_arg, str), f"Expected str cmd, got {type(first_arg)}"
        assert call.kwargs.get("shell") is True


def test_gate_shell_command_uses_utf8_encoding(tmp_path, monkeypatch):
    """Same decode risk as the wsl branch (test_gate_wsl_command_uses_utf8_encoding),
    for the shell=True dispatch path (e.g. dotnet/cosmos tasks)."""
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

    task_calls = [
        c for c in mock_run.call_args_list
        if not (isinstance(c.args[0], list) and c.args[0][:1] == ["git"])
    ]
    assert task_calls
    for call in task_calls:
        assert call.kwargs.get("encoding") == "utf-8"
        assert call.kwargs.get("errors") == "ignore"


# --- observational (non-gating) tier ---


def test_observational_tier_absent_when_task_declares_none(tiny_repo, held_out_dir, tmp_path):
    task = _make_task(tiny_repo, held_out_dir, tmp_path)
    trial = Trial(id="t-noobs", task_id="test-task", methodology_id="off", repo_context_id="none", model="none", runner="oracle", rep=0)
    wt = create_worktree(tiny_repo, task.base_commit)
    try:
        runner = OracleRunner(task)
        runner.prepare(trial, wt, METHODOLOGY, REPO_CONTEXT)
        runner.execute(trial, wt)
        result = apply(trial, wt, task)
        assert result.observe_passed is None
        assert result.observe_output is None
    finally:
        destroy_worktree(wt)


def test_observational_failure_is_recorded_but_does_not_gate(tiny_repo, held_out_dir, tmp_path):
    """The whole point of the tier: a failing observation must not change
    `passed` (only gate-passers are gradeable, so gating on e.g. convention
    adherence would bias the grading pool)."""
    task = _make_task(tiny_repo, held_out_dir, tmp_path)
    task.observe_cmd = (
        f'"{sys.executable}" -c "print(\'ADHERENCE conventions FAIL\'); raise SystemExit(1)"'
    )
    trial = Trial(id="t-obs-fail", task_id="test-task", methodology_id="off", repo_context_id="none", model="none", runner="oracle", rep=0)
    wt = create_worktree(tiny_repo, task.base_commit)
    try:
        runner = OracleRunner(task)
        runner.prepare(trial, wt, METHODOLOGY, REPO_CONTEXT)
        runner.execute(trial, wt)
        result = apply(trial, wt, task)
        assert result.passed is True          # hidden tier alone decides
        assert result.hidden_passed is True
        assert result.observe_passed is False
        assert "ADHERENCE conventions FAIL" in result.observe_output
    finally:
        destroy_worktree(wt)


def test_observational_tier_passes_independently_of_gate(tiny_repo, held_out_dir, tmp_path):
    """A nop trial fails the hidden gate; its observation is still recorded."""
    task = _make_task(tiny_repo, held_out_dir, tmp_path)
    task.observe_cmd = f'"{sys.executable}" -c "print(\'ADHERENCE conventions PASS\')"'
    trial = Trial(id="t-obs-pass", task_id="test-task", methodology_id="off", repo_context_id="none", model="none", runner="nop", rep=0)
    wt = create_worktree(tiny_repo, task.base_commit)
    try:
        runner = NopRunner()
        runner.prepare(trial, wt, METHODOLOGY, REPO_CONTEXT)
        runner.execute(trial, wt)
        result = apply(trial, wt, task)
        assert result.passed is False
        assert result.observe_passed is True
        assert "ADHERENCE conventions PASS" in result.observe_output
    finally:
        destroy_worktree(wt)


def test_observational_tier_runs_after_a_build_failure(tmp_path, monkeypatch):
    """The compile tier short-circuits the gate; the observation still runs —
    a convention check is meaningful on a trial that didn't build."""
    held_out = tmp_path / "held_out"
    held_out.mkdir()
    task = TaskSpec(
        id="obs-X", repo_url="x", base_commit="x", instruction="add something",
        run_cmd="pytest -q", held_out_tests_path=str(held_out), reference_diff_path="x",
        build_cmd="build-it", observe_cmd="observe-it",
    )
    trial = Trial(
        id="t-obs-build", task_id="obs-X", methodology_id="off",
        repo_context_id="none", model="none", runner="nop", rep=0,
    )

    def fake_run(cmd, *args, **kwargs):
        m = MagicMock()
        m.returncode = 1 if cmd == "build-it" else 0
        m.stdout, m.stderr = ("out:" + str(cmd)), ""
        return m

    with patch("grading.gate.subprocess.run", side_effect=fake_run) as mock_run:
        result = apply(trial, tmp_path, task)

    assert result.compile_passed is False
    assert result.passed is False
    assert result.hidden_passed is None          # gate short-circuited
    assert result.observe_passed is True         # observation still recorded
    assert "observe-it" in result.observe_output
    assert any(c.args[0] == "observe-it" for c in mock_run.call_args_list)
