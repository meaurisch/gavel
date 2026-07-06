"""Adversarial blinding probes for the LLM-judge pipeline.

Every test here builds DB content that actively tries to leak the varying
axis into the judge's view: ids glued into identifiers and paths, ids inside
string literals, ids colliding with English words or with each other, axis
mentions in the task instruction, worktree paths baked into committed
content, and gate scorecards with missing tiers. Assertions run at the two
non-browser layers (the exact prompt handed to the provider, and the SSE
event stream / run snapshots); the rendered-DOM layer lives in
tests/test_ui_playwright.py.

The BlindingError path is probed too: when redaction genuinely cannot hold,
the run must fail closed BEFORE any provider call — and the surfaced error
must not itself name the leaked id (the progress page is a blind surface).
"""

import re
import time
from pathlib import Path

import pytest

from core.db import (
    connect,
    insert_gate_result,
    insert_run_result,
    insert_task_spec,
    insert_trial,
)
from core.models import GateResult, RunResult, TaskSpec, Trial
from grading.judge_providers import MockJudgeProvider
from ui import judge_runs


class RecordingMock(MockJudgeProvider):
    def __init__(self):
        self.prompts = []

    def complete(self, prompt, model):
        self.prompts.append(prompt)
        return super().complete(prompt, model)


@pytest.fixture(autouse=True)
def _reset_runs():
    judge_runs._runs.clear()
    yield
    judge_runs._runs.clear()


def _seed_db(path: Path, *, instruction: str, trials: list[dict]) -> None:
    """trials: [{"id", "methodology", "model", "runner", "ctx", "diff",
    "gate" (optional GateResult kwargs)}]"""
    conn = connect(path)
    insert_task_spec(conn, TaskSpec(
        id="atask", repo_url="u", base_commit="c",
        instruction=instruction, run_cmd="pytest",
        held_out_tests_path="h", reference_diff_path="r",
    ))
    for t in trials:
        insert_trial(conn, Trial(
            id=t["id"], task_id="atask",
            methodology_id=t.get("methodology", "methx"),
            repo_context_id=t.get("ctx", "ctxx"),
            model=t.get("model", "modelx"),
            runner=t.get("runner", "runnerx"),
            rep=t.get("rep", 0),
        ))
        insert_run_result(conn, RunResult(
            trial_id=t["id"], diff=t["diff"], exit_status=0, wall_seconds=1.0,
        ))
        gate = t.get("gate", {})
        insert_gate_result(conn, GateResult(
            trial_id=t["id"], passed=True,
            compile_passed=gate.get("compile_passed", True),
            visible_passed=gate.get("visible_passed", True),
            hidden_passed=gate.get("hidden_passed", True),
        ))
    conn.close()


def _params(axis="methodology", **overrides):
    params = {
        "axis": axis, "task": "atask",
        "provider": "mock", "judge_model": "mock-judge", "passes": 2,
    }
    pinned = {"methodology": "methx", "repo_context": "ctxx",
              "model": "modelx", "runner": "runnerx"}
    pinned.pop({"methodology": "methodology", "model": "model",
                "runner": "runner", "repo_context": "repo_context"}[axis])
    params.update(pinned)
    params.update(overrides)
    return params


def _wait(handle, timeout=10.0):
    deadline = time.time() + timeout
    while handle.status == "running" and time.time() < deadline:
        time.sleep(0.02)
    return handle


def _run(db_path, monkeypatch, *, axis="methodology", **param_overrides):
    recorder = RecordingMock()
    monkeypatch.setattr(judge_runs, "get_provider", lambda pid: recorder)
    handle = judge_runs.start_judge(
        "adv.db", db_path, _params(axis=axis, **param_overrides), confirm_phrase=None)
    _wait(handle)
    return handle, recorder


def _assert_never_appears(needle: str, prompts: list[str]):
    """Case-insensitive whole-string scan — a case-variant of an axis id is
    still that id (redact_axis_ids matches case-insensitively)."""
    for prompt in prompts:
        assert re.search(re.escape(needle), prompt, re.IGNORECASE) is None, (
            f"axis id {needle!r} (some case variant) reached the judge prompt"
        )


# ---------------------------------------------------------------------------
# ids glued into identifiers, paths, and literals
# ---------------------------------------------------------------------------

def _hostile_diff(mid: str) -> str:
    """A diff that smears the methodology id into every channel that must be
    scrubbed: a new-file PATH in the diff header, snake/kebab identifiers,
    JSON string literals, and an absolute worktree path in committed text."""
    return (
        f"diff --git a/src/{mid}_utils.py b/src/{mid}_utils.py\n"
        "new file mode 100644\n"
        "--- /dev/null\n"
        f"+++ b/src/{mid}_utils.py\n"
        "@@ -0,0 +1,6 @@\n"
        f"+# helper written in {mid} style\n"
        f"+{mid}_mode = True\n"
        f"+FLAVOR = \"{mid}-fast\"\n"
        f"+CONFIG = '{{\"approach\": \"{mid}\", \"level\": 3}}'\n"
        "+BUILT_IN = r'C:/Users/x/AppData/Local/Temp/sb-wt-1a2b3c4d/repo'\n"
        "+DONE = 'sb-wt-DEADBEEF placeholder'\n"
    )


