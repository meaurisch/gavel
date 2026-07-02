import pytest

from core.db import (
    connect,
    insert_cost_record,
    insert_gate_result,
    insert_grading_session,
    insert_judgment,
    insert_run_result,
    insert_trial,
)
from core.models import CostRecord, GateResult, GradingSession, Judgment, RunResult, Trial
from grading.aggregate import (
    AxisValueSummary,
    build_report,
    judgments_to_comparisons,
    pareto_frontier,
    stakes_picks,
)


# ---------------------------------------------------------------- helpers

def _trial(tid, methodology, model="m1", task="t1", ctx="none", runner="r1", rep=0):
    return Trial(id=tid, task_id=task, methodology_id=methodology,
                 repo_context_id=ctx, model=model, runner=runner, rep=rep)


def _seed(conn, tid, methodology, *, passed=True, usd=None, task="t1", model="m1"):
    insert_trial(conn, _trial(tid, methodology, task=task, model=model))
    insert_run_result(conn, RunResult(trial_id=tid, diff="d", exit_status=0, wall_seconds=1.0))
    insert_gate_result(conn, GateResult(
        trial_id=tid, passed=passed,
        compile_passed=True, visible_passed=passed, hidden_passed=passed,
    ))
    if usd is not None:
        insert_cost_record(conn, CostRecord(
            trial_id=tid, native_unit="usd", native_amount=usd, usd_equiv=usd,
            input_tokens=10, output_tokens=10, cache_read_tokens=0,
        ))


def _judge(conn, session_id, left, right, choice, n=0):
    insert_judgment(conn, Judgment(
        id=f"{session_id}-j{n}", session_id=session_id, task_id="t1", model="m1",
        left_trial_id=left, right_trial_id=right, choice=choice,
        rubric_correctness=None, rubric_minimality=None,
        rubric_readability=None, rubric_overengineering=None,
        created_at="2026-07-02T00:00:00+00:00",
    ))


def _session(conn, sid, axis, pairs):
    insert_grading_session(conn, GradingSession(
        id=sid, axis=axis, cell={"task_id": "t1"}, pairs=pairs,
        created_at="2026-07-02T00:00:00+00:00",
    ))


# ---------------------------------------------------------------- pareto

def test_pareto_frontier_basic():
    points = {
        "cheap-bad": (1.0, 0.0),
        "dear-good": (10.0, 2.0),
        "dominated": (12.0, 1.0),   # costs more than dear-good, worse quality
    }
    assert pareto_frontier(points) == {"cheap-bad", "dear-good"}


def test_pareto_frontier_ties_both_kept():
    points = {"a": (1.0, 1.0), "b": (1.0, 1.0)}
    assert pareto_frontier(points) == {"a", "b"}


def test_pareto_frontier_strict_domination():
    points = {"a": (1.0, 1.0), "b": (1.0, 2.0)}
    assert pareto_frontier(points) == {"b"}


# ---------------------------------------------------------------- picks

def _summary(value, strength, ci, mean_usd):
    return AxisValueSummary(value=value, bt_strength=strength, bt_ci=ci, mean_usd=mean_usd)


def test_stakes_picks_routine_is_cheapest_within_ci_overlap():
    s = [
        _summary("winner", 1.0, (0.5, 1.5), 5.0),
        _summary("cheap-similar", 0.6, (0.2, 1.0), 1.0),   # CI overlaps winner
        _summary("cheap-worse", -1.6, (-2.0, -1.2), 0.10),  # no overlap
    ]
    picks = stakes_picks(s)
    assert picks["high_stakes"] == "winner"
    assert picks["routine"] == "cheap-similar"


def test_stakes_picks_no_bt_data():
    s = [AxisValueSummary(value="only-gate-data")]
    assert stakes_picks(s) == {"high_stakes": None, "routine": None}


def test_stakes_picks_winner_is_own_routine_when_nothing_overlaps():
    s = [
        _summary("winner", 2.0, (1.8, 2.2), 5.0),
        _summary("far", -2.0, (-2.2, -1.8), 0.1),
    ]
    picks = stakes_picks(s)
    assert picks == {"high_stakes": "winner", "routine": "winner"}


# ---------------------------------------------------------------- adapter

def test_judgments_to_comparisons_maps_choices(tmp_path):
    conn = connect(tmp_path / "t.db")
    _seed(conn, "ta", "alpha")
    _seed(conn, "tb", "beta")
    _session(conn, "s1", "methodology", [("ta", "tb"), ("tb", "ta")])
    _judge(conn, "s1", "ta", "tb", "A", 0)     # alpha win
    _judge(conn, "s1", "tb", "ta", "B", 1)     # left=beta loses -> alpha wins
    _judge(conn, "s1", "ta", "tb", "tie", 2)

    comps, n_j, n_s = judgments_to_comparisons(conn, "methodology")
    assert (n_j, n_s) == (3, 1)
    assert ("alpha", "beta", "win") in comps
    assert ("beta", "alpha", "loss") in comps
    assert ("alpha", "beta", "tie") in comps


