"""Tests for the phase-1 UI backend additions: catalog, db listing, session
resume, gate detail + metrics blinding, originals, report JSON, run launcher.
"""

import time

import pytest
from fastapi.testclient import TestClient

from core.db import (
    connect,
    insert_cost_record,
    insert_gate_result,
    insert_run_result,
    insert_trial,
)
from core.models import CostRecord, GateResult, RunResult, Trial
from ui import server
from ui import runs as run_manager


def _make_diff(methodology_id: str, path: str = "src/app.py") -> str:
    return (
        f"diff --git a/{path} b/{path}\n"
        f"--- a/{path}\n"
        f"+++ b/{path}\n"
        "@@ -1,2 +1,3 @@\n"
        " def f():\n"
        f"+    return '{methodology_id}'\n"
        " # end\n"
    )


def _seed(conn, trial_id, *, task="taskx", methodology="methx", ctx="ctxx",
          model="modelx", runner="runnerx", rep=0, passed=True,
          diff=None, gate_outputs=True, cost=True):
    insert_trial(conn, Trial(id=trial_id, task_id=task, methodology_id=methodology,
                             repo_context_id=ctx, model=model, runner=runner, rep=rep))
    insert_run_result(conn, RunResult(
        trial_id=trial_id,
        diff=diff if diff is not None else _make_diff(methodology),
        exit_status=0, wall_seconds=12.5,
    ))
    outputs = {}
    if gate_outputs:
        outputs = dict(
            compile_output=f"building for {methodology} on {model} ok",
            visible_output=f"3 passed ({methodology})",
            hidden_output=f"5 passed, log mentions {model} and {runner}",
        )
    insert_gate_result(conn, GateResult(
        trial_id=trial_id, passed=passed, compile_passed=True,
        visible_passed=True, hidden_passed=passed, **outputs,
    ))
    if cost:
        insert_cost_record(conn, CostRecord(
            trial_id=trial_id, native_unit="usd", native_amount=0.5, usd_equiv=0.5,
            input_tokens=1000, output_tokens=200, cache_read_tokens=50,
        ))


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "results.db"
    conn = connect(db_path)
    # Methodology-axis gradeable cell (2 methodologies).
    _seed(conn, "m1", methodology="methalpha")
    _seed(conn, "m2", methodology="methbeta")
    # Model-axis gradeable cell (2 models) on a second task.
    _seed(conn, "d1", task="tasky", model="modelalpha")
    _seed(conn, "d2", task="tasky", model="modelbeta")
    conn.close()
    server.set_db_path(db_path)
    server._sessions.clear()
    with TestClient(server.app) as c:
        yield c


def _start_session(client, axis="methodology", task="taskx", **pins):
    params = {"axis": axis, "task": task,
              "repo_context": "ctxx", "model": "modelx", "runner": "runnerx",
              "methodology": "methx", **pins}
    if axis in params:
        del params[axis]
    resp = client.get("/api/pairs", params=params)
    assert resp.status_code == 200, resp.text
    return resp.json()


# ---------------------------------------------------------------------------
# Gate detail + metrics blinding
# ---------------------------------------------------------------------------

def test_gate_detail_logs_served_and_redacted(client):
    data = _start_session(client, axis="methodology")
    side = data["pairs"][0]["left"]
    detail = side["gate_detail"]
    assert detail["passed"] is True
    for tier in ("compile", "visible", "hidden"):
        assert detail[tier]["output"], f"{tier} log missing"
    all_logs = "".join(detail[t]["output"] for t in ("compile", "visible", "hidden"))
    assert "methalpha" not in all_logs
    assert "methbeta" not in all_logs
    assert "[methodology]" in all_logs


