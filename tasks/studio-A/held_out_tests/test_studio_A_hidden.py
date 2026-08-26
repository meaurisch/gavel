"""Hidden FAIL_TO_PASS tests for studio-A: ledger CSV export flattens the
`detail` column to a single capped line (studio_worker/ledger.py::export_csv).

Implementation-agnostic: exercises only the public Ledger API and the exported
CSV bytes — behaviour the instruction states, nothing about how it is done.
"""
import csv

from studio_worker.ledger import Ledger


def _data_rows(path):
    with open(path, newline="", encoding="utf-8") as f:
        rows = list(csv.reader(f))
    return rows[1:]  # drop header


def test_multiline_overlong_detail_exports_as_single_capped_line(tmp_path):
    lg = Ledger(tmp_path / "state.db")
    tail = "\n".join(
        f"FAILED tests/test_mod.py::test_case_{i} - AssertionError: boom" for i in range(40)
    )
    assert "\n" in tail and len(tail) > 200  # the premise of the task
    lg.record("implement_attempt", outcome="check-failed", detail=tail)

    reported = lg.export_csv(tmp_path / "ledger.csv")
    rows = _data_rows(tmp_path / "ledger.csv")

    assert reported == 1 and len(rows) == 1  # row count preserved
    cell = rows[0][-1]
    assert "\n" not in cell and "\r" not in cell  # single line
    assert len(cell) <= 201  # capped at 200 (ellipsis may sit at or after the cap)
    assert cell.endswith("…")  # truncation is marked with an ellipsis


def test_short_single_line_detail_roundtrips_unchanged(tmp_path):
    lg = Ledger(tmp_path / "state.db")
    lg.record("cycle", outcome="ok", detail="comment=1234 handled")

    lg.export_csv(tmp_path / "ledger.csv")
    rows = _data_rows(tmp_path / "ledger.csv")

    assert rows[0][-1] == "comment=1234 handled"


def test_row_count_preserved_across_mixed_details(tmp_path):
    lg = Ledger(tmp_path / "state.db")
    lg.record("a", detail="short")
    lg.record("b", detail="x" * 500)
    lg.record("c")  # detail defaults to empty

    reported = lg.export_csv(tmp_path / "ledger.csv")
    rows = _data_rows(tmp_path / "ledger.csv")

    assert reported == 3 and len(rows) == 3
    assert rows[0][-1] == "short"
    assert len(rows[1][-1]) <= 201 and rows[1][-1].endswith("…")
