"""HTTP surface of the LLM-judge mode: providers, plan, session lifecycle
with the mock provider, confirm-phrase enforcement, reveal enrichment,
mode separation, and the report grader filter + agreement block."""

import time

import pytest
from fastapi.testclient import TestClient

from core.db import (
    connect,
    insert_gate_result,
    insert_run_result,
    insert_task_spec,
    insert_trial,
)
from core.models import GateResult, RunResult, TaskSpec, Trial
from ui import judge_runs
from ui import server


def _make_diff(methodology_id: str) -> str:
    return (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n+++ b/src/app.py\n"
        "@@ -1,2 +1,3 @@\n def f():\n"
        f"+    return '{methodology_id}'\n"
        " # end\n"
    )


def _seed(conn, trial_id, *, methodology):
    insert_trial(conn, Trial(id=trial_id, task_id="taskx", methodology_id=methodology,
                             repo_context_id="ctxx", model="modelx", runner="runnerx", rep=0))
    insert_run_result(conn, RunResult(
        trial_id=trial_id, diff=_make_diff(methodology), exit_status=0, wall_seconds=3.0))
    insert_gate_result(conn, GateResult(
        trial_id=trial_id, passed=True, compile_passed=True,
        visible_passed=True, hidden_passed=True))


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "results.db"
    conn = connect(db_path)
    insert_task_spec(conn, TaskSpec(
        id="taskx", repo_url="u", base_commit="c",
        instruction="Do the thing.", run_cmd="pytest",
        held_out_tests_path="h", reference_diff_path="r"))
    _seed(conn, "m1", methodology="methalpha")
    _seed(conn, "m2", methodology="methbeta")
    conn.close()
    server.set_db_path(db_path)
    server._sessions.clear()
    judge_runs._runs.clear()
    with TestClient(server.app) as c:
        yield c
    judge_runs._runs.clear()


def _start_and_wait(client, **overrides):
    body = {
        "axis": "methodology", "task": "taskx", "repo_context": "ctxx",
        "model": "modelx", "runner": "runnerx",
        "provider": "mock", "judge_model": "mock-judge", "passes": 2,
    }
    body.update(overrides)
    resp = client.post("/api/judge-sessions", json=body)
    assert resp.status_code == 200, resp.text
    started = resp.json()
    deadline = time.time() + 10
    while time.time() < deadline:
        snap = client.get(f"/api/judge-runs/{started['run_id']}").json()
        if snap["status"] != "running":
            return started, snap
        time.sleep(0.02)
    pytest.fail("judge run did not finish")


# ---------------------------------------------------------------------------
# providers + plan
# ---------------------------------------------------------------------------

def test_providers_lists_all_three_with_billing(client):
    providers = {p["id"]: p for p in client.get("/api/judge/providers").json()}
    assert set(providers) == {"claude-cli", "gh-models", "mock"}
    assert providers["mock"]["billing"] == "free"
    assert providers["mock"]["available"] is True
    assert providers["mock"]["confirm_phrase"] is None
    assert providers["claude-cli"]["billing"] == "subscription"
    assert providers["claude-cli"]["confirm_phrase"] == "JUDGE"
    assert providers["gh-models"]["billing"] == "metered"


def test_plan_endpoint(client):
    resp = client.get("/api/judge/plan", params={
        "axis": "methodology", "task": "taskx", "repo_context": "ctxx",
        "model": "modelx", "runner": "runnerx",
        "provider": "mock", "passes": 2,
    })
    assert resp.status_code == 200, resp.text
    plan = resp.json()
    assert plan["n_pairs"] >= 1
    assert plan["n_calls"] == plan["n_pairs"] * 2
    assert plan["est_usd"] == 0.0


def test_plan_rejects_empty_cell(client):
    resp = client.get("/api/judge/plan", params={
        "axis": "methodology", "task": "nosuchtask", "provider": "mock",
    })
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# lifecycle
# ---------------------------------------------------------------------------

