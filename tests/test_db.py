import sqlite3

import pytest

from core.db import (
    connect,
    get_cost_record,
    get_gate_result,
    get_methodology_spec,
    get_repo_context_spec,
    get_run_result,
    get_task_spec,
    get_trial,
    insert_cost_record,
    insert_gate_result,
    insert_methodology_spec,
    insert_repo_context_spec,
    insert_run_result,
    insert_task_spec,
    insert_trial,
    list_cell_trials,
    list_passing_trials,
    list_trials,
    trial_exists,
)
from core.models import (
    CostRecord,
    GateResult,
    MethodologySpec,
    RepoContextSpec,
    RunResult,
    TaskSpec,
    Trial,
)


@pytest.fixture()
def conn(tmp_path):
    db_path = tmp_path / "test.db"
    return connect(db_path)


def test_task_spec_insert_read(conn):
    obj = TaskSpec(
        id="cosmos-001",
        repo_url="https://github.com/example/cosmos",
        base_commit="abc123",
        instruction="Fix the broken import",
        run_cmd="pytest tests/",
        held_out_tests_path="tests/test_hidden.py",
        reference_diff_path="diffs/cosmos-001.patch",
    )
    insert_task_spec(conn, obj)
    got = get_task_spec(conn, "cosmos-001")
    assert got == obj


def test_methodology_spec_insert_read(conn):
    obj = MethodologySpec(
        id="vanilla",
        files={"pyproject.toml": ["[tool.pytest.ini_options]", "minversion = '8'"]},
    )
    insert_methodology_spec(conn, obj)
    got = get_methodology_spec(conn, "vanilla")
    assert got == obj


def test_repo_context_spec_insert_read(conn):
    obj = RepoContextSpec(
        id="repo-instructions",
        files={"CLAUDE.md": ["# Repo rules", "Be concise"]},
    )
    insert_repo_context_spec(conn, obj)
    got = get_repo_context_spec(conn, "repo-instructions")
    assert got == obj


def test_repo_context_spec_missing_returns_none(conn):
    assert get_repo_context_spec(conn, "nope") is None


def test_trial_insert_read(conn):
    obj = Trial(
        id="t-001",
        task_id="cosmos-001",
        methodology_id="vanilla",
        repo_context_id="none",
        model="claude-3-5-sonnet",
        runner="claude-code",
        rep=0,
    )
    insert_trial(conn, obj)
    got = get_trial(conn, "t-001")
    assert got == obj


def test_run_result_insert_read(conn):
    obj = RunResult(
        trial_id="t-001",
        diff="--- a/x\n+++ b/x\n",
        exit_status=0,
        wall_seconds=12.3,
    )
    insert_run_result(conn, obj)
    got = get_run_result(conn, "t-001")
    assert got == obj


def test_cost_record_insert_read(conn):
    obj = CostRecord(
        trial_id="t-001",
        native_unit="tokens",
        native_amount=15000.0,
        usd_equiv=0.045,
        input_tokens=10000,
        output_tokens=5000,
        cache_read_tokens=2000,
    )
    insert_cost_record(conn, obj)
    got = get_cost_record(conn, "t-001")
    assert got == obj


def test_gate_result_insert_read(conn):
    obj = GateResult(
        trial_id="t-001",
        passed=True,
        hidden_passed=True,
        hidden_output="All tests passed.",
    )
    insert_gate_result(conn, obj)
    got = get_gate_result(conn, "t-001")
    assert got == obj
    assert got.passed is True
    assert got.hidden_passed is True


def test_append_only_reinsert_raises(conn):
    obj = Trial(
        id="t-dup",
        task_id="cosmos-001",
        methodology_id="vanilla",
        repo_context_id="none",
        model="claude-3-5-sonnet",
        runner="claude-code",
        rep=0,
    )
    insert_trial(conn, obj)
    with pytest.raises(sqlite3.IntegrityError):
        insert_trial(conn, obj)


def test_trial_exists(conn):
    assert trial_exists(conn, "nonexistent") is False
    obj = Trial(
        id="t-exists",
        task_id="cosmos-001",
        methodology_id="vanilla",
        repo_context_id="none",
        model="claude-3-5-sonnet",
        runner="claude-code",
        rep=0,
    )
    insert_trial(conn, obj)
    assert trial_exists(conn, "t-exists") is True


