import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from core.db import grading_readiness  # noqa: E402
from grading.aggregate import build_report  # noqa: E402
from seed_demo import seed_demo  # noqa: E402


def test_demo_db_is_gradeable_on_two_axes(tmp_path):
    conn = seed_demo(tmp_path / "demo.db")
    readiness = grading_readiness(conn)
    assert readiness["total_hidden_gate_passers"] >= 8
    assert readiness["axes"]["methodology"]["gradeable_cells"] >= 1
    assert readiness["axes"]["model"]["gradeable_cells"] >= 1


def test_demo_report_tells_full_story(tmp_path):
    conn = seed_demo(tmp_path / "demo.db")
    report = build_report(conn, "methodology", bootstrap_n=100)
    by_value = {s.value: s for s in report.summaries}

    # Pre-graded judgments produce a ranking with demo-tdd at the top.
    assert report.n_judgments > 0
    assert report.picks["high_stakes"] == "demo-tdd"
    assert report.picks["routine"] is not None
    # Costs flow through; the expensive pack is dearer than baseline.
    assert by_value["demo-agentpack"].mean_usd > by_value["demo-baseline"].mean_usd
    # At least one value sits on the frontier.
    assert any(s.on_frontier for s in report.summaries)


def test_demo_seed_is_deterministic(tmp_path):
    import sqlite3

    seed_demo(tmp_path / "a.db").close()
    seed_demo(tmp_path / "b.db").close()

    def dump(p):
        conn = sqlite3.connect(p)
        rows = list(conn.execute(
            "SELECT id FROM trial ORDER BY id"
        )) + list(conn.execute("SELECT id, choice FROM judgment ORDER BY id"))
        conn.close()
        return rows

    assert dump(tmp_path / "a.db") == dump(tmp_path / "b.db")


def test_demo_ui_serves_pairs(tmp_path):
    from fastapi.testclient import TestClient

    from ui import server

    seed_demo(tmp_path / "demo.db").close()
    server.set_db_path(tmp_path / "demo.db")
    with TestClient(server.app) as c:
        resp = c.get("/api/pairs", params={
            "axis": "methodology", "task": "demo-lru-cache",
            "repo_context": "none", "model": "demo-model-s", "runner": "demo-runner",
        })
        assert resp.status_code == 200, resp.text
        body = resp.json()
        assert body["total_pairs"] >= 3
        # Blinding: no methodology id may appear in any served diff.
        for pair in body["pairs"]:
            for side in ("left", "right"):
                for mid in ("demo-baseline", "demo-checklist", "demo-tdd", "demo-agentpack"):
                    assert mid not in pair[side]["diff"]
