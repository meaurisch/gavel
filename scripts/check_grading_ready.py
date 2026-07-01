"""
Pre-flight check: how much gradeable data exists in results.db, per axis.

Read-only diagnostic mirroring the /api/grading-status endpoint the grading UI
uses for its empty state. Exits 1 when every axis has zero gradeable cells
(nothing gradeable yet), so it can gate a Phase J run before trials are burned.

Usage:
    python scripts/check_grading_ready.py --db results.db
"""

import argparse
import logging
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT))

from core.db import connect, grading_readiness  # noqa: E402

log = logging.getLogger("check_grading_ready")


def format_report(data: dict) -> str:
    """Render the per-axis readiness table plus the total passer count."""
    lines = [
        f"Hidden-gate passers (total): {data['total_hidden_gate_passers']}",
        "",
        f"{'axis':14s}{'distinct passing values':28s}{'gradeable cells':16s}",
    ]
    for axis in sorted(data["axes"]):
        info = data["axes"][axis]
        lines.append(
            f"{axis:14s}{info['distinct_passing_values']:<28d}{info['gradeable_cells']:<16d}"
        )
    return "\n".join(lines)


def is_ready(data: dict) -> bool:
    """True iff at least one axis has a gradeable cell."""
    return any(info["gradeable_cells"] > 0 for info in data["axes"].values())


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Pre-flight check for grading readiness (read-only).",
        epilog="Example: python scripts/check_grading_ready.py --db results.db",
    )
    parser.add_argument(
        "--db", type=Path, default=Path("results.db"),
        help="Path to the results database (default: results.db).",
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    if not args.db.exists():
        print(f"error: database not found: {args.db}", file=sys.stderr)
        sys.exit(1)

    conn = connect(args.db)
    data = grading_readiness(conn)
    print(format_report(data))

    if not is_ready(data):
        print("\nNot grading-ready: every axis has 0 gradeable cells.", file=sys.stderr)
        sys.exit(1)

    sys.exit(0)


if __name__ == "__main__":
    main()