def test_blind_logs_scrub_worktree_hashes(tmp_path):
    """Worktree temp hashes are per-trial identifiers joinable against the
    unblinded Browse surface — blind-served logs must scrub them (the raw
    trial-detail endpoint keeps them)."""
    db_path = tmp_path / "wt.db"
    conn = connect(db_path)
    for tid, meth, wt in (("w1", "methone", "sb-wt-aabbcc112233"), ("w2", "methtwo", "sb-wt-ddeeff445566")):
        insert_trial(conn, Trial(id=tid, task_id="t", methodology_id=meth,
                                 repo_context_id="c", model="m", runner="r", rep=0))
        # the agent baked its worktree path into committed content too
        diff = _make_diff(meth).replace("def f():", f"def f():  # built in C:/Temp/{wt}")
        insert_run_result(conn, RunResult(trial_id=tid, diff=diff,
                                          exit_status=0, wall_seconds=1.0))
        insert_gate_result(conn, GateResult(
            trial_id=tid, passed=True, hidden_passed=True,
            hidden_output=(
                f"building in C:\\Temp\\{wt}\\src ... ok\n"
                "Time Elapsed 00:00:01.14\nPassed! - Duration: 1.234 s\n"
                "Passed! - Total: 1, Duration: < 1 ms - Tests.dll"
            ),
        ))
    conn.close()
    server.set_db_path(db_path)
    server._sessions.clear()
    with TestClient(server.app) as c:
        data = c.get("/api/pairs", params={
            "axis": "methodology", "task": "t", "repo_context": "c",
            "model": "m", "runner": "r",
        }).json()
        for pair in data["pairs"]:
            for side in ("left", "right"):
                log = pair[side]["gate_detail"]["hidden"]["output"]
                assert "aabbcc112233" not in log and "ddeeff445566" not in log
                assert "sb-wt-[redacted]" in log
                # machine-timing lines join exactly against raw Browse logs
                assert "00:00:01.14" not in log and "1.234" not in log
                assert "< 1 ms" not in log  # the dotnet sub-millisecond form too
                # the DIFF is scrubbed too — redact_axis_ids owns the rule now
                assert "aabbcc112233" not in pair[side]["diff"]
                assert "ddeeff445566" not in pair[side]["diff"]
        # The unblinded trial detail keeps the raw path.
        raw = c.get("/api/trials/w1").json()["gate_result"]["hidden_output"]
        assert "sb-wt-aabbcc112233" in raw


@pytest.mark.parametrize("axis,task", [("methodology", "taskx"), ("model", "tasky")])
def test_no_spend_metrics_during_blind_judging(client, axis, task):
    """Cost/tokens/time bias blind judgment (user decision 2026-07-05):
    pair payloads carry no metrics on ANY axis — they belong to Reveal,
    Browse, and Report."""
    data = _start_session(client, axis=axis, task=task)
    for pair in data["pairs"]:
        for side in ("left", "right"):
            assert pair[side]["metrics"] is None  # populated only after reveal
        blob = str(pair)
        assert "0.5" not in blob or "usd" not in blob  # no spend values anywhere


def test_proxy_computed_on_anonymized_diff(tmp_path):
    """The diff-shape proxy (file list, counts) must describe what the grader
    SEES: instruction files stripped, axis ids in filenames redacted."""
    db_path = tmp_path / "proxy.db"
    conn = connect(db_path)
    for tid, meth in (("p1", "methredone"), ("p2", "methredtwo")):
        diff = (
            f"diff --git a/{meth}_helper.py b/{meth}_helper.py\n"
            f"--- a/{meth}_helper.py\n"
            f"+++ b/{meth}_helper.py\n"
            "@@ -1,1 +1,2 @@\n"
            " x = 1\n"
            "+y = 2\n"
            "diff --git a/CLAUDE.md b/CLAUDE.md\n"
            "--- /dev/null\n"
            "+++ b/CLAUDE.md\n"
            "@@ -0,0 +1,1 @@\n"
            "+instructions here\n"
        )
        _seed(conn, tid, task="tp", methodology=meth, diff=diff)
    conn.close()
    server.set_db_path(db_path)
    server._sessions.clear()
    with TestClient(server.app) as c:
        data = c.get("/api/pairs", params={
            "axis": "methodology", "task": "tp", "repo_context": "ctxx",
            "model": "modelx", "runner": "runnerx",
        }).json()
        for pair in data["pairs"]:
            for side in ("left", "right"):
                proxy = pair[side]["proxy"]
                assert "CLAUDE.md" not in proxy["file_list"], "instruction file leaked into proxy"
                for f in proxy["file_list"]:
                    assert "methredone" not in f and "methredtwo" not in f, "axis id leaked via filename"
                assert proxy["files_touched"] == 1  # only the visible file counts


def test_gate_detail_redacts_model_ids_on_model_axis(client):
    data = _start_session(client, axis="model", task="tasky")
    for pair in data["pairs"]:
        for side in (pair["left"], pair["right"]):
            blob = str(side)
            assert "modelalpha" not in blob
            assert "modelbeta" not in blob


