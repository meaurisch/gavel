"""Playwright regression tests for the web UI — every bug from the UI-revamp
feedback gets a live-browser assertion here.

Run with:
    pip install pytest-playwright playwright
    python -m playwright install chromium
    pytest -m integration tests/test_ui_playwright.py

Marked `integration` so the default `pytest` run stays fast and offline.
The suite seeds its own DB, starts a real uvicorn server on a scratch port,
and drives the built frontend (ui/frontend/dist must exist — `cli.py setup`).
"""

from __future__ import annotations

import subprocess
import sys
import time
import urllib.request
from pathlib import Path

import pytest

from core.db import (
    connect,
    insert_cost_record,
    insert_gate_result,
    insert_run_result,
    insert_trial,
)
from core.models import CostRecord, GateResult, RunResult, Trial

pytestmark = pytest.mark.integration

ROOT = Path(__file__).resolve().parent.parent
PORT = 8341
BASE = f"http://127.0.0.1:{PORT}"

TASK = "uitask"
TASK2 = "uitask2"
METHS = ["meth-alpha-x", "meth-beta-y", "meth-gamma-z", "meth-delta-q"]
MODELS = ["model-red-z", "model-blue-w"]
PINNED_CTX = "ctx-pinned"
PINNED_MODEL = "model-pinned"
PINNED_RUNNER = "runner-pinned"
PINNED_METH = "meth-pinned"

N_OLD_LINES = 150
VERY_LONG_LINE = "x" * 600


def _long_diff(marker: str, with_long_line: bool = False) -> str:
    """A single-file diff over a 150-line module: full context, two insertion
    points, so line numbers and three-way alignment are fully checkable."""
    lines = [
        "diff --git a/src/app.py b/src/app.py",
        "--- a/src/app.py",
        "+++ b/src/app.py",
        f"@@ -1,{N_OLD_LINES} +1,{N_OLD_LINES + (3 if with_long_line else 2)} @@",
    ]
    for i in range(1, N_OLD_LINES + 1):
        lines.append(f" original line {i} of the module")
        if i == 10:
            lines.append(f"+inserted after ten by {marker}")
            if with_long_line:
                lines.append(f"+{VERY_LONG_LINE}")
        if i == 100:
            lines.append(f"+second insertion by {marker}")
    return "\n".join(lines) + "\n"


def _seed(conn, trial_id, *, task, meth, ctx, model, runner, rep, diff):
    insert_trial(conn, Trial(id=trial_id, task_id=task, methodology_id=meth,
                             repo_context_id=ctx, model=model, runner=runner, rep=rep))
    insert_run_result(conn, RunResult(trial_id=trial_id, diff=diff, exit_status=0, wall_seconds=42.0))
    insert_gate_result(conn, GateResult(
        trial_id=trial_id, passed=True, compile_passed=True, visible_passed=True,
        hidden_passed=True,
        compile_output=f"build log for {meth} {model} ok",
        visible_output=f"visible: 12 passed ({meth})",
        hidden_output=f"hidden: 7 passed ({meth} on {model} via {runner})",
    ))
    insert_cost_record(conn, CostRecord(
        trial_id=trial_id, native_unit="usd", native_amount=0.25, usd_equiv=0.25,
        input_tokens=5000, output_tokens=800, cache_read_tokens=100,
    ))


def _build_test_db(path: Path) -> None:
    conn = connect(path)
    # Methodology-axis cell: 4 methodologies x 3 reps -> 18 pairs (marathon).
    for meth in METHS:
        for rep in range(3):
            _seed(conn, f"{TASK}-{meth}-r{rep}", task=TASK, meth=meth, ctx=PINNED_CTX,
                  model=PINNED_MODEL, runner=PINNED_RUNNER, rep=rep,
                  diff=_long_diff(meth, with_long_line=(meth == METHS[0])))
    # Model-axis cell on a second task.
    for model in MODELS:
        _seed(conn, f"{TASK2}-{model}", task=TASK2, meth=PINNED_METH, ctx=PINNED_CTX,
              model=model, runner=PINNED_RUNNER, rep=0, diff=_long_diff(model))
    conn.close()