def test_full_judge_session_lifecycle(client):
    started, snap = _start_and_wait(client)
    assert snap["status"] == "done", snap["error"]
    assert snap["n_done"] == snap["n_pairs"]
    assert snap["n_consistent"] == snap["n_pairs"]

    # session shows up as llm-mode with all pairs judged
    sessions = {s["session_id"]: s for s in client.get("/api/sessions").json()}
    s = sessions[started["session_id"]]
    assert s["mode"] == "llm"
    assert s["judge_provider"] == "mock"
    assert s["n_judged"] == s["total_pairs"]

    # events endpoint replays pair events; none leaks an axis value
    events = client.get(f"/api/judge-runs/{started['run_id']}/events")
    text = events.text
    assert '"type": "pair"' in text
    assert "methalpha" not in text and "methbeta" not in text


def test_non_mock_provider_requires_typed_phrase(client):
    resp = client.post("/api/judge-sessions", json={
        "axis": "methodology", "task": "taskx", "repo_context": "ctxx",
        "model": "modelx", "runner": "runnerx",
        "provider": "claude-cli", "judge_model": "claude-haiku-4-5",
    })
    assert resp.status_code == 409
    assert "JUDGE" in resp.json()["detail"]


def test_human_judge_endpoint_refuses_llm_sessions(client):
    started, snap = _start_and_wait(client)
    resp = client.post("/api/judge", json={
        "session_id": started["session_id"], "pair_index": 0, "choice": "A",
    })
    assert resp.status_code == 409
    assert "LLM" in resp.json()["detail"]


def test_reveal_stub_stays_locked_then_enriches_after_confirm(client):
    started, snap = _start_and_wait(client)
    sid = started["session_id"]

    stub = client.get("/api/reveal", params={"session_id": sid}).json()
    assert stub["revealed"] is False
    assert stub["mode"] == "llm"
    assert stub["pairs"] == []
    assert stub["judge_stats"] is None      # nothing cost-shaped while blind

    revealed = client.post("/api/reveal", json={"session_id": sid}).json()
    assert revealed["revealed"] is True
    assert revealed["mode"] == "llm"
    for pair in revealed["pairs"]:
        assert pair["rationale"]
        assert pair["position_consistent"] is True
    stats = revealed["judge_stats"]
    assert stats["provider"] == "mock"
    assert stats["n_calls"] == snap["n_pairs"] * 2
    assert stats["n_consistent"] == snap["n_pairs"]
    assert stats["usd_equiv"] == 0.0


def test_session_payload_carries_mode(client):
    started, _ = _start_and_wait(client)
    data = client.get(f"/api/session/{started['session_id']}").json()
    assert data["mode"] == "llm"
    assert data["judge_model"] == "mock-judge"


def test_for_session_lookup(client):
    started, _ = _start_and_wait(client)
    snap = client.get(f"/api/judge-runs/for-session/{started['session_id']}").json()
    assert snap["session_id"] == started["session_id"]
    assert client.get("/api/judge-runs/for-session/nope").status_code == 404


# ---------------------------------------------------------------------------
# report: grader filter + agreement
# ---------------------------------------------------------------------------

def _human_grade_same_cell(client):
    data = client.get("/api/pairs", params={
        "axis": "methodology", "task": "taskx", "repo_context": "ctxx",
        "model": "modelx", "runner": "runnerx",
    }).json()
    for pair in data["pairs"]:
        resp = client.post("/api/judge", json={
            "session_id": data["session_id"],
            "pair_index": pair["pair_index"],
            "choice": "A",
        })
        assert resp.status_code == 200, resp.text
    return data


def test_report_grader_filter_and_agreement(client):
    _start_and_wait(client)          # llm judgments
    _human_grade_same_cell(client)   # human judgments on the same trials

    everything = client.get("/api/report", params={"axis": "methodology"}).json()
    human_only = client.get("/api/report",
                            params={"axis": "methodology", "grader": "human"}).json()
    llm_only = client.get("/api/report",
                          params={"axis": "methodology", "grader": "llm"}).json()

    assert everything["n_judgments"] == human_only["n_judgments"] + llm_only["n_judgments"]
    assert human_only["grader"] == "human"
    assert llm_only["grader"] == "llm"

    agreement = everything["agreement"]
    assert agreement["n_shared"] >= 1
    assert agreement["rate"] is not None


def test_report_rejects_bad_grader(client):
    resp = client.get("/api/report", params={"axis": "methodology", "grader": "robots"})
    assert resp.status_code == 400