def test_tier_output_truncated(tmp_path):
    db_path = tmp_path / "big.db"
    conn = connect(db_path)
    big = "x" * (server.TIER_OUTPUT_CAP + 5000)
    for tid, meth in (("b1", "meth1"), ("b2", "meth2")):
        insert_trial(conn, Trial(id=tid, task_id="t", methodology_id=meth,
                                 repo_context_id="c", model="m", runner="r", rep=0))
        insert_run_result(conn, RunResult(trial_id=tid, diff=_make_diff(meth),
                                          exit_status=0, wall_seconds=1.0))
        insert_gate_result(conn, GateResult(trial_id=tid, passed=True,
                                            hidden_passed=True, hidden_output=big))
    conn.close()
    server.set_db_path(db_path)
    with TestClient(server.app) as c:
        data = c.get("/api/pairs", params={
            "axis": "methodology", "task": "t", "repo_context": "c",
            "model": "m", "runner": "r",
        }).json()
        hidden = data["pairs"][0]["left"]["gate_detail"]["hidden"]
        assert hidden["truncated"] is True
        assert len(hidden["output"]) <= server.TIER_OUTPUT_CAP + 100
        assert "[truncated" in hidden["output"]


# ---------------------------------------------------------------------------
# Session resume
# ---------------------------------------------------------------------------

def test_session_resume_returns_pairs_and_judgments(client):
    data = _start_session(client, axis="methodology")
    sid = data["session_id"]
    client.post("/api/judge", json={"session_id": sid, "pair_index": 0, "choice": "B"})

    # Simulate restart: in-memory cache gone.
    server._sessions.clear()

    resp = client.get(f"/api/session/{sid}")
    assert resp.status_code == 200
    body = resp.json()
    assert body["session_id"] == sid
    assert body["total_pairs"] == data["total_pairs"]
    assert len(body["pairs"]) == body["total_pairs"]
    assert body["judged"] == [{"pair_index": 0, "choice": "B"}]
    # Rebuilt payloads stay blind.
    blob = str(body["pairs"])
    assert "methalpha" not in blob
    assert "methbeta" not in blob


def test_sessions_list_shows_progress(client):
    data = _start_session(client, axis="methodology")
    sid = data["session_id"]
    client.post("/api/judge", json={"session_id": sid, "pair_index": 0, "choice": "A"})

    resp = client.get("/api/sessions")
    assert resp.status_code == 200
    sessions = {s["session_id"]: s for s in resp.json()}
    assert sid in sessions
    assert sessions[sid]["n_judged"] == 1
    assert sessions[sid]["total_pairs"] == data["total_pairs"]
    assert sessions[sid]["axis"] == "methodology"


def test_session_404_for_unknown(client):
    assert client.get("/api/session/nope").status_code == 404


# ---------------------------------------------------------------------------
# Reveal closes the session (blind-grading invariant)
# ---------------------------------------------------------------------------

def test_reveal_closes_session_and_hides_unjudged_pairs(client):
    data = _start_session(client, axis="methodology")
    sid = data["session_id"]
    total = data["total_pairs"]
    client.post("/api/judge", json={"session_id": sid, "pair_index": 0, "choice": "A"})

    # A bare GET must NOT close the session and must not unblind anything —
    # it returns a locked stub, and judging still works afterward.
    locked = client.get("/api/reveal", params={"session_id": sid})
    assert locked.status_code == 200
    stub = locked.json()
    assert stub["revealed"] is False
    assert stub["pairs"] == []
    assert stub["n_judged"] == 1
    assert "methalpha" not in locked.text and "methbeta" not in locked.text
    # Re-judging (upsert) still works — the GET did not close the session.
    still_open = client.post("/api/judge", json={"session_id": sid, "pair_index": 0, "choice": "tie"})
    assert still_open.status_code == 200, "GET /api/reveal must not close the session"

    # The explicit POST is what closes it.
    rev = client.post("/api/reveal", json={"session_id": sid})
    assert rev.status_code == 200
    body = rev.json()
    assert body["revealed"] is True
    # Only judged pairs are unblinded (latest judgment wins).
    assert len(body["pairs"]) == 1
    assert body["pairs"][0]["choice"] == "tie"
    assert body["n_unjudged"] == total - 1
    assert body["revealed_at"] is not None

    # Judging after reveal is refused — including re-judging the judged pair.
    resp = client.post("/api/judge", json={"session_id": sid, "pair_index": 0, "choice": "B"})
    assert resp.status_code == 409, "judgment accepted after reveal"
    assert "closed" in resp.json()["detail"]

    # The closure is persisted, not in-memory: survive a "restart".
    server._sessions.clear()
    resp = client.post("/api/judge", json={"session_id": sid, "pair_index": 1, "choice": "A"})
    assert resp.status_code == 409

    # The session payload and listing both carry the closed state.
    assert client.get(f"/api/session/{sid}").json()["revealed_at"] is not None
    listed = {s["session_id"]: s for s in client.get("/api/sessions").json()}
    assert listed[sid]["revealed_at"] is not None