@pytest.fixture(scope="session")
def server(tmp_path_factory):
    dist = ROOT / "ui" / "frontend" / "dist" / "index.html"
    if not dist.is_file():
        pytest.skip("frontend not built — run `python cli.py setup` first")

    db_path = tmp_path_factory.mktemp("uidb") / "uitest.db"
    _build_test_db(db_path)

    proc = subprocess.Popen(
        [sys.executable, "cli.py", "ui", "--db", str(db_path), "--port", str(PORT)],
        cwd=str(ROOT),
        stdout=subprocess.DEVNULL,
        stderr=subprocess.DEVNULL,
    )
    try:
        deadline = time.time() + 30
        while time.time() < deadline:
            try:
                with urllib.request.urlopen(f"{BASE}/api/dbs", timeout=2):
                    break
            except Exception:
                time.sleep(0.3)
        else:
            pytest.fail("UI server did not become ready in 30s")
        yield BASE
    finally:
        proc.kill()
        proc.wait(timeout=10)


def _start_session(page, server, axis: str) -> None:
    """Drive the picker like a user: choose the axis, start the first cell."""
    page.goto(f"{server}/grade")
    page.get_by_test_id(f"axis-{axis}").click()
    page.get_by_test_id("start-session").first.click()
    page.wait_for_url("**/grade/session/**")
    page.wait_for_selector('[data-testid="pane-a"]')


# ---------------------------------------------------------------------------
# Diff screen bugs from the feedback — each gets a measured assertion
# ---------------------------------------------------------------------------

def test_panes_measurably_equal_despite_long_lines(page, server):
    """'the split of the screen is not in the middle' — bounding-rect check.
    Side A's diff contains a 600-char unwrapped line; the panes must still
    split 50/50 and the page must not overflow horizontally."""
    _start_session(page, server, "methodology")
    a = page.locator('[data-testid="pane-a"]').bounding_box()
    b = page.locator('[data-testid="pane-b"]').bounding_box()
    assert a and b
    assert abs(a["width"] - b["width"]) <= 1.0, f"pane widths differ: {a['width']} vs {b['width']}"
    overflow = page.evaluate(
        "() => document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth"
    )
    assert overflow <= 1, f"page overflows horizontally by {overflow}px"


def test_line_numbers_track_scroll(page, server):
    """'line numbers do not change when scrolling' — scroll the pane and
    measure that the number cell sits on the same row as its code line."""
    _start_session(page, server, "methodology")
    pane = page.locator('[data-testid="pane-a"]')

    for scroll in (0, 400, 1200, 2400):
        pane.evaluate("(el, y) => { el.scrollTop = y; }", scroll)
        page.wait_for_timeout(50)
        # Find a code row that's currently visible in the pane's viewport.
        probe = pane.evaluate(
            """(el) => {
              const paneRect = el.getBoundingClientRect();
              const rows = el.querySelectorAll('table.diff tr');
              for (const tr of rows) {
                const r = tr.getBoundingClientRect();
                if (r.top >= paneRect.top + 30 && r.bottom <= paneRect.bottom - 10) {
                  const code = tr.querySelector('td.code');
                  const m = code && code.textContent.match(/^original line (\\d+) of the module$/);
                  if (m) {
                    const oldNo = tr.querySelector('td.lineno').textContent.trim();
                    const codeRect = code.getBoundingClientRect();
                    const numRect = tr.querySelector('td.lineno').getBoundingClientRect();
                    return { contentNo: m[1], gutterNo: oldNo, dy: Math.abs(codeRect.top - numRect.top) };
                  }
                }
              }
              return null;
            }"""
        )
        assert probe is not None, f"no probe row visible at scrollTop={scroll}"
        assert probe["gutterNo"] == probe["contentNo"], (
            f"at scrollTop={scroll}, line number {probe['gutterNo']} sits next to "
            f"content line {probe['contentNo']}"
        )
        assert probe["dy"] < 2, "line-number cell not on the same row as its code"


