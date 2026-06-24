import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import calibrate_tasks as ct  # noqa: E402
from core.db import connect, insert_trial, insert_gate_result  # noqa: E402
from core.models import Trial, GateResult  # noqa: E402


def _trial(tid: str, task_id: str, rep: int) -> Trial:
    return Trial(
        id=tid, task_id=task_id, methodology_id="m", repo_context_id="none",
        model="claude", runner="oracle", rep=rep,
    )


@pytest.fixture()
def conn(tmp_path):
    return connect(tmp_path / "r.db")


def test_classify_bands():
    assert ct.classify(0.90) == ("easy", "pass rate >70%, may not discriminate between methodologies")
    assert ct.classify(0.45)[0] == "medium"
    assert ct.classify(0.45)[1] is None
    assert ct.classify(0.10)[0] == "hard"
    assert ct.classify(0.10)[1] is not None


def test_classify_boundaries_are_medium():
    assert ct.classify(0.70)[0] == "medium"
    assert ct.classify(0.30)[0] == "medium"


def test_task_pass_counts(conn):
    insert_trial(conn, _trial("a0", "pyvrp-A", 0))
    insert_trial(conn, _trial("a1", "pyvrp-A", 1))
    insert_gate_result(conn, GateResult(trial_id="a0", passed=True))
    insert_gate_result(conn, GateResult(trial_id="a1", passed=False))
    assert ct.task_pass_counts(conn) == {"pyvrp-A": (1, 2)}


def test_task_pass_counts_skips_trials_without_gate(conn):
    insert_trial(conn, _trial("a0", "pyvrp-A", 0))  # no gate result inserted
    assert ct.task_pass_counts(conn) == {}


def test_format_report_flags_ceiling(conn):
    insert_trial(conn, _trial("b0", "pyvrp-B", 0))
    insert_gate_result(conn, GateResult(trial_id="b0", passed=True))
    report = ct.format_report(ct.task_pass_counts(conn))
    assert "pyvrp-B" in report
    assert "100%" in report
    assert "WARNING" in report
    assert "Recommendations:" in report