def test_reveal_refused_with_zero_judgments(client):
    """Reveal must not double as a pointless-destruction endpoint: a session
    with nothing judged has no verdict to reveal."""
    data = _start_session(client, axis="methodology")
    sid = data["session_id"]
    resp = client.post("/api/reveal", json={"session_id": sid})
    assert resp.status_code == 409
    assert "no verdict" in resp.json()["detail"].lower() or "nothing" in resp.json()["detail"].lower()
    # The session is untouched and still judgeable.
    ok = client.post("/api/judge", json={"session_id": sid, "pair_index": 0, "choice": "A"})
    assert ok.status_code == 200


def test_revealed_session_payload_includes_metrics(client):
    """Blind sessions carry no spend metrics; once revealed (closed, values
    public) the session payload includes them — honoring the UI's "they
    appear after reveal" promise."""
    data = _start_session(client, axis="methodology")
    sid = data["session_id"]
    assert data["pairs"][0]["left"]["metrics"] is None  # blind

    client.post("/api/judge", json={"session_id": sid, "pair_index": 0, "choice": "A"})
    client.post("/api/reveal", json={"session_id": sid})

    body = client.get(f"/api/session/{sid}").json()
    m = body["pairs"][0]["left"]["metrics"]
    assert m is not None
    assert m["usd"] == 0.5
    assert m["input_tokens"] == 1000
    assert m["wall_seconds"] == 12.5


def test_reveal_timestamp_stable_across_loads(client):
    data = _start_session(client, axis="methodology")
    sid = data["session_id"]
    client.post("/api/judge", json={"session_id": sid, "pair_index": 0, "choice": "tie"})
    first = client.post("/api/reveal", json={"session_id": sid}).json()["revealed_at"]
    # Re-POST is idempotent, and a later GET reads the same closed state.
    second = client.post("/api/reveal", json={"session_id": sid}).json()["revealed_at"]
    third = client.get("/api/reveal", params={"session_id": sid}).json()["revealed_at"]
    assert first == second == third


# ---------------------------------------------------------------------------
# Originals
# ---------------------------------------------------------------------------

def test_pair_originals_new_file_and_blinding(tmp_path):
    """Diffs creating new files -> original status 'new'; nothing about the
    varying axis leaks through paths or note."""
    db_path = tmp_path / "orig.db"
    conn = connect(db_path)
    for tid, meth in (("o1", "methone"), ("o2", "methtwo")):
        diff = (
            f"diff --git a/{meth}_helper.py b/{meth}_helper.py\n"
            "new file mode 100644\n"
            "--- /dev/null\n"
            f"+++ b/{meth}_helper.py\n"
            "@@ -0,0 +1,1 @@\n"
            f"+print('{meth}')\n"
        )
        _seed(conn, tid, task="demo-task", methodology=meth, diff=diff)
    conn.close()
    server.set_db_path(db_path)
    server._sessions.clear()
    with TestClient(server.app) as c:
        data = c.get("/api/pairs", params={
            "axis": "methodology", "task": "demo-task", "repo_context": "ctxx",
            "model": "modelx", "runner": "runnerx",
        }).json()
        resp = c.get("/api/pair-originals", params={
            "session_id": data["session_id"], "pair_index": 0,
        })
        assert resp.status_code == 200
        body = resp.json()
        assert body["files"], "expected at least one file entry"
        blob = str(body)
        assert "methone" not in blob
        assert "methtwo" not in blob
        for f in body["files"]:
            assert f["status"] in ("new", "unavailable")
            assert f["content"] is None


def test_pair_originals_out_of_range(client):
    data = _start_session(client, axis="methodology")
    resp = client.get("/api/pair-originals", params={
        "session_id": data["session_id"], "pair_index": 999,
    })
    assert resp.status_code == 400


