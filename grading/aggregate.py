"""Aggregation for the report command: judgment→Bradley-Terry adaptation,
cost rollup, quality/cost Pareto frontier, and the stakes-based picks from
IMPLEMENTATION_PLAN §6 (high-stakes → quality winner; routine → cheapest
value statistically indistinguishable from it)."""

from __future__ import annotations

import logging
import sqlite3
from dataclasses import dataclass, field

from core.db import (
    get_trial,
    list_cost_records,
    list_gate_results,
    list_grading_sessions,
    list_judgments,
    list_trials,
)
from grading.analyzer import AnalyzerFlags, analyze
from grading.bradley_terry import bootstrap_ci, bt_scores_to_elo, fit_bradley_terry
from grading.pairwise import AXIS_FIELDS

logger = logging.getLogger(__name__)


@dataclass
class AxisValueSummary:
    value: str
    n_trials: int = 0
    n_gated: int = 0
    gate_pass_rate: float | None = None
    tier_pass_rates: dict = field(default_factory=dict)  # compile/visible/hidden -> float|None
    total_usd: float = 0.0
    mean_usd: float | None = None
    n_comparisons: int = 0
    bt_strength: float | None = None
    bt_ci: tuple[float, float] | None = None  # (lower, upper), log-strength scale
    elo: float | None = None
    on_frontier: bool = False


@dataclass
class ReportData:
    axis: str
    cell: dict  # the filters that scoped this report (may be empty)
    summaries: list[AxisValueSummary]
    picks: dict  # {"high_stakes": value|None, "routine": value|None}
    flags: AnalyzerFlags
    n_judgments: int
    n_sessions: int


def flag_lines(flags: AnalyzerFlags) -> list[str]:
    """Human-readable analyzer flags — one wording, shared by the terminal
    report and the HTML artifact."""
    return (
        [f"non-discriminating task: {t}" for t in flags.non_discriminating_tasks]
        + [f"flaky task: {t}" for t in flags.flaky_tasks]
        + list(flags.cost_quality_notes)
    )


def judgments_to_comparisons(
    conn: sqlite3.Connection,
    axis: str,
    trial_ids: set[str] | None = None,
    trials_by_id: dict | None = None,
) -> tuple[list[tuple[str, str, str]], int, int]:
    """Translate persisted judgments into Bradley-Terry comparison tuples on
    the chosen axis: (left_value, right_value, win|loss|tie).

    Judgments from sessions graded on a DIFFERENT axis are skipped — their
    pairs pin this axis to one value, so they carry no signal for it.
    Same-value pairs are skipped too. If `trial_ids` is given, only judgments
    whose two trials both fall inside it count (cell scoping).

    Returns (comparisons, n_judgments_in_scope, n_sessions_in_scope).
    """
    field_name = AXIS_FIELDS[axis]
    comparisons: list[tuple[str, str, str]] = []
    n_judgments = 0
    n_sessions = 0

    for session in list_grading_sessions(conn):
        if session.axis != axis:
            continue
        in_scope = [
            j for j in list_judgments(conn, session.id)
            if trial_ids is None
            or (j.left_trial_id in trial_ids and j.right_trial_id in trial_ids)
        ]
        if not in_scope:
            continue
        n_sessions += 1
        n_judgments += len(in_scope)
        lookup = trials_by_id or {}
        for j in in_scope:
            left = lookup.get(j.left_trial_id) or get_trial(conn, j.left_trial_id)
            right = lookup.get(j.right_trial_id) or get_trial(conn, j.right_trial_id)
            if left is None or right is None:
                logger.warning("Judgment %s references missing trial(s); skipped", j.id)
                continue
            lv, rv = getattr(left, field_name), getattr(right, field_name)
            if lv == rv:
                continue
            outcome = {"A": "win", "B": "loss", "tie": "tie"}.get(j.choice)
            if outcome is None:
                continue
            comparisons.append((lv, rv, outcome))
    return comparisons, n_judgments, n_sessions


def pareto_frontier(points: dict[str, tuple[float, float]]) -> set[str]:
    """points: value -> (cost, quality); lower cost and higher quality are
    better. Returns the set of non-dominated values. A point is dominated if
    another point is at least as good on both dimensions and strictly better
    on one."""
    frontier: set[str] = set()
    items = list(points.items())
    for v, (cost, quality) in items:
        dominated = any(
            (oc <= cost and oq >= quality) and (oc < cost or oq > quality)
            for ov, (oc, oq) in items
            if ov != v
        )
        if not dominated:
            frontier.add(v)
    return frontier