def test_sync_scroll_locks_panes(page, server):
    _start_session(page, server, "methodology")
    page.locator('[data-testid="pane-a"]').evaluate("(el) => { el.scrollTop = 800; el.dispatchEvent(new Event('scroll')); }")
    page.wait_for_timeout(200)
    b_top = page.locator('[data-testid="pane-b"]').evaluate("(el) => el.scrollTop")
    assert abs(b_top - 800) <= 2, f"pane B did not follow (scrollTop={b_top})"


def test_three_way_view_renders_aligned_rows(page, server):
    """'the option to have a three-way split screen: original | A | B'."""
    _start_session(page, server, "methodology")
    page.get_by_test_id("view-three").click()
    page.wait_for_selector('[data-testid="threeway-file"]')

    result = page.evaluate(
        """() => {
          const t = document.querySelector('[data-testid="threeway-file"]');
          const rows = Array.from(t.querySelectorAll('tbody tr'));
          const insRow = rows.find(r => r.textContent.includes('inserted after ten by'));
          if (!insRow) return { error: 'insertion row not found', nRows: rows.length };
          const prev = insRow.previousElementSibling;
          const prevOrigNo = prev ? prev.querySelector('td.lineno').textContent.trim() : null;
          const cells = insRow.querySelectorAll('td');
          return {
            nRows: rows.length,
            prevOrigNo,
            origCellEmpty: cells[1].textContent.trim() === '',
            headers: Array.from(t.querySelectorAll('thead tr:last-child th')).map(th => th.textContent.trim()),
          };
        }"""
    )
    assert "error" not in result, str(result)
    assert result["nRows"] > 100  # full context renders, not a stub
    assert result["headers"] == ["Original", "A", "B"]
    # The insertion is anchored right after original line 10.
    assert result["prevOrigNo"] == "10"
    # An added line has no original counterpart.
    assert result["origCellEmpty"]
    # Two-way view still available (the current view must not be removed).
    page.get_by_test_id("view-two").click()
    page.wait_for_selector('[data-testid="pane-a"]')


# ---------------------------------------------------------------------------
# Gate detail + metrics during comparison
# ---------------------------------------------------------------------------

def test_gate_detail_and_metrics_visible_during_comparison(page, server):
    """'far more info than only the check marks' — tier logs + cost/tokens/
    wall-time are on the comparison screen (methodology axis)."""
    _start_session(page, server, "methodology")
    assert page.get_by_test_id("metrics-A").inner_text() != ""
    assert "$" in page.get_by_test_id("metrics-A").inner_text()
    page.get_by_test_id("log-A-hidden").click()
    log_text = page.locator('[data-testid="side-header-A"] details pre').last.inner_text()
    assert "hidden: 7 passed" in log_text
    # ids in logs are redacted
    for forbidden in METHS:
        assert forbidden not in log_text


def test_metrics_hidden_on_model_axis(page, server):
    _start_session(page, server, "model")
    assert page.get_by_test_id("metrics-hidden-A").count() == 1
    assert page.get_by_test_id("metrics-A").count() == 0


# ---------------------------------------------------------------------------
# Blind-grading invariant, on the rendered page, per axis
# ---------------------------------------------------------------------------

@pytest.mark.parametrize("axis,varying,pinned_visible", [
    ("methodology", METHS, [TASK, PINNED_CTX, PINNED_MODEL, PINNED_RUNNER]),
    ("model", MODELS, [TASK2, PINNED_CTX, PINNED_METH, PINNED_RUNNER]),
])
def test_blinding_no_varying_axis_id_anywhere(page, server, axis, varying, pinned_visible):
    """THE invariant: during comparison, no raw id of ANY value of the varying
    axis appears anywhere in the rendered page (including collapsed details).
    Checked against the full DOM HTML, both view modes."""
    _start_session(page, server, axis)

    for view in ("two", "three"):
        page.get_by_test_id(f"view-{view}").click()
        page.wait_for_timeout(600)  # three-way fetches originals
        html = page.content()
        for vid in varying:
            assert vid not in html, f"{axis} value {vid!r} leaked into the {view}-way page"

    # Sanity: the page isn't blank — pinned ids are allowed and present.
    html = page.content()
    for pid in pinned_visible:
        assert pid in html


