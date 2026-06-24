"""Analyzer heuristics — surface tasks/axis-values that need attention.

Keyed by the comparison-axis value (methodology / model / repo_context / runner).
Flags three things, following the skill-creator heuristics:
  - non-discriminating tasks (every axis value passes, or every value fails)
  - flaky tasks (some axis value passes between 20% and 80% of its reps)
  - cost/quality notes (an expensive value that performs no better than a cheap one)
"""

from collections import defaultdict
from dataclasses import dataclass, field

from core.models import Trial, GateResult, CostRecord
from grading.pairwise import AXIS_FIELDS

# A value "passes" the cell if it succeeds on a majority of its reps.
_PASS_THRESHOLD = 0.5
# Flaky band: pass rates strictly inside this range are unreliable.
_FLAKY_LOW = 0.2
_FLAKY_HIGH = 0.8
# Pass rates within this delta are "similar" for the cost/quality check.
_SIMILAR_PASS_DELTA = 0.1
# Expensive must cost at least this multiple of cheap to bother flagging.
_COST_RATIO = 2.0


@dataclass
class AnalyzerFlags:
    non_discriminating_tasks: list[str] = field(default_factory=list)
    flaky_tasks: list[str] = field(default_factory=list)
    cost_quality_notes: list[str] = field(default_factory=list)


def _pass_rates_by_value(
    trials: list[Trial],
    gate_results: dict[str, GateResult],
    field_name: str,
) -> dict[tuple[str, str], float]:
    """Pass rate across reps, keyed by (task_id, axis_value)."""
    passed: dict[tuple[str, str], int] = defaultdict(int)
    total: dict[tuple[str, str], int] = defaultdict(int)
    for t in trials:
        key = (t.task_id, getattr(t, field_name))
        gr = gate_results.get(t.id)
        if gr is None:
            continue
        total[key] += 1
        if gr.passed:
            passed[key] += 1
    return {k: passed[k] / total[k] for k in total}


def analyze(
    trials: list[Trial],
    gate_results: dict[str, GateResult],
    cost_records: dict[str, CostRecord],
    axis: str = "methodology",
) -> AnalyzerFlags:
    field_name = AXIS_FIELDS[axis]
    rates = _pass_rates_by_value(trials, gate_results, field_name)

    # Group pass rates by task.
    rates_by_task: dict[str, dict[str, float]] = defaultdict(dict)
    for (task_id, value), rate in rates.items():
        rates_by_task[task_id][value] = rate

    non_discriminating: list[str] = []
    flaky: list[str] = []
    for task_id, value_rates in rates_by_task.items():
        values = list(value_rates.values())
        if all(r == 1.0 for r in values) or all(r == 0.0 for r in values):
            non_discriminating.append(task_id)
        if any(_FLAKY_LOW < r < _FLAKY_HIGH for r in values):
            flaky.append(task_id)

    cost_quality = _cost_quality_notes(trials, gate_results, cost_records, field_name)

    return AnalyzerFlags(
        non_discriminating_tasks=sorted(set(non_discriminating)),
        flaky_tasks=sorted(set(flaky)),
        cost_quality_notes=cost_quality,
    )


def _cost_quality_notes(
    trials: list[Trial],
    gate_results: dict[str, GateResult],
    cost_records: dict[str, CostRecord],
    field_name: str,
) -> list[str]:
    # Aggregate mean cost and overall pass rate per axis value (across tasks).
    cost_sum: dict[str, float] = defaultdict(float)
    cost_n: dict[str, int] = defaultdict(int)
    passed: dict[str, int] = defaultdict(int)
    total: dict[str, int] = defaultdict(int)
    for t in trials:
        value = getattr(t, field_name)
        cr = cost_records.get(t.id)
        if cr is not None:
            cost_sum[value] += cr.usd_equiv
            cost_n[value] += 1
        gr = gate_results.get(t.id)
        if gr is not None:
            total[value] += 1
            if gr.passed:
                passed[value] += 1

    # Only consider values that reliably pass and have a known mean cost.
    candidates = {
        v: cost_sum[v] / cost_n[v]
        for v in cost_n
        if cost_n[v] > 0
        and total.get(v, 0) > 0
        and passed[v] / total[v] >= _PASS_THRESHOLD
    }
    if len(candidates) < 2:
        return []

    cheapest = min(candidates, key=candidates.get)
    priciest = max(candidates, key=candidates.get)
    if cheapest == priciest:
        return []

    cheap_rate = passed[cheapest] / total[cheapest]
    pricey_rate = passed[priciest] / total[priciest]
    cheap_cost = candidates[cheapest]
    pricey_cost = candidates[priciest]

    notes: list[str] = []
    if (
        abs(pricey_rate - cheap_rate) <= _SIMILAR_PASS_DELTA
        and pricey_cost >= _COST_RATIO * cheap_cost
    ):
        notes.append(
            f"{priciest} costs ~${pricey_cost:.2f} vs {cheapest} at ~${cheap_cost:.2f} "
            f"for a similar pass rate ({pricey_rate:.0%} vs {cheap_rate:.0%}) — "
            f"the extra cost may not be justified."
        )
    return notes
