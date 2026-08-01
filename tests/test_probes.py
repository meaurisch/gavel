"""E2.1 consistency probes: deliberate repeat pairs (sides swapped) inserted
into human grading sessions. Probes measure the judge (self-agreement +
side-swap flip rate); they are excluded from Bradley-Terry and invisible on
every blind surface."""

import pytest
from fastapi.testclient import TestClient

from core.db import (
    connect,
    get_grading_session,
    insert_grading_session,
    insert_judgment,
    list_judgments,
)
from core.models import GradingSession, Judgment
from grading.aggregate import build_report, judgments_to_comparisons
from grading.pairwise import compute_probe_stats, insert_probes
from tests.test_server import _seed_trial
from ui import server


# ---------------------------------------------------------------------------
# insert_probes — pure construction
# ---------------------------------------------------------------------------

def _pairs(n):
    return [(f"L{i}", f"R{i}") for i in range(n)]


def test_insert_probes_default_k_is_ten_percent_min_two():
    out, probe_of = insert_probes(_pairs(30), seed=0)
    assert len(probe_of) == 3          # round(0.1 * 30)
    assert len(out) == 33

    out, probe_of = insert_probes(_pairs(9), seed=0)
    assert len(probe_of) == 2          # min 2 beats round(0.9) == 1
    assert len(out) == 11


def test_insert_probes_caps_k_at_number_of_pairs():
    out, probe_of = insert_probes(_pairs(1), seed=0)
    assert len(probe_of) == 1
    assert len(out) == 2


def test_insert_probes_empty_input():
    out, probe_of = insert_probes([], seed=0)
    assert out == []
    assert probe_of == {}


def test_insert_probes_probe_is_swapped_copy_of_its_original():
    out, probe_of = insert_probes(_pairs(10), seed=42)
    assert probe_of  # at least one probe
    for probe_idx, orig_idx in probe_of.items():
        left, right = out[orig_idx]
        assert out[probe_idx] == (right, left)


def test_insert_probes_probe_comes_after_its_original():
    for seed in range(10):
        out, probe_of = insert_probes(_pairs(10), seed=seed)
        for probe_idx, orig_idx in probe_of.items():
            assert probe_idx > orig_idx


def test_insert_probes_originals_keep_relative_order():
    original = _pairs(10)
    out, probe_of = insert_probes(original, seed=7)
    probe_idxs = set(probe_of)
    kept = [p for i, p in enumerate(out) if i not in probe_idxs]
    assert kept == original


def test_insert_probes_picks_distinct_originals():
    out, probe_of = insert_probes(_pairs(30), seed=3)
    assert len(set(probe_of.values())) == len(probe_of)


def test_insert_probes_deterministic_for_seed():
    a = insert_probes(_pairs(20), seed=5)
    b = insert_probes(_pairs(20), seed=5)
    assert a == b


def test_insert_probes_explicit_k():
    out, probe_of = insert_probes(_pairs(20), k=5, seed=0)
    assert len(probe_of) == 5
    assert len(out) == 25


# ---------------------------------------------------------------------------
# compute_probe_stats — the two instrument numbers
# ---------------------------------------------------------------------------

def test_probe_stats_perfect_agreement():
    # original judged A, probe (sides swapped) judged B => same content chosen
    stats = compute_probe_stats({5: 0, 6: 1}, {0: "A", 5: "B", 1: "tie", 6: "tie"})
    assert stats.n_probes == 2
    assert stats.n_evaluated == 2
    assert stats.self_agreement == 1.0
    assert stats.flip_rate == 0.0


def test_probe_stats_flip():
    # original judged A, probe judged A => the verdict followed the SIDE, not
    # the content: disagreement AND a positional flip.
    stats = compute_probe_stats({5: 0}, {0: "A", 5: "A"})
    assert stats.n_evaluated == 1
    assert stats.self_agreement == 0.0
    assert stats.flip_rate == 1.0


def test_probe_stats_tie_mismatch_is_disagreement_but_not_flip():
    stats = compute_probe_stats({5: 0}, {0: "A", 5: "tie"})
    assert stats.self_agreement == 0.0
    assert stats.flip_rate == 0.0


def test_probe_stats_unjudged_probes_are_not_evaluated():
    # probe 6's original (1) was never judged; probe 7 itself never judged
    stats = compute_probe_stats(
        {5: 0, 6: 1, 7: 2}, {0: "A", 5: "B", 2: "B"}
    )
    assert stats.n_probes == 3
    assert stats.n_evaluated == 1
    assert stats.self_agreement == 1.0


def test_probe_stats_no_evaluated_pairs_yields_none_rates():
    stats = compute_probe_stats({5: 0}, {})
    assert stats.n_probes == 1
    assert stats.n_evaluated == 0
    assert stats.self_agreement is None
    assert stats.flip_rate is None