def test_ids_in_paths_identifiers_and_literals_are_redacted(tmp_path, monkeypatch):
    db = tmp_path / "adv.db"
    _seed_db(db, instruction="Implement the widget.", trials=[
        {"id": "t1", "methodology": "speedrun", "diff": _hostile_diff("speedrun")},
        {"id": "t2", "methodology": "walkthrough", "diff": _hostile_diff("walkthrough")},
    ])
    handle, recorder = _run(db, monkeypatch)
    assert handle.status == "done", handle.error
    assert recorder.prompts
    for mid in ("speedrun", "walkthrough"):
        _assert_never_appears(mid, recorder.prompts)
    for prompt in recorder.prompts:
        assert "[methodology]" in prompt          # redaction token, not deletion
        assert "sb-wt-1a2b3c4d" not in prompt      # worktree hash scrubbed
        assert "sb-wt-DEADBEEF" not in prompt
        assert "sb-wt-[redacted]" in prompt


def test_ids_that_are_substrings_of_each_other_and_english_words(tmp_path, monkeypatch):
    """id "plain" vs id "plain-plus": longest-first redaction; the English
    word "explain" must survive (letters are the token boundary)."""
    diff_a = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -0,0 +1,3 @@\n"
        "+style = 'plain'\n"
        "+# we explain the approach here\n"
        "+mode = 'plain-plus'\n"
    )
    diff_b = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -0,0 +1,2 @@\n"
        "+style = 'plain-plus'\n"
        "+note = 'plainly better'\n"
    )
    db = tmp_path / "adv.db"
    _seed_db(db, instruction="Implement the widget.", trials=[
        {"id": "t1", "methodology": "plain", "diff": diff_a},
        {"id": "t2", "methodology": "plain-plus", "diff": diff_b},
    ])
    handle, recorder = _run(db, monkeypatch)
    assert handle.status == "done", handle.error
    for prompt in recorder.prompts:
        # every whole-token occurrence of either id is gone
        assert re.search(r"(?<![A-Za-z0-9])plain(?![A-Za-z0-9])", prompt) is None
        assert "plain-plus" not in prompt
        # english words that merely contain an id are untouched
        if "explain the approach" in prompt or "plainly better" in prompt:
            pass
    joined = "\n".join(recorder.prompts)
    assert "explain the approach" in joined
    assert "plainly better" in joined


@pytest.mark.parametrize("axis,field,values", [
    ("model", "model", ["claude-haiku-4-5", "gpt-5-mini"]),
    ("runner", "runner", ["claude-code", "aider"]),
])
def test_model_and_runner_axes_are_blind_too(tmp_path, monkeypatch, axis, field, values):
    """An agent that signs its work ("Generated by <model> via <runner>")
    must not deblind a model- or runner-axis session."""
    def diff(v):
        return (
            "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -0,0 +1,2 @@\n"
            f"+# Generated by {v}\n"
            f"+AGENT = \"{v}\"\n"
        )
    db = tmp_path / "adv.db"
    _seed_db(db, instruction="Implement the widget.", trials=[
        {"id": f"t{i}", field: v, "diff": diff(v)} for i, v in enumerate(values)
    ])
    handle, recorder = _run(db, monkeypatch, axis=axis)
    assert handle.status == "done", handle.error
    assert recorder.prompts
    for v in values:
        _assert_never_appears(v, recorder.prompts)
    token = {"model": "[model]", "runner": "[runner]"}[axis]
    assert all(token in p for p in recorder.prompts)


# ---------------------------------------------------------------------------
# the task instruction is part of the judge's view — redact it like a diff
# ---------------------------------------------------------------------------

def test_instruction_mentioning_axis_ids_is_redacted_in_any_case(tmp_path, monkeypatch):
    """A task instruction that names a contender id — in ANY case variant —
    must not carry it to the provider, and must not kill the run either
    (mentions are legitimate content; they get the same redaction diffs do)."""
    db = tmp_path / "adv.db"
    _seed_db(
        db,
        instruction=(
            "Implement caching. The speedrun module is a good reference; "
            "compare with the SPEEDRUN benchmark and the Walkthrough doc."
        ),
        trials=[
            {"id": "t1", "methodology": "speedrun", "diff": _hostile_diff("speedrun")},
            {"id": "t2", "methodology": "walkthrough", "diff": _hostile_diff("walkthrough")},
        ],
    )
    handle, recorder = _run(db, monkeypatch)
    assert handle.status == "done", handle.error
    assert recorder.prompts
    for mid in ("speedrun", "walkthrough"):
        _assert_never_appears(mid, recorder.prompts)
    # the instruction itself still made it in (redacted, not dropped)
    assert all("Implement caching." in p for p in recorder.prompts)


