import pytest
from fastapi.testclient import TestClient

from core.db import (
    connect,
    insert_trial,
    insert_run_result,
    insert_gate_result,
    insert_cost_record,
)
from core.models import Trial, RunResult, GateResult, CostRecord
from grading.pairwise import AXIS_FIELDS
from ui import server


def _make_diff_with_ids(methodology_id: str, repo_context_id: str, model: str, runner: str) -> str:
    """Build a unified diff touching src/app.py that embeds the given ids in added lines."""
    return (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,0 +1,4 @@\n"
        f"+methodology_val = {methodology_id}\n"
        f"+context_val = {repo_context_id}\n"
        f"+model_val = {model}\n"
        f"+runner_val = {runner}\n"
    )


def _seed_trial(conn, *, trial_id, task_id, methodology_id, repo_context_id, model, runner, rep=0):
    """Insert a trial + run_result + passing gate_result in one shot."""
    trial = Trial(
        id=trial_id,
        task_id=task_id,
        methodology_id=methodology_id,
        repo_context_id=repo_context_id,
        model=model,
        runner=runner,
        rep=rep,
    )
    diff = _make_diff_with_ids(methodology_id, repo_context_id, model, runner)
    rr = RunResult(trial_id=trial_id, diff=diff, exit_status=0, wall_seconds=10.0)
    gr = GateResult(trial_id=trial_id, passed=True, hidden_passed=True, hidden_output="ok")
    insert_trial(conn, trial)
    insert_run_result(conn, rr)
    insert_gate_result(conn, gr)


@pytest.fixture()
def client(tmp_path):
    db_path = tmp_path / "results.db"
    conn = connect(db_path)

    # Gradable cell: task=taskone, methodology=methoda, repo_context=ctxa, runner=runnera
    # with 2 distinct models: modelone and modeltwo
    _seed_trial(conn, trial_id="t1", task_id="taskone", methodology_id="methoda",
                repo_context_id="ctxa", model="modelone", runner="runnera")
    _seed_trial(conn, trial_id="t2", task_id="taskone", methodology_id="methoda",
                repo_context_id="ctxa", model="modeltwo", runner="runnera")

    # Non-gradable cell: task=tasktwo, only 1 model
    _seed_trial(conn, trial_id="t3", task_id="tasktwo", methodology_id="methoda",
                repo_context_id="ctxa", model="modelone", runner="runnera")

    # Decoy cell: same task but different repo_context=ctxb, models m9/m10
    _seed_trial(conn, trial_id="t4", task_id="taskone", methodology_id="methoda",
                repo_context_id="ctxb", model="modelnine", runner="runnera")
    _seed_trial(conn, trial_id="t5", task_id="taskone", methodology_id="methoda",
                repo_context_id="ctxb", model="modelten", runner="runnera")

    # Rich cell for BT/stats: task=taskthree, methodology=methodc, repo_context=ctxc,
    # runner=runnerc, 3 models x 2 reps, all passing, with cost records.
    costs = {"modelA": 0.10, "modelB": 0.20, "modelC": 5.00}
    for mdl, usd in costs.items():
        for rep in (0, 1):
            tid = f"tt-{mdl}-{rep}"
            _seed_trial(conn, trial_id=tid, task_id="taskthree", methodology_id="methodc",
                        repo_context_id="ctxc", model=mdl, runner="runnerc", rep=rep)
            insert_cost_record(conn, CostRecord(
                trial_id=tid, native_unit="usd", native_amount=usd, usd_equiv=usd,
                input_tokens=100, output_tokens=50, cache_read_tokens=0,
            ))

    conn.close()
    server.set_db_path(db_path)
    with TestClient(server.app) as c:
        yield c


def test_cells_lists_multi_value_and_omits_single(client):
    resp = client.get("/api/cells", params={"axis": "model"})
    assert resp.status_code == 200
    cells = resp.json()

    task_ids = [c["task_id"] for c in cells]
    assert "taskone" in task_ids
    assert "tasktwo" not in task_ids

    taskone_cells = [c for c in cells if c["task_id"] == "taskone"]
    for c in taskone_cells:
        assert c["n_values"] >= 2


