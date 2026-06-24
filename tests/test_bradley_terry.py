import math

from grading.bradley_terry import (
    fit_bradley_terry,
    bootstrap_ci,
    bt_scores_to_elo,
)


def _repeat(comparisons, times):
    out = []
    for _ in range(times):
        out.extend(comparisons)
    return out


def test_fit_ranks_transitive_chain():
    # A always beats B, B always beats C, A always beats C.
    comparisons = _repeat(
        [("A", "B", "win"), ("B", "C", "win"), ("A", "C", "win")],
        times=10,
    )
    strengths = fit_bradley_terry(comparisons)
    assert strengths["A"] > strengths["B"] > strengths["C"]


def test_fit_all_ties_gives_equal_strengths():
    comparisons = _repeat(
        [("A", "B", "tie"), ("B", "C", "tie"), ("A", "C", "tie")],
        times=10,
    )
    strengths = fit_bradley_terry(comparisons)
    values = list(strengths.values())
    assert max(values) - min(values) < 1e-6


def test_fit_empty_returns_empty():
    assert fit_bradley_terry([]) == {}


def test_strengths_normalized_to_mean_zero():
    comparisons = _repeat(
        [("A", "B", "win"), ("B", "C", "win"), ("A", "C", "win")],
        times=5,
    )
    strengths = fit_bradley_terry(comparisons)
    assert abs(sum(strengths.values()) / len(strengths)) < 1e-9


def test_bootstrap_ci_brackets_point_estimate():
    comparisons = _repeat(
        [("A", "B", "win"), ("B", "C", "win"), ("A", "C", "win")],
        times=20,
    )
    point = fit_bradley_terry(comparisons)
    ci = bootstrap_ci(comparisons, n_bootstrap=200, seed=0)
    for key, (lower, median, upper) in ci.items():
        assert lower <= median <= upper
        assert lower <= point[key] <= upper


def test_elo_preserves_order_and_centers_on_base():
    strengths = {"A": 0.5, "B": 0.0, "C": -0.5}
    elo = bt_scores_to_elo(strengths, base=1000.0, scale=400.0)
    assert elo["A"] > elo["B"] > elo["C"]
    assert math.isclose(elo["B"], 1000.0, abs_tol=1e-9)
    # B has strength 0 -> exactly base
    expected_a = 1000.0 + 400.0 * 0.5 / math.log(10)
    assert math.isclose(elo["A"], expected_a, rel_tol=1e-9)
