"""ui.judge_runs — planning, spend confirmation, the background judging
worker, resume, and the blinding of everything a judge provider sees."""

import time
from pathlib import Path

import pytest

from core.db import (
    connect,
    get_grading_session,
    insert_gate_result,
    insert_grading_session,
    insert_judgment,
    insert_run_result,
    insert_task_spec,
    insert_trial,
    list_judge_calls,
    list_judgments,
    mark_session_revealed,
)
from core.models import GateResult, GradingSession, Judgment, RunResult, TaskSpec, Trial
from grading.judge_providers import MockJudgeProvider
from ui import judge_runs


def _diff(marker: str) -> str:
    return (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n+++ b/src/app.py\n"
        "@@ -1,0 +1,2 @@\n"
        f"+change_{marker} = 1\n"
        f"+built_by = 'meth-{marker}'\n"
    )


@pytest.fixture()
def seeded_db(tmp_path: Path):
    path = tmp_path / "judge.db"
    conn = connect(path)
    insert_task_spec(conn, TaskSpec(
        id="taskone", repo_url="u", base_commit="c",
        instruction="Implement the frobnicator.", run_cmd="pytest",
        held_out_tests_path="h", reference_diff_path="r",
    ))
    for marker in ("a", "b"):
        tid = f"trial-{marker}"
        insert_trial(conn, Trial(
            id=tid, task_id="taskone", methodology_id=f"meth-{marker}",
            repo_context_id="ctxone", model="modelone", runner="runnerone", rep=0,
        ))
        insert_run_result(conn, RunResult(
            trial_id=tid, diff=_diff(marker), exit_status=0, wall_seconds=1.0,
        ))
        insert_gate_result(conn, GateResult(
            trial_id=tid, passed=True,
            compile_passed=True, visible_passed=True, hidden_passed=True,
        ))
    conn.close()
    return path


@pytest.fixture(autouse=True)
def _reset_runs():
    judge_runs._runs.clear()
    yield
    judge_runs._runs.clear()


class RecordingMock(MockJudgeProvider):
    def __init__(self):
        self.prompts = []

    def complete(self, prompt, model):
        self.prompts.append(prompt)
        return super().complete(prompt, model)


def _params(**overrides):
    params = {
        "axis": "methodology",
        "task": "taskone",
        "repo_context": "ctxone",
        "model": "modelone",
        "runner": "runnerone",
        "provider": "mock",
        "judge_model": "mock-judge",
        "passes": 2,
    }
    params.update(overrides)
    return params


def _wait(handle, timeout=10.0):
    deadline = time.time() + timeout
    while handle.status == "running" and time.time() < deadline:
        time.sleep(0.02)
    return handle


# ---------------------------------------------------------------------------
# plan
# ---------------------------------------------------------------------------

def test_plan_reports_pairs_calls_and_estimate(seeded_db):
    conn = connect(seeded_db)
    try:
        plan = judge_runs.plan_judge(conn, _params())
    finally:
        conn.close()
    assert plan["n_pairs"] >= 1
    assert plan["n_calls"] == plan["n_pairs"] * 2
    assert plan["est_input_tokens"] > 0
    assert plan["billing"] == "free"
    assert plan["available"] is True
    assert plan["confirm_phrase"] is None            # mock never needs a phrase


def test_plan_single_pass_halves_calls(seeded_db):
    conn = connect(seeded_db)
    try:
        two = judge_runs.plan_judge(conn, _params(passes=2))
        one = judge_runs.plan_judge(conn, _params(passes=1))
    finally:
        conn.close()
    assert one["n_calls"] == two["n_calls"] // 2


def test_plan_non_mock_provider_requires_confirm_phrase(seeded_db):
    conn = connect(seeded_db)
    try:
        plan = judge_runs.plan_judge(conn, _params(provider="claude-cli",
                                                   judge_model="claude-haiku-4-5"))
    finally:
        conn.close()
    assert plan["confirm_phrase"] == judge_runs.CONFIRM_PHRASE


def test_plan_rejects_unknown_axis(seeded_db):
    conn = connect(seeded_db)
    try:
        with pytest.raises(judge_runs.JudgeRequestError):
            judge_runs.plan_judge(conn, _params(axis="bogus"))
    finally:
        conn.close()


# ---------------------------------------------------------------------------
# start + worker
# ---------------------------------------------------------------------------

def test_start_judges_every_pair_and_persists(seeded_db, monkeypatch):
    recorder = RecordingMock()
    monkeypatch.setattr(judge_runs, "get_provider", lambda pid: recorder)

    handle = judge_runs.start_judge("judge.db", seeded_db, _params(), confirm_phrase=None)
    _wait(handle)
    assert handle.status == "done", handle.error

    conn = connect(seeded_db)
    try:
        session = get_grading_session(conn, handle.session_id)
        assert session.mode == "llm"
        assert session.judge_provider == "mock"
        assert session.judge_passes == 2
        judgments = list_judgments(conn, handle.session_id)
        assert len(judgments) == len(session.pairs)
        assert all(j.grader == "llm:mock:mock-judge" for j in judgments)
        assert all(j.rationale for j in judgments)
        assert all(j.position_consistent is True for j in judgments)
        calls = list_judge_calls(conn, handle.session_id)
        assert len(calls) == 2 * len(session.pairs)
    finally:
        conn.close()

    # progress events: one per pair plus a final status event
    types = [e["type"] for e in handle.events]
    assert types.count("pair") == len(session.pairs)
    assert types[-1] == "status"


