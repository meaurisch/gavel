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


# ---------------------------------------------------------------------------
# grader-filter arithmetic + agreement scoping vs hand counts
# (critic session 2026-07-07)
# ---------------------------------------------------------------------------

def _seed_two_task_cells(conn):
    """Two tasks, meth-a vs meth-b in each. Hand-countable judgment mix:
    task1: human session (A win + tie), llm session (B win)   -> 3 judgments
    task2: llm session (A win)                                -> 1 judgment
    """
    for task in ("task1", "task2"):
        for tid, meth in ((f"{task}-ta", "meth-a"), (f"{task}-tb", "meth-b")):
            insert_trial(conn, Trial(id=tid, task_id=task, methodology_id=meth,
                                     repo_context_id="none", model="m", runner="r", rep=0))
            insert_gate_result(conn, GateResult(trial_id=tid, passed=True))

    insert_grading_session(conn, GradingSession(
        id="h1", axis="methodology", cell={"task_id": "task1"},
        pairs=[("task1-ta", "task1-tb"), ("task1-tb", "task1-ta")],
        created_at="2026-07-07T00:00:00Z", mode="human"))
    _judgment(conn, session_id="h1", left="task1-ta", right="task1-tb",
              choice="A", grader="human", jid="h1a")            # meth-a win
    _judgment(conn, session_id="h1", left="task1-tb", right="task1-ta",
              choice="tie", grader="human", jid="h1b")          # tie

    insert_grading_session(conn, GradingSession(
        id="l1", axis="methodology", cell={"task_id": "task1"},
        pairs=[("task1-ta", "task1-tb")],
        created_at="2026-07-07T01:00:00Z", mode="llm",
        judge_provider="mock", judge_model="mock-judge", judge_passes=2))
    _judgment(conn, session_id="l1", left="task1-ta", right="task1-tb",
              choice="B", grader="llm:mock:mock-judge", jid="l1a")   # meth-b win

    insert_grading_session(conn, GradingSession(
        id="l2", axis="methodology", cell={"task_id": "task2"},
        pairs=[("task2-ta", "task2-tb")],
        created_at="2026-07-07T02:00:00Z", mode="llm",
        judge_provider="mock", judge_model="mock-judge", judge_passes=2))
    _judgment(conn, session_id="l2", left="task2-ta", right="task2-tb",
              choice="A", grader="llm:mock:mock-judge", jid="l2a")   # meth-a win


def test_report_grader_arithmetic_matches_hand_counts(conn):
    from grading.aggregate import build_report

    _seed_two_task_cells(conn)
    everything = build_report(conn, "methodology")
    human = build_report(conn, "methodology", grader="human")
    llm = build_report(conn, "methodology", grader="llm")

    assert (everything.n_judgments, everything.n_sessions) == (4, 3)
    assert (human.n_judgments, human.n_sessions) == (2, 1)
    assert (llm.n_judgments, llm.n_sessions) == (2, 2)

    # per-value comparison counts by hand: every judgment touches both values
    for report, expected in ((everything, 4), (human, 2), (llm, 2)):
        by_value = {s.value: s for s in report.summaries}
        assert by_value["meth-a"].n_comparisons == expected
        assert by_value["meth-b"].n_comparisons == expected

    # cell pin scopes judgments to that task's trials
    pinned = build_report(conn, "methodology", cell={"task_id": "task1"})
    assert (pinned.n_judgments, pinned.n_sessions) == (3, 2)


def test_agreement_scoping_with_cell_pin(conn):
    from grading.aggregate import grader_agreement_report

    _seed_two_task_cells(conn)
    # unscoped: the shared pair is task1's (human A vs llm B -> disagree)
    overall = grader_agreement_report(conn, "methodology")
    assert overall["n_shared"] == 1
    assert overall["n_agree"] == 0

    # pinned to task1: same single shared pair
    task1 = grader_agreement_report(conn, "methodology", {"task_id": "task1"})
    assert task1["n_shared"] == 1

    # pinned to task2: llm judged it, no human did -> nothing shared
    task2 = grader_agreement_report(conn, "methodology", {"task_id": "task2"})
    assert task2["n_shared"] == 0
    assert task2["rate"] is None