# ---------------------------------------------------------------------------
# DBs, catalog, report
# ---------------------------------------------------------------------------

def test_dbs_lists_default(client):
    resp = client.get("/api/dbs")
    assert resp.status_code == 200
    dbs = resp.json()
    default = [d for d in dbs if d["is_default"]]
    assert len(default) == 1
    assert default[0]["n_trials"] == 4
    assert default[0]["n_passers"] == 4


def test_db_param_rejects_traversal(client):
    assert client.get("/api/axes", params={"db": "../evil.db"}).status_code == 400
    assert client.get("/api/axes", params={"db": "no-such.db"}).status_code == 404


def test_catalog_shape(client):
    resp = client.get("/api/catalog")
    assert resp.status_code == 200
    cat = resp.json()
    for key in ("tasks", "methodologies", "repo_contexts", "models", "runners"):
        assert key in cat

    # DB-only ids appear with counts even without local specs.
    tasks = {t["id"]: t for t in cat["tasks"]}
    assert "taskx" in tasks
    assert tasks["taskx"]["n_trials"] == 2
    assert tasks["taskx"]["available_locally"] is False

    # Local specs carry their descriptions.
    meths = {m["id"]: m for m in cat["methodologies"]}
    assert "baseline" in meths
    assert meths["baseline"]["available_locally"] is True
    assert meths["baseline"]["description"]

    ctxs = {c["id"]: c for c in cat["repo_contexts"]}
    assert "cosmos" in ctxs
    assert ctxs["cosmos"]["task_affinity"] == ["cosmos-A", "cosmos-B"]

    # Local tasks carry instruction + difficulty for hover previews.
    assert "moreiter-A" in tasks
    assert tasks["moreiter-A"]["instruction"]
    assert tasks["moreiter-A"]["difficulty"] == "medium"

    runners = {r["id"]: r for r in cat["runners"]}
    assert runners["claude-code"]["paid"] is True
    assert runners["manual"]["browser_launchable"] is False
    assert runners["oracle"]["paid"] is False


def test_report_json(client):
    resp = client.get("/api/report", params={"axis": "methodology"})
    assert resp.status_code == 200
    body = resp.json()
    assert body["axis"] == "methodology"
    values = {s["value"] for s in body["summaries"]}
    assert {"methalpha", "methbeta", "methx"} <= values
    assert "artifacts" in body
    assert "flag_lines" in body


# ---------------------------------------------------------------------------
# Run launcher
# ---------------------------------------------------------------------------

@pytest.fixture(autouse=True)
def _clear_runs():
    run_manager._runs.clear()
    yield
    run_manager._runs.clear()