def test_judge_prompts_are_blind(seeded_db, monkeypatch):
    """The provider must never see raw axis ids — diffs are anonymized and
    the forbidden-token check backs that up."""
    recorder = RecordingMock()
    monkeypatch.setattr(judge_runs, "get_provider", lambda pid: recorder)

    handle = judge_runs.start_judge("judge.db", seeded_db, _params(), confirm_phrase=None)
    _wait(handle)
    assert handle.status == "done", handle.error
    assert recorder.prompts
    for prompt in recorder.prompts:
        for raw_id in ("meth-a", "meth-b"):
            assert raw_id not in prompt
        assert "[methodology]" in prompt
        assert "Implement the frobnicator." in prompt


def test_pair_events_expose_letters_but_never_axis_values(seeded_db, monkeypatch):
    recorder = RecordingMock()
    monkeypatch.setattr(judge_runs, "get_provider", lambda pid: recorder)
    handle = judge_runs.start_judge("judge.db", seeded_db, _params(), confirm_phrase=None)
    _wait(handle)
    for event in handle.events:
        if event["type"] != "pair":
            continue
        assert event["choice"] in ("A", "B", "tie")
        blob = str(event)
        assert "meth-a" not in blob and "meth-b" not in blob


def test_start_requires_confirm_phrase_for_non_mock(seeded_db):
    with pytest.raises(judge_runs.JudgeRequestError) as exc:
        judge_runs.start_judge(
            "judge.db", seeded_db,
            _params(provider="claude-cli", judge_model="claude-haiku-4-5"),
            confirm_phrase=None,
        )
    assert exc.value.status == 409


def test_start_refuses_second_concurrent_run(seeded_db, monkeypatch):
    slow = RecordingMock()
    orig = slow.complete

    def slow_complete(prompt, model):
        time.sleep(0.3)
        return orig(prompt, model)

    slow.complete = slow_complete
    monkeypatch.setattr(judge_runs, "get_provider", lambda pid: slow)

    handle = judge_runs.start_judge("judge.db", seeded_db, _params(), confirm_phrase=None)
    try:
        with pytest.raises(judge_runs.JudgeRequestError) as exc:
            judge_runs.start_judge("judge.db", seeded_db, _params(), confirm_phrase=None)
        assert exc.value.status == 409
    finally:
        _wait(handle)


def test_resume_skips_already_judged_pairs(seeded_db, monkeypatch):
    recorder = RecordingMock()
    monkeypatch.setattr(judge_runs, "get_provider", lambda pid: recorder)

    conn = connect(seeded_db)
    session = GradingSession(
        id="resume-me", axis="methodology",
        cell={"task_id": "taskone", "repo_context_id": "ctxone",
              "model": "modelone", "runner": "runnerone"},
        pairs=[("trial-a", "trial-b"), ("trial-b", "trial-a")],
        created_at="2026-07-06T00:00:00Z",
        mode="llm", judge_provider="mock", judge_model="mock-judge", judge_passes=1,
    )
    insert_grading_session(conn, session)
    insert_judgment(conn, Judgment(
        id="pre", session_id="resume-me", task_id="taskone", model="modelone",
        left_trial_id="trial-a", right_trial_id="trial-b", choice="A",
        rubric_correctness=None, rubric_minimality=None,
        rubric_readability=None, rubric_overengineering=None,
        created_at="2026-07-06T00:00:00Z", grader="llm:mock:mock-judge",
    ))
    conn.close()

    handle = judge_runs.start_judge(
        "judge.db", seeded_db, {"session_id": "resume-me", "passes": 1},
        confirm_phrase=None,
    )
    _wait(handle)
    assert handle.status == "done", handle.error
    assert sum(1 for e in handle.events if e["type"] == "pair") == 1

    conn = connect(seeded_db)
    try:
        assert len(list_judgments(conn, "resume-me")) == 2
    finally:
        conn.close()


def test_resume_refuses_revealed_session(seeded_db):
    conn = connect(seeded_db)
    insert_grading_session(conn, GradingSession(
        id="revealed", axis="methodology", cell={"task_id": "taskone"},
        pairs=[("trial-a", "trial-b")], created_at="2026-07-06T00:00:00Z",
        mode="llm", judge_provider="mock", judge_model="mock-judge", judge_passes=1,
    ))
    mark_session_revealed(conn, "revealed", "2026-07-06T01:00:00Z")
    conn.close()

    with pytest.raises(judge_runs.JudgeRequestError) as exc:
        judge_runs.start_judge("judge.db", seeded_db,
                               {"session_id": "revealed"}, confirm_phrase=None)
    assert exc.value.status == 409


def test_resume_refuses_human_session(seeded_db):
    conn = connect(seeded_db)
    insert_grading_session(conn, GradingSession(
        id="human-sess", axis="methodology", cell={"task_id": "taskone"},
        pairs=[("trial-a", "trial-b")], created_at="2026-07-06T00:00:00Z",
    ))
    conn.close()
    with pytest.raises(judge_runs.JudgeRequestError):
        judge_runs.start_judge("judge.db", seeded_db,
                               {"session_id": "human-sess"}, confirm_phrase=None)