def test_pairs_filters_to_one_cell(client):
    # Pin to cell cA -> only modelone vs modeltwo: 1 base pair + 1 E2.1
    # consistency probe (k capped at the pair count)
    resp = client.get("/api/pairs", params={
        "axis": "model",
        "task": "taskone",
        "methodology": "methoda",
        "repo_context": "ctxa",
        "runner": "runnera",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_pairs"] == 2

    # Pin to decoy cell cB -> only modelnine vs modelten
    resp2 = client.get("/api/pairs", params={
        "axis": "model",
        "task": "taskone",
        "methodology": "methoda",
        "repo_context": "ctxb",
        "runner": "runnera",
    })
    assert resp2.status_code == 200
    data2 = resp2.json()
    assert data2["total_pairs"] == 2


def test_pairs_diffs_have_no_axis_ids(client):
    resp = client.get("/api/pairs", params={
        "axis": "model",
        "task": "taskone",
        "methodology": "methoda",
        "repo_context": "ctxa",
        "runner": "runnera",
    })
    assert resp.status_code == 200
    data = resp.json()

    forbidden = {"methoda", "ctxa", "modelone", "modeltwo", "runnera"}
    expected_tokens = {"[methodology]", "[context]", "[model]", "[runner]"}

    all_diffs = ""
    for pair in data["pairs"]:
        all_diffs += pair["left"]["diff"]
        all_diffs += pair["right"]["diff"]

    for raw_id in forbidden:
        assert raw_id not in all_diffs, f"Raw id {raw_id!r} leaked into anonymized diff"

    for token in expected_tokens:
        assert token in all_diffs, f"Expected token {token!r} not found in anonymized diff"


def test_pairs_never_serve_the_observational_tier(tmp_path):
    """The observational tier (e.g. convention adherence) tracks the
    methodology axis, so it must not reach a blind grader — same rule as
    cost/tokens/time. Browse serves it; blind comparison never does."""
    from fastapi.testclient import TestClient

    db_path = tmp_path / "obs.db"
    conn = connect(db_path)
    for tid, mdl, adhered in (("o1", "modelone", True), ("o2", "modeltwo", False)):
        insert_trial(conn, Trial(id=tid, task_id="t", methodology_id="m",
                                 repo_context_id="c", model=mdl, runner="r", rep=0))
        insert_run_result(conn, RunResult(trial_id=tid, diff=_make_diff_with_ids("m", "c", mdl, "r"),
                                         exit_status=0, wall_seconds=1.0))
        insert_gate_result(conn, GateResult(
            trial_id=tid, passed=True, hidden_passed=True, hidden_output="ok",
            observe_passed=adhered, observe_output="ADHERENCE house-style PASS",
        ))
    conn.close()

    server.set_db_path(db_path)
    with TestClient(server.app) as c:
        resp = c.get("/api/pairs", params={
            "axis": "model", "task": "t", "methodology": "m",
            "repo_context": "c", "runner": "r",
        })
        assert resp.status_code == 200
        assert "observe" not in resp.text
        assert "ADHERENCE" not in resp.text
        side = resp.json()["pairs"][0]["left"]
        assert set(side["gate"]) == {"compile_passed", "visible_passed", "hidden_passed"}
        assert set(side["gate_detail"]) == {"passed", "compile", "visible", "hidden"}

        # The unblinded browse surface DOES carry it.
        rows = {r["id"]: r for r in c.get("/api/trials").json()}
        assert rows["o1"]["observe_passed"] is True
        assert rows["o2"]["observe_passed"] is False
        detail = c.get("/api/trials/o1").json()
        assert detail["gate_result"]["observe_passed"] is True
        assert detail["gate_result"]["observe_output"] == "ADHERENCE house-style PASS"


def test_axes_lists_gradable(client):
    resp = client.get("/api/axes")
    assert resp.status_code == 200
    axes = resp.json()
    assert isinstance(axes, list)
    axis_names = {a["axis"] for a in axes}
    assert "model" in axis_names
    model_entry = next(a for a in axes if a["axis"] == "model")
    assert model_entry["n_cells"] >= 1


_RICH_CELL = {
    "axis": "model",
    "task": "taskthree",
    "methodology": "methodc",
    "repo_context": "ctxc",
    "runner": "runnerc",
}


def _judge_n(client, session_id, pairs, n, choice="A"):
    for p in pairs[:n]:
        resp = client.post("/api/judge", json={
            "session_id": session_id,
            "pair_index": p["pair_index"],
            "choice": choice,
        })
        assert resp.status_code == 200


def test_reveal_includes_bt_scores_and_flags(client):
    resp = client.get("/api/pairs", params=_RICH_CELL)
    assert resp.status_code == 200
    data = resp.json()
    session_id = data["session_id"]
    pairs = data["pairs"]
    assert data["total_pairs"] == 11  # C(3,2) * 3 base pairs + 2 probes

    _judge_n(client, session_id, pairs, len(pairs))

    # GET is read-only: an unrevealed session returns a locked stub.
    locked = client.get("/api/reveal", params={"session_id": session_id}).json()
    assert locked["revealed"] is False
    assert locked["pairs"] == []

    rev = client.post("/api/reveal", json={"session_id": session_id})
    assert rev.status_code == 200
    body = rev.json()
    assert body["revealed"] is True

    assert body["bt_scores"] is not None
    values = {s["axis_value"] for s in body["bt_scores"]}
    assert values == {"modelA", "modelB", "modelC"}
    for s in body["bt_scores"]:
        assert s["ci_lower"] <= s["elo"] <= s["ci_upper"]

    assert body["pass_rates"] == {"modelA": 1.0, "modelB": 1.0, "modelC": 1.0}
    assert "taskthree" in body["analyzer_flags"]["non_discriminating_tasks"]


def test_reveal_skips_bt_with_few_judgments(client):
    resp = client.get("/api/pairs", params=_RICH_CELL)
    data = resp.json()
    _judge_n(client, data["session_id"], data["pairs"], 2)

    rev = client.post("/api/reveal", json={"session_id": data["session_id"]})
    body = rev.json()
    assert body["bt_scores"] is None


def test_grading_status_reports_readiness(client):
    resp = client.get("/api/grading-status")
    assert resp.status_code == 200
    body = resp.json()

    assert isinstance(body["total_hidden_gate_passers"], int)
    assert body["total_hidden_gate_passers"] >= 1

    assert set(body["axes"]) == set(AXIS_FIELDS)
    for axis in AXIS_FIELDS:
        entry = body["axes"][axis]
        assert set(entry) == {"distinct_passing_values", "gradeable_cells"}
        assert isinstance(entry["distinct_passing_values"], int)
        assert isinstance(entry["gradeable_cells"], int)

    model_entry = body["axes"]["model"]
    assert model_entry["gradeable_cells"] >= 1


def test_stats_returns_per_value(client):
    resp = client.get("/api/stats", params=_RICH_CELL)
    assert resp.status_code == 200
    stats = {s["axis_value"]: s for s in resp.json()["stats"]}
    assert set(stats) == {"modelA", "modelB", "modelC"}
    assert stats["modelA"]["pass_rate"] == 1.0
    assert stats["modelA"]["n_trials"] == 2
    assert stats["modelA"]["mean_cost_usd"] == 0.10
    assert stats["modelC"]["mean_cost_usd"] == 5.00
    assert stats["modelA"]["mean_wall_seconds"] == 10.0


def test_inert_axis_ids_skips_no_file_specs():
    from types import SimpleNamespace

    from ui.server import _inert_axis_ids

    trials = [
        SimpleNamespace(runner="claude-code", methodology_id="baseline", repo_context_id="none"),
        SimpleNamespace(runner="claude-code", methodology_id="no-such-methodology", repo_context_id="no-such-ctx"),
    ]
    inert = _inert_axis_ids(trials)
    # baseline/none lay down zero files -> inert; unknown ids fail to load ->
    # NOT inert (when in doubt, keep redacting).
    assert "baseline" in inert
    assert "none" in inert
    assert "no-such-methodology" not in inert
    assert "no-such-ctx" not in inert


def test_pairs_excludes_passing_trial_without_run_result(tmp_path):
    from fastapi.testclient import TestClient

    from core.db import insert_gate_result, insert_trial
    from core.models import GateResult, Trial

    db_path = tmp_path / "results.db"
    conn = connect(db_path)
    _seed_trial(conn, trial_id="ok1", task_id="t", methodology_id="m",
                repo_context_id="c", model="modelone", runner="r")
    _seed_trial(conn, trial_id="ok2", task_id="t", methodology_id="m",
                repo_context_id="c", model="modeltwo", runner="r")
    # Gate-passing trial with NO run_result row: must be excluded, not 500.
    broken = Trial(id="broken", task_id="t", methodology_id="m",
                   repo_context_id="c", model="modelthree", runner="r", rep=0)
    insert_trial(conn, broken)
    insert_gate_result(conn, GateResult(trial_id="broken", passed=True, hidden_passed=True))
    conn.close()

    server.set_db_path(db_path)
    with TestClient(server.app) as c:
        resp = c.get("/api/pairs", params={
            "axis": "model", "task": "t", "methodology": "m",
            "repo_context": "c", "runner": "r",
        })
        assert resp.status_code == 200
        body = resp.json()
        ids = {p["left"]["label"] for p in body["pairs"]} | {p["right"]["label"] for p in body["pairs"]}
        assert ids <= {"A", "B"}
        assert body["total_pairs"] >= 1


def test_session_survives_server_restart(client):
    resp = client.get("/api/pairs", params={
        "axis": "model", "task": "taskone", "methodology": "methoda",
        "repo_context": "ctxa", "runner": "runnera",
    })
    assert resp.status_code == 200
    body = resp.json()
    sid = body["session_id"]

    r = client.post("/api/judge", json={"session_id": sid, "pair_index": 0, "choice": "A"})
    assert r.status_code == 200

    # Simulate a server restart: drop all in-memory session state.
    server._sessions.clear()

    # Judging and revealing must still work off the persisted session.
    reveal = client.post("/api/reveal", json={"session_id": sid})
    assert reveal.status_code == 200
    judged = [p for p in reveal.json()["pairs"] if p["choice"] == "A"]
    assert len(judged) == 1


def test_stats_pass_rate_denominator_matches_reveal(tmp_path):
    """A trial with no gate verdict must not deflate pass_rate (the /api/reveal
    denominator) — but still counts in n_trials."""
    from fastapi.testclient import TestClient

    from core.db import insert_run_result, insert_trial
    from core.models import RunResult, Trial

    db_path = tmp_path / "results.db"
    conn = connect(db_path)
    _seed_trial(conn, trial_id="g1", task_id="t", methodology_id="m",
                repo_context_id="c", model="modelone", runner="r")
    _seed_trial(conn, trial_id="g2", task_id="t", methodology_id="m",
                repo_context_id="c", model="modeltwo", runner="r")
    # modelone also has a trial with run_result but NO gate row (legacy orphan).
    ungated = Trial(id="g3", task_id="t", methodology_id="m",
                    repo_context_id="c", model="modelone", runner="r", rep=1)
    insert_trial(conn, ungated)
    insert_run_result(conn, RunResult(trial_id="g3", diff="d", exit_status=0, wall_seconds=1.0))
    conn.close()

    server.set_db_path(db_path)
    with TestClient(server.app) as c:
        resp = c.get("/api/stats", params={
            "axis": "model", "task": "t", "methodology": "m",
            "repo_context": "c", "runner": "r",
        })
        assert resp.status_code == 200
        stats = {s["axis_value"]: s for s in resp.json()["stats"]}
        assert stats["modelone"]["pass_rate"] == 1.0   # 1/1 gated, not 1/2
        assert stats["modelone"]["n_trials"] == 2
