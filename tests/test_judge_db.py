"""DB layer for the LLM-judge mode: schema backfill, grader-tagged judgments,
llm grading sessions, the judge_call audit table, and grader-filtered
Bradley-Terry comparisons."""

import sqlite3
from pathlib import Path

import pytest

from core.db import (
    connect,
    get_grading_session,
    insert_gate_result,
    insert_grading_session,
    insert_judgment,
    insert_judge_call,
    insert_trial,
    list_judge_calls,
    list_judgments,
    judge_call_rollup,
    upsert_judgment,
)
from core.models import GateResult, GradingSession, Judgment, JudgeCallRecord, Trial
from grading.aggregate import judgments_to_comparisons


@pytest.fixture()
def conn(tmp_path: Path) -> sqlite3.Connection:
    c = connect(tmp_path / "test.db")
    yield c
    c.close()


def _judgment(conn, session_id="s1", left="t1", right="t2", choice="A",
              grader="human", rationale=None, confidence=None,
              position_consistent=None, jid="j1"):
    j = Judgment(
        id=jid, session_id=session_id, task_id="task", model="m",
        left_trial_id=left, right_trial_id=right, choice=choice,
        rubric_correctness=None, rubric_minimality=None,
        rubric_readability=None, rubric_overengineering=None,
        created_at="2026-07-06T00:00:00Z",
        grader=grader, rationale=rationale, confidence=confidence,
        position_consistent=position_consistent,
    )
    insert_judgment(conn, j)
    return j


# ---------------------------------------------------------------------------
# schema + models
# ---------------------------------------------------------------------------

def test_judgment_roundtrips_llm_fields(conn):
    _judgment(conn, grader="llm:mock:mock-judge", rationale="A is tighter.",
              confidence=0.9, position_consistent=True)
    [j] = list_judgments(conn, "s1")
    assert j.grader == "llm:mock:mock-judge"
    assert j.rationale == "A is tighter."
    assert j.confidence == pytest.approx(0.9)
    assert j.position_consistent is True


def test_judgment_defaults_to_human_grader(conn):
    _judgment(conn)
    [j] = list_judgments(conn, "s1")
    assert j.grader == "human"
    assert j.position_consistent is None


def test_grading_session_roundtrips_mode_and_judge_config(conn):
    s = GradingSession(
        id="sess-llm", axis="methodology", cell={"task_id": "task"},
        pairs=[("t1", "t2")], created_at="2026-07-06T00:00:00Z",
        mode="llm", judge_provider="mock", judge_model="mock-judge",
        judge_passes=2,
    )
    insert_grading_session(conn, s)
    got = get_grading_session(conn, "sess-llm")
    assert got.mode == "llm"
    assert got.judge_provider == "mock"
    assert got.judge_model == "mock-judge"
    assert got.judge_passes == 2


def test_grading_session_defaults_to_human_mode(conn):
    s = GradingSession(
        id="sess-h", axis="methodology", cell={"task_id": "task"},
        pairs=[("t1", "t2")], created_at="2026-07-06T00:00:00Z",
    )
    insert_grading_session(conn, s)
    got = get_grading_session(conn, "sess-h")
    assert got.mode == "human"
    assert got.judge_provider is None


def test_legacy_db_backfills_new_columns(tmp_path):
    """A pre-llm-judge DB opens cleanly and its rows read as human-mode."""
    path = tmp_path / "legacy.db"
    raw = sqlite3.connect(str(path))
    raw.executescript("""
        CREATE TABLE grading_session (
            id TEXT PRIMARY KEY, axis TEXT NOT NULL, cell TEXT NOT NULL,
            pairs TEXT NOT NULL, created_at TEXT NOT NULL, revealed_at TEXT
        );
        CREATE TABLE judgment (
            id TEXT PRIMARY KEY, session_id TEXT NOT NULL, task_id TEXT NOT NULL,
            model TEXT NOT NULL, left_trial_id TEXT NOT NULL,
            right_trial_id TEXT NOT NULL, choice TEXT NOT NULL,
            rubric_correctness TEXT, rubric_minimality TEXT,
            rubric_readability TEXT, rubric_overengineering TEXT,
            created_at TEXT NOT NULL
        );
        INSERT INTO grading_session VALUES
            ('old-sess', 'methodology', '{"task_id": "t"}', '[["a","b"]]', '2026-06-01', NULL);
        INSERT INTO judgment VALUES
            ('old-j', 'old-sess', 't', 'm', 'a', 'b', 'A',
             NULL, NULL, NULL, NULL, '2026-06-01');
    """)
    raw.commit()
    raw.close()

    conn = connect(path)
    try:
        got = get_grading_session(conn, "old-sess")
        assert got.mode == "human"
        [j] = list_judgments(conn, "old-sess")
        assert j.grader == "human"
    finally:
        conn.close()