# ---------------------------------------------------------------------------
# Picker: everything up front + hover previews
# ---------------------------------------------------------------------------

def test_picker_shows_all_axes_and_hover_preview(page, server):
    page.goto(f"{server}/grade")
    page.wait_for_selector('[data-testid="axis-picker"]')
    # All four comparison axes are visible immediately, with cell counts.
    for axis in ("methodology", "model", "repo_context", "runner"):
        assert page.get_by_test_id(f"axis-{axis}").count() == 1
    # The five-axis catalog is on the same page — nothing hidden behind a pick.
    page.wait_for_selector('[data-testid="catalog-reference"]')
    ref = page.get_by_test_id("catalog-reference")
    assert ref.count() == 1
    text = ref.inner_text()
    for expected in ("Tasks", "Methodologies", "Repo contexts", "Models", "Runners"):
        assert expected in text

    # Hover preview on a real local task id shows its instruction.
    chip = ref.get_by_text("moreiter-A", exact=True).first
    chip.hover()
    page.wait_for_selector(".preview-card")
    preview = page.locator(".preview-card").first.inner_text()
    assert "running aggregates" in preview  # from tasks/moreiter-A/task.yaml
    assert "medium" in preview


def test_cell_rows_show_pinned_values_with_previews(page, server):
    page.goto(f"{server}/grade")
    page.get_by_test_id("axis-methodology").click()
    row = page.get_by_test_id("cell-row").first
    text = row.inner_text()
    for pid in (TASK, PINNED_CTX, PINNED_MODEL, PINNED_RUNNER):
        assert pid in text
    # varying values are NOT shown in the picker rows (only a count)
    for meth in METHS:
        assert meth not in text


# ---------------------------------------------------------------------------
# Marathon: judge 18 pairs back-to-back with the keyboard, reload mid-way
# ---------------------------------------------------------------------------

def test_marathon_keyboard_session_with_reload(page, server):
    _start_session(page, server, "methodology")
    url = page.url
    total = int(page.get_by_test_id("pair-progress").inner_text().split("/")[1].split("·")[0].strip())
    assert total >= 10, f"expected a long session, got {total} pairs"

    keys = ["a", "b", "t"]
    half = total // 2
    for i in range(half):
        page.keyboard.press(keys[i % 3])
        page.wait_for_function(
            f"() => document.querySelector('[data-testid=\"pair-progress\"]').textContent.includes('{i + 1} judged')"
        )

    # Reload mid-session: nothing may be lost.
    page.goto(url)
    page.wait_for_selector('[data-testid="pair-progress"]')
    assert f"{half} judged" in page.get_by_test_id("pair-progress").inner_text()

    for i in range(half, total):
        page.keyboard.press(keys[i % 3])
        if i < total - 1:
            page.wait_for_function(
                f"() => document.querySelector('[data-testid=\"pair-progress\"]').textContent.includes('{i + 1} judged')"
            )

    # After the last judgment the app moves to the reveal CONFIRM screen —
    # revealing is irreversible, so it takes one explicit click.
    page.wait_for_url("**/reveal**", timeout=10000)
    page.wait_for_selector('[data-testid="reveal-confirm"]')
    page.get_by_test_id("confirm-reveal").click()
    page.wait_for_selector('[data-testid="reveal-pairs"]')
    reveal = page.locator('[data-testid="reveal-pairs"]').inner_text()
    for meth in METHS:  # now (and only now) values are revealed
        assert meth in reveal