def test_instruction_mentioning_pinned_id_does_not_kill_the_run(tmp_path, monkeypatch):
    """Real tasks routinely name their pinned repo context (e.g. "the cosmos
    codebase"). That must not fail the run — pinned mentions are redacted
    like everything else."""
    diff = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -0,0 +1,1 @@\n+x = 1\n"
    )
    db = tmp_path / "adv.db"
    _seed_db(
        db,
        instruction="Add the aggregate to the cosmos codebase.",
        trials=[
            {"id": "t1", "methodology": "m-one", "ctx": "cosmos", "diff": diff},
            {"id": "t2", "methodology": "m-two", "ctx": "cosmos", "diff": diff + "+y = 2\n"},
        ],
    )
    handle, recorder = _run(db, monkeypatch, repo_context="cosmos")
    assert handle.status == "done", handle.error
    _assert_never_appears("cosmos", recorder.prompts)


# ---------------------------------------------------------------------------
# fail-closed: BlindingError before any provider call, with a clean message
# ---------------------------------------------------------------------------

def test_blinding_failure_fails_closed_and_names_no_ids(tmp_path, monkeypatch):
    """Simulate a redaction regression (anonymize_diff becomes a no-op): the
    run must error BEFORE any provider call, and the surfaced error — which
    the blind progress page renders — must not contain the leaked id."""
    db = tmp_path / "adv.db"
    _seed_db(db, instruction="Implement the widget.", trials=[
        {"id": "t1", "methodology": "speedrun", "diff": _hostile_diff("speedrun")},
        {"id": "t2", "methodology": "walkthrough", "diff": _hostile_diff("walkthrough")},
    ])
    monkeypatch.setattr(judge_runs, "anonymize_diff", lambda diff, ids: diff)
    handle, recorder = _run(db, monkeypatch)
    assert handle.status == "error"
    assert recorder.prompts == [], "a provider call happened despite a blinding failure"
    surfaced = (handle.error or "") + str(handle.events)
    assert "blind" in (handle.error or "").lower()   # the error says WHY, clearly
    for mid in ("speedrun", "walkthrough"):
        assert re.search(re.escape(mid), surfaced, re.IGNORECASE) is None, (
            f"the blinding-failure error itself leaked {mid!r} onto a blind surface"
        )


# ---------------------------------------------------------------------------
# gate scorecards with missing tiers
# ---------------------------------------------------------------------------

def test_gate_scorecard_with_missing_tiers_serves_na_not_crash(tmp_path, monkeypatch):
    db = tmp_path / "adv.db"
    diff = (
        "diff --git a/a.py b/a.py\n--- a/a.py\n+++ b/a.py\n@@ -0,0 +1,1 @@\n+x = 1\n"
    )
    _seed_db(db, instruction="Implement the widget.", trials=[
        {"id": "t1", "methodology": "m-one", "diff": diff,
         "gate": {"compile_passed": None, "visible_passed": None, "hidden_passed": True}},
        {"id": "t2", "methodology": "m-two", "diff": diff + "+y = 2\n",
         "gate": {"visible_passed": False}},
    ])
    handle, recorder = _run(db, monkeypatch)
    assert handle.status == "done", handle.error
    joined = "\n".join(recorder.prompts)
    assert "compile=n/a" in joined
    assert "visible tests=n/a" in joined
    assert "visible tests=fail" in joined


# ---------------------------------------------------------------------------
# SSE layer: the event stream a browser receives is as blind as the prompts
# ---------------------------------------------------------------------------

def test_sse_stream_and_snapshots_leak_no_axis_values(tmp_path, monkeypatch):
    from fastapi.testclient import TestClient
    from ui import server

    db = tmp_path / "results.db"
    _seed_db(db, instruction="Implement the widget.", trials=[
        {"id": "t1", "methodology": "speedrun", "diff": _hostile_diff("speedrun")},
        {"id": "t2", "methodology": "walkthrough", "diff": _hostile_diff("walkthrough")},
    ])
    server.set_db_path(db)
    server._sessions.clear()
    with TestClient(server.app) as client:
        resp = client.post("/api/judge-sessions", json={
            "axis": "methodology", "task": "atask", "repo_context": "ctxx",
            "model": "modelx", "runner": "runnerx",
            "provider": "mock", "judge_model": "mock-judge", "passes": 2,
        })
        assert resp.status_code == 200, resp.text
        run_id = resp.json()["run_id"]
        deadline = time.time() + 10
        while time.time() < deadline:
            snap = client.get(f"/api/judge-runs/{run_id}").json()
            if snap["status"] != "running":
                break
            time.sleep(0.02)
        assert snap["status"] == "done", snap.get("error")

        stream = client.get(f"/api/judge-runs/{run_id}/events").text
        listing = str(client.get("/api/judge-runs").json())
        for_session = str(client.get(
            f"/api/judge-runs/for-session/{snap['session_id']}").json())
        for surface in (str(snap), stream, listing, for_session):
            for mid in ("speedrun", "walkthrough"):
                assert re.search(re.escape(mid), surface, re.IGNORECASE) is None, (
                    f"axis id {mid!r} leaked into a blind judge-run surface"
                )