def stakes_picks(summaries: list[AxisValueSummary]) -> dict:
    """§6 decision rule. high_stakes: the quality winner (highest BT
    strength). routine: the cheapest value whose CI overlaps the winner's
    (overlapping CIs = statistically indistinguishable). Values without BT
    data are ineligible."""
    ranked = [s for s in summaries if s.bt_strength is not None]
    if not ranked:
        return {"high_stakes": None, "routine": None}

    winner = max(ranked, key=lambda s: s.bt_strength)

    def overlaps(s: AxisValueSummary) -> bool:
        if s.bt_ci is None or winner.bt_ci is None:
            return s.value == winner.value
        return s.bt_ci[1] >= winner.bt_ci[0] and winner.bt_ci[1] >= s.bt_ci[0]

    candidates = [s for s in ranked if overlaps(s) and s.mean_usd is not None]
    routine = min(candidates, key=lambda s: s.mean_usd) if candidates else winner
    return {"high_stakes": winner.value, "routine": routine.value}


def build_report(
    conn: sqlite3.Connection,
    axis: str,
    cell: dict | None = None,
    bootstrap_n: int = 1000,
    seed: int | None = 0,
) -> ReportData:
    """Aggregate everything the report renders. `cell` optionally pins any of
    task_id / methodology_id / repo_context_id / model / runner; trials (and
    the judgments whose pairs fall inside the scope) are filtered to it."""
    if axis not in AXIS_FIELDS:
        raise ValueError(f"Unknown axis {axis!r}; valid: {sorted(AXIS_FIELDS)}")
    cell = {k: v for k, v in (cell or {}).items() if v}
    field_name = AXIS_FIELDS[axis]

    all_trials = list_trials(conn)
    trials_by_id = {t.id: t for t in all_trials}
    trials = [
        t for t in all_trials
        if all(getattr(t, k) == v for k, v in cell.items())
    ]

    scoped = {t.id for t in trials}
    all_gates = list_gate_results(conn)
    all_costs = list_cost_records(conn)
    gate_results = {tid: g for tid, g in all_gates.items() if tid in scoped}
    cost_records = {tid: c for tid, c in all_costs.items() if tid in scoped}

    trial_ids = scoped if cell else None
    comparisons, n_judgments, n_sessions = judgments_to_comparisons(
        conn, axis, trial_ids, trials_by_id
    )

    strengths = fit_bradley_terry(comparisons) if len(comparisons) >= 3 else {}
    cis = bootstrap_ci(comparisons, n_bootstrap=bootstrap_n, seed=seed) if strengths else {}
    elos = bt_scores_to_elo(strengths) if strengths else {}

    comparison_counts: dict[str, int] = {}
    for a, b, _ in comparisons:
        comparison_counts[a] = comparison_counts.get(a, 0) + 1
        comparison_counts[b] = comparison_counts.get(b, 0) + 1

    values = sorted({getattr(t, field_name) for t in trials} | set(strengths))
    summaries: list[AxisValueSummary] = []
    for v in values:
        vtrials = [t for t in trials if getattr(t, field_name) == v]
        s = AxisValueSummary(value=v, n_trials=len(vtrials))

        gated = [gate_results[t.id] for t in vtrials if t.id in gate_results]
        s.n_gated = len(gated)
        if gated:
            s.gate_pass_rate = sum(1 for g in gated if g.passed) / len(gated)
            for tier in ("compile", "visible", "hidden"):
                verdicts = [getattr(g, f"{tier}_passed") for g in gated]
                known = [x for x in verdicts if x is not None]
                s.tier_pass_rates[tier] = (sum(known) / len(known)) if known else None

        # Cost rollup deliberately includes errored-but-billed trials: any
        # trial with a cost record counts, regardless of gate/error state.
        costs = [cost_records[t.id].usd_equiv for t in vtrials if t.id in cost_records]
        s.total_usd = sum(costs)
        s.mean_usd = (s.total_usd / len(costs)) if costs else None

        s.n_comparisons = comparison_counts.get(v, 0)
        if v in strengths:
            s.bt_strength = strengths[v]
            s.elo = elos.get(v)
            if v in cis:
                lo, _, hi = cis[v]
                s.bt_ci = (lo, hi)
        summaries.append(s)

    frontier = pareto_frontier({
        s.value: (s.mean_usd, s.bt_strength)
        for s in summaries
        if s.mean_usd is not None and s.bt_strength is not None
    })
    for s in summaries:
        s.on_frontier = s.value in frontier

    flags = analyze(trials, gate_results, cost_records, axis=axis)
    picks = stakes_picks(summaries)

    return ReportData(
        axis=axis,
        cell=cell,
        summaries=summaries,
        picks=picks,
        flags=flags,
        n_judgments=n_judgments,
        n_sessions=n_sessions,
    )