# ---------------------------------------------------------------------------
# Persistence — additive schema, legacy rows stay interpretable
# ---------------------------------------------------------------------------

def test_session_probe_of_round_trips_with_int_keys(tmp_path):
    conn = connect(tmp_path / "t.db")
    insert_grading_session(conn, GradingSession(
        id="s1", axis="model", cell={"task_id": "t"},
        pairs=[("a", "b"), ("c", "d"), ("b", "a")],
        created_at="2026-08-01T00:00:00Z",
        probe_of={2: 0},
    ))
    stored = get_grading_session(conn, "s1")
    assert stored.probe_of == {2: 0}
    conn.close()


def test_session_without_probes_round_trips_none(tmp_path):
    conn = connect(tmp_path / "t.db")
    insert_grading_session(conn, GradingSession(
        id="s1", axis="model", cell={"task_id": "t"},
        pairs=[("a", "b")], created_at="2026-08-01T00:00:00Z",
    ))
    assert get_grading_session(conn, "s1").probe_of is None
    conn.close()


def test_judgment_is_probe_round_trips(tmp_path):
    conn = connect(tmp_path / "t.db")
    for jid, is_probe in (("j1", True), ("j2", False), ("j3", None)):
        insert_judgment(conn, Judgment(
            id=jid, session_id="s1", task_id="t", model="m",
            left_trial_id=f"{jid}-l", right_trial_id=f"{jid}-r", choice="A",
            rubric_correctness=None, rubric_minimality=None,
            rubric_readability=None, rubric_overengineering=None,
            created_at="2026-08-01T00:00:00Z", is_probe=is_probe,
        ))
    by_id = {j.id: j for j in list_judgments(conn, "s1")}
    assert by_id["j1"].is_probe is True
    assert by_id["j2"].is_probe is False
    assert by_id["j3"].is_probe is None
    conn.close()


# ---------------------------------------------------------------------------
# Bradley-Terry exclusion
# ---------------------------------------------------------------------------

def _judgment(jid, left, right, choice, is_probe=None):
    return Judgment(
        id=jid, session_id="s1", task_id="taskone", model="",
        left_trial_id=left, right_trial_id=right, choice=choice,
        rubric_correctness=None, rubric_minimality=None,
        rubric_readability=None, rubric_overengineering=None,
        created_at="2026-08-01T00:00:00Z", is_probe=is_probe,
    )


def test_probe_judgments_are_excluded_from_comparisons(tmp_path):
    conn = connect(tmp_path / "t.db")
    _seed_trial(conn, trial_id="t1", task_id="taskone", methodology_id="m",
                repo_context_id="c", model="modelone", runner="r")
    _seed_trial(conn, trial_id="t2", task_id="taskone", methodology_id="m",
                repo_context_id="c", model="modeltwo", runner="r")
    insert_grading_session(conn, GradingSession(
        id="s1", axis="model", cell={"task_id": "taskone"},
        pairs=[("t1", "t2"), ("t2", "t1")],
        created_at="2026-08-01T00:00:00Z", probe_of={1: 0},
    ))
    insert_judgment(conn, _judgment("j0", "t1", "t2", "A", is_probe=False))
    insert_judgment(conn, _judgment("j1", "t2", "t1", "B", is_probe=True))

    comparisons, n_judgments, n_sessions = judgments_to_comparisons(conn, "model")
    assert comparisons == [("modelone", "modeltwo", "win")]
    assert n_judgments == 1
    conn.close()


# ---------------------------------------------------------------------------
# Server: blind construction, judgment marking, reveal stats
# ---------------------------------------------------------------------------

@pytest.fixture()
def probe_client(tmp_path):
    db_path = tmp_path / "results.db"
    conn = connect(db_path)
    # 3 models x 2 reps -> C(3,2)*3 = 9 base pairs => 2 probes, 11 total.
    for mdl in ("modelA", "modelB", "modelC"):
        for rep in (0, 1):
            _seed_trial(conn, trial_id=f"tt-{mdl}-{rep}", task_id="taskthree",
                        methodology_id="methodc", repo_context_id="ctxc",
                        model=mdl, runner="runnerc", rep=rep)
    conn.close()
    server.set_db_path(db_path)
    with TestClient(server.app) as c:
        yield c, db_path


def _start_session(client):
    resp = client.get("/api/pairs", params={
        "axis": "model", "task": "taskthree", "methodology": "methodc",
        "repo_context": "ctxc", "runner": "runnerc",
    })
    assert resp.status_code == 200
    return resp


