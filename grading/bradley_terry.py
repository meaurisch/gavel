"""Bradley-Terry model — turn pairwise judgments into a ranked strength scale.

Comparisons are tuples ``(first_id, second_id, outcome)`` where ``outcome`` is one
of ``"win"`` (first beats second), ``"loss"`` (second beats first), or ``"tie"``.
IDs are comparison-axis values (e.g. methodology ids, model names).

Fitting uses the standard MM (minorization-maximization) iteration in linear
strength (pi) space; the public API returns log-strengths normalized to mean 0.
"""

import math

import numpy as np

_EPS = 1e-8
_MAX_ITERS = 100
_TOL = 1e-9


def _aggregate(comparisons):
    ids = sorted({a for a, _, _ in comparisons} | {b for _, b, _ in comparisons})
    idx = {v: i for i, v in enumerate(ids)}
    n = len(ids)
    wins = np.zeros(n)
    counts = np.zeros((n, n))
    for a, b, outcome in comparisons:
        i, j = idx[a], idx[b]
        counts[i, j] += 1
        counts[j, i] += 1
        if outcome == "win":
            wins[i] += 1
        elif outcome == "loss":
            wins[j] += 1
        elif outcome == "tie":
            wins[i] += 0.5
            wins[j] += 0.5
        else:
            raise ValueError(f"Unknown outcome {outcome!r}")
    return ids, wins, counts


def fit_bradley_terry(comparisons: list[tuple[str, str, str]]) -> dict[str, float]:
    """Fit a Bradley-Terry model; return log-strength per id (mean-centered)."""
    if not comparisons:
        return {}

    ids, wins, counts = _aggregate(comparisons)
    n = len(ids)
    pi = np.ones(n)

    for _ in range(_MAX_ITERS):
        new = np.empty(n)
        for i in range(n):
            denom = 0.0
            for j in range(n):
                if j != i and counts[i, j] > 0:
                    denom += counts[i, j] / (pi[i] + pi[j])
            new[i] = wins[i] / denom if (denom > 0 and wins[i] > 0) else _EPS
        new = np.clip(new, _EPS, 1.0 / _EPS)
        # normalize so the geometric mean is 1 (i.e. mean log-strength is 0)
        log_new = np.log(new)
        log_new -= log_new.mean()
        new = np.exp(log_new)
        if np.max(np.abs(np.log(new) - np.log(pi))) < _TOL:
            pi = new
            break
        pi = new

    log_pi = np.log(pi)
    log_pi -= log_pi.mean()
    return {ids[i]: float(log_pi[i]) for i in range(n)}


def bootstrap_ci(
    comparisons: list[tuple[str, str, str]],
    n_bootstrap: int = 1000,
    ci: float = 0.95,
    seed: int | None = None,
) -> dict[str, tuple[float, float, float]]:
    """Bootstrap confidence intervals on log-strength. Returns {id: (lower, median, upper)}."""
    if not comparisons:
        return {}

    rng = np.random.default_rng(seed)
    m = len(comparisons)
    samples: dict[str, list[float]] = {}
    for _ in range(n_bootstrap):
        picks = rng.integers(0, m, size=m)
        resample = [comparisons[k] for k in picks]
        fit = fit_bradley_terry(resample)
        for key, val in fit.items():
            samples.setdefault(key, []).append(val)

    lo_pct = (1.0 - ci) / 2.0 * 100.0
    hi_pct = (1.0 + ci) / 2.0 * 100.0
    result: dict[str, tuple[float, float, float]] = {}
    for key, vals in samples.items():
        arr = np.array(vals)
        result[key] = (
            float(np.percentile(arr, lo_pct)),
            float(np.percentile(arr, 50.0)),
            float(np.percentile(arr, hi_pct)),
        )
    return result


def strength_to_elo(strength: float, base: float = 1000.0, scale: float = 400.0) -> float:
    """Map one BT log-strength onto the Elo-style display scale. The single
    home of the formula — CLI, HTML report, and UI convert through here so
    the scales can never drift apart."""
    return base + scale * strength / math.log(10)


def bt_scores_to_elo(
    strengths: dict[str, float],
    base: float = 1000.0,
    scale: float = 400.0,
) -> dict[str, float]:
    """Convert BT log-strengths to Elo-style scores centered on ``base``."""
    return {k: strength_to_elo(v, base, scale) for k, v in strengths.items()}