def test_runs_plan_free_runner(client):
    resp = client.get("/api/runs/plan", params={
        "task": "moreiter-A", "methodology": "baseline", "repo_context": "none",
        "model": "test-model", "runner": "oracle", "reps": 2,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["n_trials"] == 2
    assert body["paid"] is False
    assert body["launchable"] is True
    assert body["estimate"] is None  # free -> no spend estimate needed


def test_runs_plan_paid_runner_includes_estimate_and_phrase(client):
    resp = client.get("/api/runs/plan", params={
        "task": "moreiter-A", "methodology": "baseline", "repo_context": "none",
        "model": "modelx", "runner": "claude-code", "reps": 1,
    })
    assert resp.status_code == 200
    body = resp.json()
    assert body["paid"] is True
    assert body["confirm_phrase"] == run_manager.CONFIRM_PHRASE
    assert body["estimate"]["n_trials"] == 1
    # modelx has historical cost records (0.5 usd each) in the fixture DB.
    assert body["estimate"]["estimated_total_usd"] == pytest.approx(0.5)


def test_runs_start_paid_refused_without_phrase(client):
    resp = client.post("/api/runs", json={
        "task": "moreiter-A", "methodology": "baseline", "repo_context": "none",
        "model": "modelx", "runner": "claude-code", "reps": 1,
    })
    assert resp.status_code == 409
    assert "SPEND" in resp.json()["detail"]


def test_runs_start_manual_refused(client):
    resp = client.post("/api/runs", json={
        "task": "moreiter-A", "methodology": "baseline", "repo_context": "none",
        "model": "modelx", "runner": "manual", "reps": 1,
    })
    assert resp.status_code == 400
    assert "terminal" in resp.json()["detail"].lower() or "stdin" in resp.json()["detail"].lower()


def test_runs_start_free_runner_executes(client, tmp_path, monkeypatch):
    """Free runner starts, streams progress, and finishes — with execute_all
    stubbed so the fast suite never builds a real worktree."""
    def fake_execute_all(trials, conn, delay=0.0, on_progress=None, keep_worktree=False):
        for i, t in enumerate(trials):
            if on_progress:
                on_progress(i, t, {"passed": i % 2 == 0, "usd": 0.0, "tokens": 0,
                                   "wall_seconds": 0.1, "error": None})
        return []

    monkeypatch.setattr(run_manager, "execute_all", fake_execute_all)

    resp = client.post("/api/runs", json={
        "task": "moreiter-A", "methodology": "baseline", "repo_context": "none",
        "model": "test-model", "runner": "nop", "reps": 3, "db": "scratch-test.db",
    })
    assert resp.status_code == 200, resp.text
    run_id = resp.json()["run_id"]

    deadline = time.time() + 10
    status = None
    while time.time() < deadline:
        snap = client.get(f"/api/runs/{run_id}").json()
        status = snap["status"]
        if status != "running":
            break
        time.sleep(0.05)
    assert status == "done"
    snap = client.get(f"/api/runs/{run_id}").json()
    progress = [e for e in snap["events"] if e["type"] == "progress"]
    assert len(progress) == 3
    assert progress[0]["summary"]["passed"] is True

    # SSE stream replays events and terminates.
    with client.stream("GET", f"/api/runs/{run_id}/events") as s:
        text = "".join(s.iter_text())
    assert text.count("data:") >= 4  # 3 progress + status/end
    assert '"type": "end"' in text or '"type": "status"' in text

    # cleanup the scratch db created in the project root
    (server.ROOT / "scratch-test.db").unlink(missing_ok=True)


def test_runs_single_flight(client, monkeypatch):
    started = time.time()

    def slow_execute_all(trials, conn, delay=0.0, on_progress=None, keep_worktree=False):
        time.sleep(0.5)
        return []

    monkeypatch.setattr(run_manager, "execute_all", slow_execute_all)
    body = {"task": "moreiter-A", "methodology": "baseline", "repo_context": "none",
            "model": "test-model", "runner": "nop", "reps": 1, "db": "scratch-test2.db"}
    r1 = client.post("/api/runs", json=body)
    assert r1.status_code == 200
    r2 = client.post("/api/runs", json=body)
    assert r2.status_code == 409

    deadline = time.time() + 10
    while time.time() < deadline:
        if client.get(f"/api/runs/{r1.json()['run_id']}").json()["status"] != "running":
            break
        time.sleep(0.05)
    (server.ROOT / "scratch-test2.db").unlink(missing_ok=True)
    assert started  # silence lint


# ---------------------------------------------------------------------------
# SPA fallback
# ---------------------------------------------------------------------------

def test_spa_fallback_when_not_built_or_index(client):
    resp = client.get("/grade")
    # Either the built SPA (200 + html) or the not-built page (503) — both are
    # valid states for this repo; what matters is it's not a bare 404.
    assert resp.status_code in (200, 503)
    assert "html" in resp.headers["content-type"]


def test_api_paths_never_fall_through_to_spa(client):
    resp = client.get("/api/definitely-not-a-thing")
    assert resp.status_code == 404


def test_stale_bundle_request_gets_rescue_script(client):
    """A browser holding a stale cached shell requests a hashed bundle that no
    longer exists — it must receive a reload script, not a 404 blank page."""
    resp = client.get("/assets/index-DEADBEEF.js")
    assert resp.status_code == 200
    assert resp.headers["content-type"].startswith("application/javascript")
    assert resp.headers["cache-control"] == "no-store"
    assert "location.reload" in resp.text
    assert "gavel-bundle-reload" in resp.text  # loop guard

    # Non-JS assets don't get the rescue treatment.
    assert client.get("/assets/missing.css").status_code == 404


def test_existing_bundle_served_immutable(client):
    from ui.server import FRONTEND_DIST

    assets = FRONTEND_DIST / "assets"
    if not assets.is_dir():
        import pytest as _pytest
        _pytest.skip("frontend not built")
    js = next(assets.glob("index-*.js"), None)
    assert js is not None, "built frontend has no entry bundle"
    resp = client.get(f"/assets/{js.name}")
    assert resp.status_code == 200
    assert "immutable" in resp.headers["cache-control"]