def test_list_trials(conn):
    assert list_trials(conn) == []
    t1 = Trial(id="t-1", task_id="c1", methodology_id="v", repo_context_id="none", model="m", runner="r", rep=0)
    t2 = Trial(id="t-2", task_id="c2", methodology_id="v", repo_context_id="none", model="m", runner="r", rep=1)
    insert_trial(conn, t1)
    insert_trial(conn, t2)
    trials = list_trials(conn)
    assert len(trials) == 2
    ids = {t.id for t in trials}
    assert ids == {"t-1", "t-2"}


def test_task_spec_difficulty_insert_read(conn):
    obj = TaskSpec(
        id="cosmos-001",
        repo_url="https://github.com/example/cosmos",
        base_commit="abc123",
        instruction="Fix the broken import",
        run_cmd="pytest tests/",
        held_out_tests_path="tests/test_hidden.py",
        reference_diff_path="diffs/cosmos-001.patch",
        difficulty="hard",
    )
    insert_task_spec(conn, obj)
    got = get_task_spec(conn, "cosmos-001")
    assert got == obj
    assert got.difficulty == "hard"


def test_init_schema_migrates_legacy_task_spec(tmp_path):
    # A DB created before build_cmd/visible_test_cmd/difficulty existed.
    db_path = tmp_path / "legacy.db"
    raw = sqlite3.connect(str(db_path))
    raw.execute(
        """CREATE TABLE task_spec (
            id TEXT PRIMARY KEY, repo_url TEXT NOT NULL, base_commit TEXT NOT NULL,
            instruction TEXT NOT NULL, run_cmd TEXT NOT NULL,
            held_out_tests_path TEXT NOT NULL, reference_diff_path TEXT NOT NULL)"""
    )
    raw.execute(
        "INSERT INTO task_spec VALUES (?, ?, ?, ?, ?, ?, ?)",
        ("legacy", "url", "abc", "do it", "pytest", "tests/", "ref.diff"),
    )
    raw.commit()
    raw.close()

    conn = connect(db_path)  # connect() -> init_schema() must migrate
    got = get_task_spec(conn, "legacy")
    assert got.difficulty is None
    assert got.build_cmd is None
    assert got.visible_test_cmd is None


def test_list_cell_trials_includes_failing(conn):
    # one cell (task=c1, model=m), two methodologies, mix of pass/fail
    trials = [
        Trial(id="p1", task_id="c1", methodology_id="m1", repo_context_id="ctx", model="m", runner="r", rep=0),
        Trial(id="f1", task_id="c1", methodology_id="m1", repo_context_id="ctx", model="m", runner="r", rep=1),
        Trial(id="p2", task_id="c1", methodology_id="m2", repo_context_id="ctx", model="m", runner="r", rep=0),
        # different cell (other task) -> must be excluded
        Trial(id="other", task_id="c2", methodology_id="m1", repo_context_id="ctx", model="m", runner="r", rep=0),
    ]
    for t in trials:
        insert_trial(conn, t)
    insert_gate_result(conn, GateResult(trial_id="p1", passed=True))
    insert_gate_result(conn, GateResult(trial_id="f1", passed=False))
    insert_gate_result(conn, GateResult(trial_id="p2", passed=True))
    insert_gate_result(conn, GateResult(trial_id="other", passed=True))

    cell = list_cell_trials(conn, task_id="c1", model="m")
    assert {t.id for t in cell} == {"p1", "f1", "p2"}  # failing f1 included, other-task excluded

    passing = list_passing_trials(conn, task_id="c1", model="m")
    assert {t.id for t in passing} == {"p1", "p2"}

    # a trial without any gate row still counts as a cell member
    insert_trial(conn, Trial(id="nogate", task_id="c1", methodology_id="m3", repo_context_id="ctx", model="m", runner="r", rep=0))
    cell2 = list_cell_trials(conn, task_id="c1", model="m")
    assert "nogate" in {t.id for t in cell2}
