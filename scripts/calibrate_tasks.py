"""
Per-task pass-rate calibration for setup-bench.

Reads a results database and reports each task's pass rate across all
methodologies and reps, with a difficulty band and ceiling/floor warnings.
This is a read-only analysis tool — it never modifies the database or tasks.

Difficulty bands (research §4, 30-70% discriminative window):
  easy   : pass rate > 70%   (sanity check; weak discrimination)
  medium : 30%-70%           (maximum discriminative power)
  hard   : pass rate < 30%   (may test the base agent, not the methodology)

Usage:
    python scripts/calibrate_tasks.py --db results.db
"""

import argparse
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.db import connect, get_gate_result, list_trials  # noqa: E402

CEILING = 0.70
FLOOR = 0.30


def task_pass_counts(conn) -> dict[str, tuple[int, int]]:
    """Return {task_id: (passed, total)} across all trials that have a gate result."""
    passed: dict[str, int] = {}
    total: dict[str, int] = {}
    for trial in list_trials(conn):
        gr = get_gate_result(conn, trial.id)
        if gr is None:
            continue
        total[trial.task_id] = total.get(trial.task_id, 0) + 1
        if gr.passed:
            passed[trial.task_id] = passed.get(trial.task_id, 0) + 1
    return {tid: (passed.get(tid, 0), total[tid]) for tid in total}


def classify(rate: float) -> tuple[str, str | None]:
    """Map a pass rate in [0, 1] to (difficulty_label, warning_or_None)."""
    if rate > CEILING:
        return "easy", "pass rate >70%, may not discriminate between methodologies"
    if rate < FLOOR:
        return "hard", "pass rate <30%, may be testing the base agent, not the methodology"
    return "medium", None


def format_report(stats: dict[str, tuple[int, int]]) -> str:
    lines = ["Task Pass Rates (across all methodologies and reps):"]
    recs: list[str] = []
    for task_id in sorted(stats):
        p, n = stats[task_id]
        rate = p / n if n else 0.0
        label, warning = classify(rate)
        if warning is None:
            note = f"[{label} - good discriminative power]"
        else:
            effect = "ceiling" if rate > CEILING else "floor"
            note = f"[WARNING: {effect} effect - {label}]"
        lines.append(f"  {task_id}:  {rate:.0%} ({p}/{n})   {note}")
        if warning is not None:
            recs.append(f"  - {task_id}: {warning}")
    if recs:
        lines.append("")
        lines.append("Recommendations:")
        lines.extend(recs)
    return "\n".join(lines)


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Per-task pass-rate calibration (read-only)."
    )
    parser.add_argument(
        "--db", type=Path, default=Path("results.db"),
        help="Path to the results database (default: results.db).",
    )
    args = parser.parse_args()

    if not args.db.exists():
        print(f"error: database not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    conn = connect(args.db)
    stats = task_pass_counts(conn)
    if not stats:
        print(f"No trials with gate results found in {args.db}.")
        sys.exit(0)
    print(format_report(stats))


if __name__ == "__main__":
    main()