def test_human_session_gains_probes_but_blind_payload_never_marks_them(probe_client):
    client, db_path = probe_client
    resp = _start_session(client)
    data = resp.json()
    assert data["total_pairs"] == 11          # 9 originals + 2 probes
    assert len(data["pairs"]) == 11
    # The blind payload must not distinguish probes in any way.
    assert "probe" not in resp.text.lower()

    conn = connect(db_path)
    stored = get_grading_session(conn, data["session_id"])
    assert stored.probe_of is not None and len(stored.probe_of) == 2
    for probe_idx, orig_idx in stored.probe_of.items():
        left, right = stored.pairs[orig_idx]
        assert stored.pairs[probe_idx] == (right, left)
    conn.close()


def test_session_resume_keeps_probe_count_and_stays_blind(probe_client):
    client, _ = probe_client
    sid = _start_session(client).json()["session_id"]
    server._sessions.clear()  # force DB rehydration (restart simulation)
    resp = client.get(f"/api/session/{sid}")
    assert resp.status_code == 200
    assert resp.json()["total_pairs"] == 11
    assert "probe" not in resp.text.lower()


def test_judging_marks_probe_rows(probe_client):
    client, db_path = probe_client
    data = _start_session(client).json()
    sid = data["session_id"]

    conn = connect(db_path)
    probe_of = get_grading_session(conn, sid).probe_of
    probe_idx = next(iter(probe_of))
    orig_idx = probe_of[probe_idx]

    for idx in (orig_idx, probe_idx):
        r = client.post("/api/judge", json={"session_id": sid, "pair_index": idx, "choice": "A"})
        assert r.status_code == 200

    by_pair = {(j.left_trial_id, j.right_trial_id): j for j in list_judgments(conn, sid)}
    stored = get_grading_session(conn, sid)
    assert by_pair[stored.pairs[orig_idx]].is_probe is False
    assert by_pair[stored.pairs[probe_idx]].is_probe is True
    conn.close()


def _judge_all(client, db_path, sid, flip_probes=False):
    """Judge every pair 'A' on originals; probes get the content-consistent
    'B' (or the positional 'A' when flip_probes)."""
    conn = connect(db_path)
    stored = get_grading_session(conn, sid)
    conn.close()
    probe_idxs = set(stored.probe_of or {})
    for idx in range(len(stored.pairs)):
        if idx in probe_idxs:
            choice = "A" if flip_probes else "B"
        else:
            choice = "A"
        r = client.post("/api/judge", json={"session_id": sid, "pair_index": idx, "choice": choice})
        assert r.status_code == 200
    return stored


def test_reveal_serves_probe_stats_and_excludes_probes_from_summary(probe_client):
    client, db_path = probe_client
    sid = _start_session(client).json()["session_id"]
    _judge_all(client, db_path, sid)  # consistent judge

    reveal = client.post("/api/reveal", json={"session_id": sid})
    assert reveal.status_code == 200
    body = reveal.json()

    stats = body["probe_stats"]
    assert stats["n_probes"] == 2
    assert stats["n_evaluated"] == 2
    assert stats["self_agreement"] == 1.0
    assert stats["flip_rate"] == 0.0

    # Probe pairs are marked at reveal — and only there.
    probe_pairs = [p for p in body["pairs"] if p.get("is_probe")]
    assert len(probe_pairs) == 2

    # The win/loss summary counts ORIGINAL judgments only (9, not 11).
    total = sum(v["wins"] + v["losses"] + v["ties"] for v in body["summary"].values())
    assert total == 9 * 2  # each judgment credits two axis values


def test_reveal_probe_stats_reports_flips(probe_client):
    client, db_path = probe_client
    sid = _start_session(client).json()["session_id"]
    _judge_all(client, db_path, sid, flip_probes=True)  # position-following judge

    body = client.post("/api/reveal", json={"session_id": sid}).json()
    assert body["probe_stats"]["self_agreement"] == 0.0
    assert body["probe_stats"]["flip_rate"] == 1.0


def test_probe_judgments_never_reach_report_bt(probe_client):
    client, db_path = probe_client
    sid = _start_session(client).json()["session_id"]
    _judge_all(client, db_path, sid)

    conn = connect(db_path)
    data = build_report(conn, "model", {"task_id": "taskthree"})
    assert data.n_judgments == 9  # 11 rows in the DB, 2 are probes
    assert data.probe_stats is not None
    assert data.probe_stats.n_probes == 2
    assert data.probe_stats.self_agreement == 1.0
    conn.close()


def test_report_without_probe_sessions_has_no_probe_stats(tmp_path):
    conn = connect(tmp_path / "t.db")
    _seed_trial(conn, trial_id="t1", task_id="taskone", methodology_id="m",
                repo_context_id="c", model="modelone", runner="r")
    data = build_report(conn, "model", {"task_id": "taskone"})
    assert data.probe_stats is None
    conn.close()
