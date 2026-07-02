from pathlib import Path

from typer.testing import CliRunner

from core.db import connect
from grading.aggregate import build_report
from grading.report_html import render_pareto_svg, render_report_html
from tests.test_aggregate import _judge, _seed, _session, rich_db  # noqa: F401 (fixture)


def test_render_report_html_smoke(rich_db):  # noqa: F811
    data = build_report(rich_db, "methodology", bootstrap_n=50)
    html = render_report_html(data, generated_at="2026-07-02 00:00 UTC")

    assert "<svg" in html
    for value in ("alpha", "beta", "gamma"):
        assert value in html
    assert "quality pick" in html
    assert "budget pick" in html
    assert "Pareto frontier" in html
    # self-contained: no external fetches
    assert "http://" not in html.replace("http://www.w3.org", "")
    assert "https://" not in html


def test_render_pareto_svg_empty_state(tmp_path):
    conn = connect(tmp_path / "e.db")
    data = build_report(conn, "methodology")
    svg = render_pareto_svg(data)
    assert "<svg" not in svg
    assert "No plottable points" in svg


def test_render_html_escapes_values(tmp_path):
    conn = connect(tmp_path / "x.db")
    _seed(conn, "t1", "<script>alert(1)</script>")
    data = build_report(conn, "methodology")
    html = render_report_html(data)
    assert "<script>alert(1)</script>" not in html
    assert "&lt;script&gt;" in html


def test_report_cli_end_to_end(rich_db, tmp_path):  # noqa: F811
    # rich_db's connection points at a file under its own tmp dir; find it.
    db_path = Path(rich_db.execute("PRAGMA database_list").fetchone()["file"])
    from cli import app

    runner = CliRunner()
    out_dir = tmp_path / "reports"
    result = runner.invoke(app, [
        "report", "--axis", "methodology",
        "--db", str(db_path), "--out-dir", str(out_dir),
    ])
    assert result.exit_code == 0, result.output
    # Rich table content wraps unpredictably at test-terminal width; assert on
    # the plain summary lines instead.
    assert "High-stakes pick:" in result.output
    assert "alpha" in result.output
    written = list(out_dir.glob("report-methodology-*.html"))
    assert len(written) == 1
    assert "<svg" in written[0].read_text(encoding="utf-8")


def test_report_cli_unknown_axis(tmp_path):
    from cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["report", "--axis", "flavor", "--db", str(tmp_path / "missing.db")])
    assert result.exit_code == 2


def test_report_cli_missing_db(tmp_path):
    from cli import app

    runner = CliRunner()
    result = runner.invoke(app, ["report", "--db", str(tmp_path / "missing.db")])
    assert result.exit_code == 2