def test_judgments_to_comparisons_skips_other_axes_and_same_value(tmp_path):
    conn = connect(tmp_path / "t.db")
    _seed(conn, "ta", "alpha")
    _seed(conn, "tb", "alpha", usd=1.0)  # same methodology
    _session(conn, "s1", "model", [("ta", "tb")])
    _judge(conn, "s1", "ta", "tb", "A", 0)

    comps, n_j, n_s = judgments_to_comparisons(conn, "methodology")
    assert comps == []
    assert (n_j, n_s) == (0, 0)

    # On its own axis the same-value pair is dropped from comparisons but the
    # judgment still counts as in-scope work.
    comps_m, n_jm, _ = judgments_to_comparisons(conn, "model")
    assert comps_m == []  # same model on both sides
    assert n_jm == 1


def test_judgments_to_comparisons_cell_scoping(tmp_path):
    conn = connect(tmp_path / "t.db")
    _seed(conn, "ta", "alpha")
    _seed(conn, "tb", "beta")
    _session(conn, "s1", "methodology", [("ta", "tb")])
    _judge(conn, "s1", "ta", "tb", "A", 0)

    comps, n_j, _ = judgments_to_comparisons(conn, "methodology", trial_ids={"ta"})
    assert comps == [] and n_j == 0
    comps, n_j, _ = judgments_to_comparisons(conn, "methodology", trial_ids={"ta", "tb"})
    assert len(comps) == 1 and n_j == 1


# ---------------------------------------------------------------- build_report

@pytest.fixture()
def rich_db(tmp_path):
    """Three methodologies x 3 reps with judgments: alpha > beta > gamma;
    alpha is expensive, beta mid, gamma cheap."""
    conn = connect(tmp_path / "r.db")
    costs = {"alpha": 3.0, "beta": 1.0, "gamma": 0.2}
    tids = {}
    for m, usd in costs.items():
        for rep in range(3):
            tid = f"{m}-{rep}"
            insert_trial(conn, _trial(tid, m, rep=rep))
            insert_run_result(conn, RunResult(trial_id=tid, diff="d", exit_status=0, wall_seconds=2.0))
            insert_gate_result(conn, GateResult(
                trial_id=tid, passed=True,
                compile_passed=True, visible_passed=True, hidden_passed=True,
            ))
            insert_cost_record(conn, CostRecord(
                trial_id=tid, native_unit="usd", native_amount=usd, usd_equiv=usd,
                input_tokens=10, output_tokens=10, cache_read_tokens=0,
            ))
            tids.setdefault(m, []).append(tid)

    pairs = []
    judgments = []
    n = 0
    for rep in range(3):
        for winner_m, loser_m in (("alpha", "beta"), ("alpha", "gamma"), ("beta", "gamma")):
            pairs.append((tids[winner_m][rep], tids[loser_m][rep]))
            judgments.append((tids[winner_m][rep], tids[loser_m][rep], "A", n))
            n += 1
    _session(conn, "s1", "methodology", pairs)
    for left, right, choice, i in judgments:
        _judge(conn, "s1", left, right, choice, i)
    return conn


def test_build_report_ranking_and_frontier(rich_db):
    report = build_report(rich_db, "methodology", bootstrap_n=100)

    by_value = {s.value: s for s in report.summaries}
    assert set(by_value) == {"alpha", "beta", "gamma"}

    # Ranking: alpha strongest, gamma weakest.
    assert by_value["alpha"].bt_strength > by_value["beta"].bt_strength > by_value["gamma"].bt_strength
    assert by_value["alpha"].elo > by_value["beta"].elo

    # Cost rollup: alpha 3 trials x $3.
    assert by_value["alpha"].total_usd == pytest.approx(9.0)
    assert by_value["alpha"].mean_usd == pytest.approx(3.0)

    # Gate tiers all pass.
    assert by_value["beta"].gate_pass_rate == 1.0
    assert by_value["beta"].tier_pass_rates["hidden"] == 1.0

    # Frontier: gamma (cheapest) and alpha (best) are on it; beta is dominated
    # only if something is both cheaper AND better — gamma is cheaper but
    # worse, alpha better but dearer, so beta is ALSO on the frontier.
    assert by_value["gamma"].on_frontier
    assert by_value["alpha"].on_frontier
    assert by_value["beta"].on_frontier

    assert report.picks["high_stakes"] == "alpha"
    assert report.n_judgments == 9
    assert report.n_sessions == 1


def test_build_report_cell_scoping_excludes_other_tasks(rich_db):
    # Add an out-of-scope trial on another task with huge cost.
    _seed(rich_db, "other", "alpha", usd=100.0, task="t2")
    report = build_report(rich_db, "methodology", cell={"task_id": "t1"}, bootstrap_n=50)
    alpha = next(s for s in report.summaries if s.value == "alpha")
    assert alpha.total_usd == pytest.approx(9.0)


def test_build_report_without_judgments_still_reports_gate_and_cost(tmp_path):
    conn = connect(tmp_path / "e.db")
    _seed(conn, "ta", "alpha", passed=True, usd=1.0)
    _seed(conn, "tb", "beta", passed=False, usd=2.0)
    report = build_report(conn, "methodology")
    by_value = {s.value: s for s in report.summaries}
    assert by_value["alpha"].gate_pass_rate == 1.0
    assert by_value["beta"].gate_pass_rate == 0.0
    assert by_value["beta"].mean_usd == pytest.approx(2.0)
    assert report.picks == {"high_stakes": None, "routine": None}
    assert all(s.bt_strength is None for s in report.summaries)


def test_build_report_unknown_axis_raises(tmp_path):
    conn = connect(tmp_path / "x.db")
    with pytest.raises(ValueError, match="Unknown axis"):
        build_report(conn, "flavor")
