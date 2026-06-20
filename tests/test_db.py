import sqlite3

import pytest

from core.db import (
    connect,
    get_cost_record,
    get_gate_result,
    get_run_result,
    get_setup_spec,
    get_task_spec,
    get_trial,
    insert_cost_record,
    insert_gate_result,
    insert_run_result,
    insert_setup_spec,
    insert_task_spec,
    insert_trial,
    list_trials,
    trial_exists,
)
from core.models import (
    CostRecord,
    GateResult,
    RunResult,
    SetupSpec,
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


def test_setup_spec_insert_read(conn):
    obj = SetupSpec(
        id="vanilla",
        files={"pyproject.toml": ["[tool.pytest.ini_options]", "minversion = '8'"]},
    )
    insert_setup_spec(conn, obj)
    got = get_setup_spec(conn, "vanilla")
    assert got == obj


def test_trial_insert_read(conn):
    obj = Trial(
        id="t-001",
        task_id="cosmos-001",
        setup_id="vanilla",
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
        test_output="All tests passed.",
    )
    insert_gate_result(conn, obj)
    got = get_gate_result(conn, "t-001")
    assert got == obj
    assert got.passed is True


def test_append_only_reinsert_raises(conn):
    obj = Trial(
        id="t-dup",
        task_id="cosmos-001",
        setup_id="vanilla",
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
        setup_id="vanilla",
        model="claude-3-5-sonnet",
        runner="claude-code",
        rep=0,
    )
    insert_trial(conn, obj)
    assert trial_exists(conn, "t-exists") is True


def test_list_trials(conn):
    assert list_trials(conn) == []
    t1 = Trial(id="t-1", task_id="c1", setup_id="v", model="m", runner="r", rep=0)
    t2 = Trial(id="t-2", task_id="c2", setup_id="v", model="m", runner="r", rep=1)
    insert_trial(conn, t1)
    insert_trial(conn, t2)
    trials = list_trials(conn)
    assert len(trials) == 2
    ids = {t.id for t in trials}
    assert ids == {"t-1", "t-2"}