def test_upsert_judgment_replaces_and_keeps_llm_fields(conn):
    _judgment(conn, grader="llm:mock:mock-judge", rationale="first", jid="j1")
    replacement = Judgment(
        id="j2", session_id="s1", task_id="task", model="m",
        left_trial_id="t1", right_trial_id="t2", choice="B",
        rubric_correctness=None, rubric_minimality=None,
        rubric_readability=None, rubric_overengineering=None,
        created_at="2026-07-06T01:00:00Z",
        grader="llm:mock:mock-judge", rationale="second", confidence=0.4,
        position_consistent=False,
    )
    upsert_judgment(conn, replacement)
    rows = list_judgments(conn, "s1")
    assert len(rows) == 1
    assert rows[0].choice == "B"
    assert rows[0].rationale == "second"
    assert rows[0].position_consistent is False


# ---------------------------------------------------------------------------
# judge_call audit table
# ---------------------------------------------------------------------------

def test_judge_call_roundtrip_and_rollup(conn):
    for i, (status, in_tok, out_tok, usd) in enumerate([
        ("ok", 100, 40, 0.001),
        ("ok", 110, 45, 0.001),
        ("parse_error", 90, 30, 0.0009),
    ]):
        insert_judge_call(conn, JudgeCallRecord(
            id=f"c{i}", session_id="s1", pair_index=0, ordering="AB",
            provider="claude-cli", model="claude-haiku-4-5", status=status,
            input_tokens=in_tok, output_tokens=out_tok, usd_equiv=usd,
            wall_seconds=1.5, error=None, created_at="2026-07-06T00:00:00Z",
        ))
    calls = list_judge_calls(conn, "s1")
    assert len(calls) == 3
    assert calls[0].provider == "claude-cli"

    rollup = judge_call_rollup(conn, "s1")
    assert rollup["n_calls"] == 3
    assert rollup["input_tokens"] == 300
    assert rollup["output_tokens"] == 115
    assert rollup["usd_equiv"] == pytest.approx(0.0029)
    assert rollup["n_errors"] == 1


def test_judge_call_rollup_empty_session(conn):
    rollup = judge_call_rollup(conn, "nope")
    assert rollup["n_calls"] == 0
    assert rollup["usd_equiv"] == 0.0


# ---------------------------------------------------------------------------
# grader-filtered Bradley-Terry comparisons
# ---------------------------------------------------------------------------

def _seed_cell(conn):
    for tid, meth in (("t1", "meth-a"), ("t2", "meth-b")):
        insert_trial(conn, Trial(id=tid, task_id="task", methodology_id=meth,
                                 repo_context_id="none", model="m", runner="r", rep=0))
        insert_gate_result(conn, GateResult(trial_id=tid, passed=True))
    for sid, mode in (("s-human", "human"), ("s-llm", "llm")):
        insert_grading_session(conn, GradingSession(
            id=sid, axis="methodology", cell={"task_id": "task"},
            pairs=[("t1", "t2")], created_at="2026-07-06T00:00:00Z", mode=mode,
        ))
    _judgment(conn, session_id="s-human", choice="A", grader="human", jid="jh")
    _judgment(conn, session_id="s-llm", choice="B",
              grader="llm:mock:mock-judge", jid="jl")


def test_comparisons_default_includes_both_graders(conn):
    _seed_cell(conn)
    comparisons, n_judgments, n_sessions = judgments_to_comparisons(conn, "methodology")
    assert n_judgments == 2
    assert n_sessions == 2
    assert sorted(c[2] for c in comparisons) == ["loss", "win"]


def test_comparisons_grader_human_only(conn):
    _seed_cell(conn)
    comparisons, n_judgments, n_sessions = judgments_to_comparisons(
        conn, "methodology", grader="human")
    assert n_judgments == 1
    assert n_sessions == 1
    assert comparisons == [("meth-a", "meth-b", "win")]


def test_comparisons_grader_llm_only(conn):
    _seed_cell(conn)
    comparisons, n_judgments, n_sessions = judgments_to_comparisons(
        conn, "methodology", grader="llm")
    assert n_judgments == 1
    assert comparisons == [("meth-a", "meth-b", "loss")]