def test_reveal_needs_confirmation_then_closes_session(page, server):
    """Landing on the reveal URL mid-session (URL autocomplete, a slipped
    keystroke) must NOT close the session — it shows a confirmation step and
    leaks nothing. Only the explicit confirm closes it, unblinds the judged
    pairs, and disables further judging."""
    _start_session(page, server, "methodology")
    session_url = page.url
    page.keyboard.press("a")
    page.wait_for_function(
        "() => document.querySelector('[data-testid=\"pair-progress\"]').textContent.includes('1 judged')"
    )

    # Bare navigation → confirm screen; session stays open, nothing unblinded.
    page.goto(session_url.rstrip("/") + "/reveal")
    page.wait_for_selector('[data-testid="reveal-confirm"]')
    assert page.locator('[data-testid="reveal-pairs"]').count() == 0
    html = page.content()
    for meth in METHS:
        assert meth not in html, "confirm screen must not leak axis values"

    # Going back, the session is still judgeable.
    page.goto(session_url)
    page.wait_for_selector('[data-testid="judge-bar"]')
    page.keyboard.press("b")
    page.wait_for_function(
        "() => document.querySelector('[data-testid=\"pair-progress\"]').textContent.includes('2 judged')"
    )

    # Explicit confirm closes the session and unblinds ONLY the judged pairs.
    page.goto(session_url.rstrip("/") + "/reveal")
    page.wait_for_selector('[data-testid="reveal-confirm"]')
    page.get_by_test_id("confirm-reveal").click()
    page.wait_for_selector('[data-testid="session-closed-note"]')
    assert "stayed blind" in page.get_by_test_id("session-closed-note").inner_text()
    assert page.locator('[data-testid="reveal-pairs"] tbody tr').count() == 2

    page.goto(session_url)
    page.wait_for_selector('[data-testid="session-closed-bar"]')
    assert page.get_by_test_id("judge-bar").count() == 0
    before = page.get_by_test_id("pair-progress").inner_text()
    page.keyboard.press("a")
    page.wait_for_timeout(400)
    assert page.get_by_test_id("pair-progress").inner_text() == before, "judgment accepted after reveal"


# ---------------------------------------------------------------------------
# Run launcher spend gate (never launches anything paid)
# ---------------------------------------------------------------------------

def test_spend_gate_blocks_paid_runner(page, server):
    page.goto(f"{server}/runs")
    page.wait_for_selector('[data-testid="runner-select"]')
    page.get_by_test_id("runner-select").select_option("claude-code")
    page.get_by_test_id("model-input").fill("claude-haiku-4-5")
    page.get_by_test_id("plan-run").click()
    page.wait_for_selector('[data-testid="spend-gate"]')

    start = page.get_by_test_id("start-run")
    assert start.is_disabled(), "paid launch must be disabled without the phrase"
    page.get_by_test_id("confirm-phrase").fill("WRONG")
    assert start.is_disabled(), "wrong phrase must not enable the launch"
    page.get_by_test_id("confirm-phrase").fill("SPEND")
    assert start.is_enabled()
    # Never click start here — this suite must not spend money. The backend
    # refusal path (409 without the phrase) is covered by fast API tests.


def test_free_runner_needs_no_gate(page, server):
    page.goto(f"{server}/runs")
    page.wait_for_selector('[data-testid="runner-select"]')
    page.get_by_test_id("runner-select").select_option("nop")
    page.get_by_test_id("model-input").fill("self-test")
    page.get_by_test_id("plan-run").click()
    page.wait_for_selector('[data-testid="plan-preview"]')
    assert page.get_by_test_id("spend-gate").count() == 0
    assert page.get_by_test_id("start-run").is_enabled()


# ---------------------------------------------------------------------------
# Unified entry point
# ---------------------------------------------------------------------------

def test_dashboard_links_every_area(page, server):
    page.goto(server)
    page.wait_for_selector('[data-testid="active-db"]')
    for path in ("/grade", "/runs", "/browse", "/report"):
        assert page.locator(f'a[href="{path}"]').count() >= 1, f"dashboard missing link to {path}"
    # Readiness summary reflects the seeded DB (async fetch — wait for it).
    page.wait_for_function(
        "() => document.querySelector('[data-testid=\"active-db\"]').textContent.includes('trials')"
    )
    assert "trials" in page.get_by_test_id("active-db").inner_text()
