import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import check_grading_ready as cgr  # noqa: E402
from core.db import connect, insert_trial, insert_gate_result  # noqa: E402
from core.models import Trial, GateResult  # noqa: E402


def _trial(tid: str, methodology_id: str) -> Trial:
    return Trial(
        id=tid, task_id="t1", methodology_id=methodology_id, repo_context_id="none",
        model="claude", runner="oracle", rep=0,
    )


@pytest.fixture()
def conn(tmp_path):
    return connect(tmp_path / "r.db")


def test_is_ready_false_when_no_gradeable_cells(conn):
    from core.db import grading_readiness

    data = grading_readiness(conn)
    assert cgr.is_ready(data) is False


def test_is_ready_true_when_a_cell_has_two_passing_values(conn):
    from core.db import grading_readiness

    insert_trial(conn, _trial("a0", "m1"))
    insert_trial(conn, _trial("a1", "m2"))
    insert_gate_result(conn, GateResult(trial_id="a0", passed=True))
    insert_gate_result(conn, GateResult(trial_id="a1", passed=True))

    data = grading_readiness(conn)
    assert cgr.is_ready(data) is True


def test_format_report_lists_all_axes(conn):
    from core.db import grading_readiness

    data = grading_readiness(conn)
    report = cgr.format_report(data)
    assert "methodology" in report
    assert "model" in report
    assert "repo_context" in report
    assert "runner" in report


def test_main_exits_1_when_db_has_no_gradeable_cells(tmp_path, monkeypatch):
    db_path = tmp_path / "empty.db"
    connect(db_path)  # create schema, no trials

    monkeypatch.setattr(sys, "argv", ["check_grading_ready.py", "--db", str(db_path)])
    with pytest.raises(SystemExit) as exc:
        cgr.main()
    assert exc.value.code == 1


def test_main_exits_0_when_db_has_a_gradeable_cell(tmp_path, monkeypatch):
    db_path = tmp_path / "ready.db"
    conn = connect(db_path)
    insert_trial(conn, _trial("a0", "m1"))
    insert_trial(conn, _trial("a1", "m2"))
    insert_gate_result(conn, GateResult(trial_id="a0", passed=True))
    insert_gate_result(conn, GateResult(trial_id="a1", passed=True))

    monkeypatch.setattr(sys, "argv", ["check_grading_ready.py", "--db", str(db_path)])
    with pytest.raises(SystemExit) as exc:
        cgr.main()
    assert exc.value.code == 0


def test_main_exits_1_when_db_missing(tmp_path, monkeypatch):
    missing = tmp_path / "nope.db"
    monkeypatch.setattr(sys, "argv", ["check_grading_ready.py", "--db", str(missing)])
    with pytest.raises(SystemExit) as exc:
        cgr.main()
    assert exc.value.code == 1
