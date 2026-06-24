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
    # Pin to cell cA -> only modelone vs modeltwo
    resp = client.get("/api/pairs", params={
        "axis": "model",
        "task": "taskone",
        "methodology": "methoda",
        "repo_context": "ctxa",
        "runner": "runnera",
    })
    assert resp.status_code == 200
    data = resp.json()
    assert data["total_pairs"] == 1

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
    assert data2["total_pairs"] == 1


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
    assert data["total_pairs"] == 9  # C(3,2) * 3

    _judge_n(client, session_id, pairs, len(pairs))

    rev = client.get("/api/reveal", params={"session_id": session_id})
    assert rev.status_code == 200
    body = rev.json()

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

    rev = client.get("/api/reveal", params={"session_id": data["session_id"]})
    body = rev.json()
    assert body["bt_scores"] is None


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
