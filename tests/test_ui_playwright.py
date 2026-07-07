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
    insert_grading_session,
    insert_judgment,
    insert_run_result,
    insert_trial,
)
from core.models import CostRecord, GateResult, GradingSession, Judgment, RunResult, Trial

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
    """A two-file diff: a 150-line module with full context and two insertion
    points (line numbers + three-way alignment checkable), plus a small
    second file so the file navigator has something to jump to."""
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
    lines += [
        "diff --git a/src/zz_extra.py b/src/zz_extra.py",
        "new file mode 100644",
        "--- /dev/null",
        "+++ b/src/zz_extra.py",
        "@@ -0,0 +1,2 @@",
        "+# the second file",
        "+EXTRA = True",
    ]
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
    # Every diff carries a 600-char unwrapped line so any sampled pair
    # exercises horizontal overflow (pane equality + sticky gutters).
    for meth in METHS:
        for rep in range(3):
            _seed(conn, f"{TASK}-{meth}-r{rep}", task=TASK, meth=meth, ctx=PINNED_CTX,
                  model=PINNED_MODEL, runner=PINNED_RUNNER, rep=rep,
                  diff=_long_diff(meth, with_long_line=True))
    # Model-axis cell on a second task.
    for model in MODELS:
        _seed(conn, f"{TASK2}-{model}", task=TASK2, meth=PINNED_METH, ctx=PINNED_CTX,
              model=model, runner=PINNED_RUNNER, rep=0, diff=_long_diff(model))

    # A pre-revealed llm session whose rationale carries an unbroken 150-char
    # identifier and a truncated-diff verdict — the reveal page must wrap it
    # inside the cell (no table-wide horizontal scroll) and show the badge.
    insert_grading_session(conn, GradingSession(
        id="revealed-llm", axis="model", cell={
            "task_id": TASK2, "methodology_id": PINNED_METH,
            "repo_context_id": PINNED_CTX, "runner": PINNED_RUNNER},
        pairs=[(f"{TASK2}-{MODELS[0]}", f"{TASK2}-{MODELS[1]}")],
        created_at="2026-07-07T00:00:00Z", revealed_at="2026-07-07T01:00:00Z",
        mode="llm", judge_provider="mock", judge_model="mock-judge", judge_passes=2,
    ))
    insert_judgment(conn, Judgment(
        id="revealed-llm-j0", session_id="revealed-llm", task_id=TASK2, model="",
        left_trial_id=f"{TASK2}-{MODELS[0]}", right_trial_id=f"{TASK2}-{MODELS[1]}",
        choice="A", rubric_correctness="A", rubric_minimality="tie",
        rubric_readability="A", rubric_overengineering="tie",
        created_at="2026-07-07T00:30:00Z", grader="llm:mock:mock-judge",
        rationale=("Solution A keeps the pipeline single-pass and avoids the "
                   "speculative registry. See the unbroken identifier "
                   + "SupercalifragilisticWindowedAggregationCoordinator" * 3
                   + " which must wrap inside the cell rather than stretch "
                     "the table into horizontal scroll."),
        confidence=0.8, position_consistent=True, truncated=True,
    ))
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


def test_gutter_stays_pinned_under_horizontal_scroll(page, server):
    """Line numbers and change markers must stay visible while long lines
    scroll horizontally inside a pane (sticky gutter)."""
    _start_session(page, server, "methodology")
    probe = page.evaluate(
        """() => {
          // find whichever pane actually has horizontal overflow (the
          // side with the 600-char line is randomized between A and B)
          const panes = [...document.querySelectorAll('[data-testid="pane-a"],[data-testid="pane-b"]')];
          const pane = panes.find(p => p.scrollWidth > p.clientWidth + 10);
          if (!pane) return { error: 'no pane with horizontal overflow' };
          pane.scrollLeft = 400;
          const paneRect = pane.getBoundingClientRect();
          const rows = [...pane.querySelectorAll('table.diff tr.add, table.diff tr.context')];
          const mid = rows[Math.floor(rows.length / 2)];
          const lineno = mid.querySelector('td.lineno');
          const marker = mid.querySelector('td.marker');
          return {
            scrolled: pane.scrollLeft,
            linenoLeft: lineno.getBoundingClientRect().left - paneRect.left,
            markerRight: marker.getBoundingClientRect().right - paneRect.left,
            paneWidth: paneRect.width,
          };
        }"""
    )
    assert "error" not in probe, str(probe)
    assert probe["scrolled"] > 100, "pane did not scroll horizontally"
    # Gutter pinned at the pane's left edge, fully inside the pane.
    assert -1 <= probe["linenoLeft"] <= 3, f"line numbers scrolled away: {probe}"
    assert 0 < probe["markerRight"] < probe["paneWidth"], f"marker off-screen: {probe}"

    # File-header label and @@ hunk text stay readable too (pass-10 finding).
    headers = page.evaluate(
        """() => {
          const panes = [...document.querySelectorAll('[data-testid="pane-a"],[data-testid="pane-b"]')];
          const pane = panes.find(p => p.scrollWidth > p.clientWidth + 10);
          const paneL = pane.getBoundingClientRect().left;
          return {
            header: pane.querySelector('.diff-file-inner').getBoundingClientRect().left - paneL,
            hunk: pane.querySelector('tr.hunk .hunk-inner').getBoundingClientRect().left - paneL,
            paneW: pane.clientWidth,
          };
        }"""
    )
    assert 0 <= headers["header"] < headers["paneW"] / 2, f"file header scrolled away: {headers}"
    assert 0 <= headers["hunk"] < headers["paneW"] / 2, f"hunk header scrolled away: {headers}"


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

def test_gate_detail_visible_but_no_spend_metrics(page, server):
    """'far more info than only the check marks' — tier logs are on the
    comparison screen; cost/tokens/time are NOT (they bias blind judgment —
    user decision 2026-07-05) on any axis."""
    _start_session(page, server, "methodology")
    page.get_by_test_id("log-A-hidden").click()
    log_text = page.locator('[data-testid="side-header-A"] details pre').last.inner_text()
    assert "hidden: 7 passed" in log_text
    # ids in logs are redacted
    for forbidden in METHS:
        assert forbidden not in log_text
    # no dollar/token readouts anywhere in the side headers, on either axis
    for axis in ("methodology", "model"):
        _start_session(page, server, axis)
        for label in ("A", "B"):
            header = page.get_by_test_id(f"side-header-{label}").inner_text()
            assert "$" not in header, f"spend metric leaked into {axis} side header"
            assert page.get_by_test_id(f"metrics-hidden-{label}").count() == 1


def test_file_navigator_jumps_both_panes(page, server):
    """Multi-file diffs get a file navigator that scrolls every pane to the
    chosen file."""
    _start_session(page, server, "methodology")
    page.wait_for_selector('[data-testid="file-nav"]')
    items = page.locator('[data-testid="file-nav-item"]')
    assert items.count() == 2

    # Jump to the last file (below 150 lines of app.py): panes must scroll and
    # the file header must be visible in the pane viewport. The pane may clamp
    # at max scroll for a short trailing file — visibility is the contract.
    items.last.click()
    page.wait_for_timeout(150)
    probe = page.evaluate(
        """() => {
          const out = {};
          for (const id of ['pane-a', 'pane-b']) {
            const pane = document.querySelector(`[data-testid="${id}"]`);
            const paneRect = pane.getBoundingClientRect();
            const t = pane.querySelector('[data-file="src/zz_extra.py"]').getBoundingClientRect();
            out[id] = { scrolled: pane.scrollTop,
                        visible: t.top >= paneRect.top - 2 && t.top < paneRect.bottom - 40 };
          }
          return out;
        }"""
    )
    for pane_id, r in probe.items():
        assert r["scrolled"] > 100, f"{pane_id} did not scroll: {r}"
        assert r["visible"], f"{pane_id} target file not visible after jump: {r}"

    # Jump back to the first file: this one CAN reach the pane top exactly —
    # in BOTH panes (pixel-sync mirroring must not clobber either pane's own
    # target offset; wait past the 60ms sync-suppression window).
    items.first.click()
    page.wait_for_timeout(250)
    back = page.evaluate(
        """() => {
          const out = {};
          for (const id of ['pane-a', 'pane-b']) {
            const pane = document.querySelector(`[data-testid="${id}"]`);
            const t = pane.querySelector('[data-file="src/app.py"]').getBoundingClientRect();
            out[id] = Math.abs(t.top - pane.getBoundingClientRect().top);
          }
          return out;
        }"""
    )
    for pane_id, delta in back.items():
        assert delta < 5, f"{pane_id} first-file jump not at pane top: {back}"


def test_open_log_expander_takes_full_row(page, server):
    """With THREE logboxes per side (the real-trial case that demo data
    hides), an opened one must claim the full card width — pass 10 found an
    inline flex style silently defeating the stylesheet rule."""
    _start_session(page, server, "methodology")
    page.get_by_test_id("log-A-compile").click()
    page.wait_for_timeout(150)
    probe = page.evaluate(
        """() => {
          const card = document.querySelector('[data-testid="side-header-A"]');
          const open = card.querySelector('details.logbox[open]');
          const boxes = card.querySelectorAll('details.logbox').length;
          return {
            boxes,
            cardW: card.getBoundingClientRect().width,
            openW: open.getBoundingClientRect().width,
          };
        }"""
    )
    assert probe["boxes"] == 3, f"fixture must have 3 logboxes, got {probe['boxes']}"
    assert probe["openW"] > probe["cardW"] * 0.9, f"open log not full-width: {probe}"


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


def test_plan_invalidated_when_selection_changes(page, server):
    """An armed (or merely previewed) plan must die when any parameter
    changes — a stale plan offering the old trial count is a footgun."""
    page.goto(f"{server}/runs")
    page.wait_for_selector('[data-testid="runner-select"]')
    page.get_by_test_id("runner-select").select_option("nop")
    page.get_by_test_id("model-input").fill("self-test")
    page.get_by_test_id("plan-run").click()
    page.wait_for_selector('[data-testid="plan-preview"]')

    # First click arms the free confirm (does NOT launch).
    page.get_by_test_id("start-run").click()
    page.wait_for_timeout(150)
    assert "Confirm — write" in page.get_by_test_id("start-run").inner_text()

    # Change the selection: the whole plan (and the armed confirm) must go.
    page.locator('[data-testid^="pick-task-"]').first.click()
    page.wait_for_timeout(200)
    assert page.get_by_test_id("plan-preview").count() == 0, "stale plan survived a selection change"
    assert page.get_by_test_id("start-run").count() == 0


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

# ---------------------------------------------------------------------------
# LLM judge mode (mode 2 of grading — zero-spend mock provider throughout)
# ---------------------------------------------------------------------------

import json


def _api_json(server: str, path: str, body: dict | None = None) -> dict | list:
    req = urllib.request.Request(
        f"{server}{path}",
        data=json.dumps(body).encode() if body is not None else None,
        headers={"Content-Type": "application/json"} if body is not None else {},
        method="POST" if body is not None else "GET",
    )
    with urllib.request.urlopen(req, timeout=10) as resp:
        return json.loads(resp.read().decode())


_MODEL_CELL = {
    "axis": "model", "task": TASK2, "methodology": PINNED_METH,
    "repo_context": PINNED_CTX, "runner": PINNED_RUNNER,
}


def _run_mock_judge(server: str, passes: int = 2) -> dict:
    """Create + finish an llm session on the model-axis cell via the API."""
    started = _api_json(server, "/api/judge-sessions", {
        **_MODEL_CELL, "provider": "mock", "judge_model": "mock-judge",
        "passes": passes,
    })
    deadline = time.time() + 20
    while time.time() < deadline:
        snap = _api_json(server, f"/api/judge-runs/{started['run_id']}")
        if snap["status"] != "running":
            assert snap["status"] == "done", snap["error"]
            return started
        time.sleep(0.1)
    pytest.fail("mock judge run did not finish in 20s")


def test_llm_judge_end_to_end_via_browser(page, server):
    """The full second mode as a user drives it: picker → LLM judge button →
    config panel → mock provider → launch → blind progress → reveal with
    rationales + judge stats. Blinding holds until the explicit reveal."""
    page.goto(f"{server}/grade")
    page.get_by_test_id("axis-model").click()
    page.wait_for_selector('[data-testid="cell-row"]')
    page.get_by_test_id("start-llm-judge").first.click()
    page.wait_for_selector('[data-testid="judge-config"]')

    # the config panel lists all three providers with billing badges
    # (the provider list loads async — wait for it before counting)
    page.wait_for_selector('[data-testid="judge-provider-mock"]')
    for pid in ("claude-cli", "gh-models", "mock"):
        assert page.get_by_test_id(f"judge-provider-{pid}").count() == 1
    page.get_by_test_id("judge-provider-mock").click()
    # a plan for the previously-selected default provider may still be on
    # screen — wait for the MOCK plan (recognizable by its zero-spend note)
    page.wait_for_function(
        "() => (document.querySelector('[data-testid=\"judge-plan\"]')?.textContent ?? '').includes('zero spend')"
    )
    plan_text = page.get_by_test_id("judge-plan").inner_text()
    assert "call" in plan_text

    # free provider: no phrase input, launch armed immediately
    assert page.get_by_test_id("judge-confirm-input").count() == 0
    page.get_by_test_id("judge-launch").click()
    page.wait_for_url("**/grade/judge/**")

    # the mock judge finishes fast; the page stays blind meanwhile and after
    page.wait_for_selector('[data-testid="judge-done"]', timeout=20000)
    html = page.content()
    for mid in MODELS:
        assert mid not in html, f"judge progress page leaked axis value {mid!r}"
    assert page.locator('[data-testid="judge-verdicts"] tbody tr').count() >= 1
    consistency = page.get_by_test_id("judge-progress-text").inner_text()
    assert "swap-consistent" in consistency

    # reveal: explicit confirm, then rationales + judge reliability/spend card
    page.get_by_test_id("judge-reveal-link").click()
    page.wait_for_selector('[data-testid="reveal-confirm"]')
    page.get_by_test_id("confirm-reveal").click()
    page.wait_for_selector('[data-testid="judge-stats"]')
    revealed = page.content()
    assert any(m in revealed for m in MODELS), "reveal did not unblind the values"
    assert page.get_by_test_id("judge-rationale").count() >= 1
    stats = page.get_by_test_id("judge-stats").inner_text()
    assert "mock" in stats and "double pass" in stats


def test_paid_judge_provider_requires_typed_phrase(page, server):
    """claude-cli/gh-models judging spends real budget — the launch button
    must stay disarmed until the JUDGE phrase is typed. Nothing is launched."""
    page.goto(f"{server}/grade")
    page.get_by_test_id("axis-model").click()
    page.wait_for_selector('[data-testid="cell-row"]')
    page.get_by_test_id("start-llm-judge").first.click()
    page.wait_for_selector('[data-testid="judge-config"]')

    claude_btn = page.get_by_test_id("judge-provider-claude-cli")
    if not claude_btn.is_enabled():
        pytest.skip("claude CLI not on PATH here — phrase gate not reachable")
    claude_btn.click()
    page.wait_for_selector('[data-testid="judge-confirm-input"]')
    assert page.get_by_test_id("judge-launch").is_disabled()
    page.get_by_test_id("judge-confirm-input").fill("WRONG")
    assert page.get_by_test_id("judge-launch").is_disabled()
    page.get_by_test_id("judge-confirm-input").fill("JUDGE")
    assert page.get_by_test_id("judge-launch").is_enabled()
    # never click launch — this test must not spend anything


def test_llm_session_refuses_manual_grading(page, server):
    started = _run_mock_judge(server)
    page.goto(f"{server}/grade/session/{started['session_id']}")
    page.wait_for_selector('[data-testid="llm-session-redirect"]')
    text = page.get_by_test_id("llm-session-redirect").inner_text()
    assert "LLM judge" in text


def test_reveal_long_rationale_wraps_and_truncation_badge_shows(page, server):
    """A rationale citing an unbroken 150-char identifier must wrap inside
    its cell (not stretch the table into horizontal scroll that clips every
    column), and a verdict rendered on a truncated diff must say so."""
    page.goto(f"{server}/grade/session/revealed-llm/reveal")
    page.wait_for_selector('[data-testid="judge-stats"]')
    assert page.get_by_test_id("judge-rationale").count() == 1
    assert page.get_by_test_id("truncated-badge").count() == 1

    probe = page.evaluate(
        """() => {
          const wrap = document.querySelector('[data-testid="reveal-pairs"]').closest('.table-wrap');
          return {
            tableOverflow: wrap.scrollWidth - wrap.clientWidth,
            pageOverflow: document.scrollingElement.scrollWidth - document.scrollingElement.clientWidth,
          };
        }"""
    )
    assert probe["tableOverflow"] <= 1, f"rationale stretched the table: {probe}"
    assert probe["pageOverflow"] <= 1, f"page overflows horizontally: {probe}"


def test_plan_banner_never_shows_another_providers_numbers(page, server):
    """Switching provider must never leave the previous provider's estimate
    on screen (a mock 'zero spend' banner next to a selected paid provider
    lies about the launch cost). A MutationObserver records every DOM state
    between the switch and the settled new plan."""
    page.goto(f"{server}/grade")
    page.get_by_test_id("axis-model").click()
    page.wait_for_selector('[data-testid="cell-row"]')
    page.get_by_test_id("start-llm-judge").first.click()
    page.wait_for_selector('[data-testid="judge-provider-mock"]')
    page.get_by_test_id("judge-provider-mock").click()
    page.wait_for_function(
        "() => (document.querySelector('[data-testid=\"judge-plan\"]')?.textContent ?? '').includes('zero spend')"
    )

    claude_btn = page.get_by_test_id("judge-provider-claude-cli")
    if not claude_btn.is_enabled():
        pytest.skip("claude CLI not on PATH here — provider switch not reachable")

    page.evaluate(
        """() => {
          window.__planLog = [];
          const root = document.querySelector('[data-testid="judge-config"]');
          new MutationObserver(() => {
            const plan = root.querySelector('[data-testid="judge-plan"]');
            const cli = root.querySelector('[data-testid="judge-provider-claude-cli"]');
            window.__planLog.push({
              plan: plan ? plan.textContent : null,
              cliSelected: cli ? cli.getAttribute('aria-pressed') === 'true' : false,
            });
          }).observe(root, {subtree: true, childList: true, characterData: true, attributes: true});
        }"""
    )
    claude_btn.click()
    page.wait_for_function(
        "() => (document.querySelector('[data-testid=\"judge-plan\"]')?.textContent ?? '').includes('subscription')",
        timeout=15000,
    )
    stale_frames = page.evaluate(
        "() => window.__planLog.filter((s) => s.cliSelected && s.plan && s.plan.includes('zero spend'))"
    )
    assert stale_frames == [], f"stale mock plan shown while claude-cli selected: {stale_frames[:3]}"


def test_report_grader_filter_and_agreement(page, server):
    """With both an LLM session and a human session over the same cell, the
    report shows the human↔LLM agreement card and the grader filter narrows
    the judgment pool."""
    _run_mock_judge(server)
    human = _api_json(
        server,
        "/api/pairs?" + "&".join(f"{k}={v}" for k, v in _MODEL_CELL.items()),
    )
    for pair in human["pairs"]:
        _api_json(server, "/api/judge", {
            "session_id": human["session_id"],
            "pair_index": pair["pair_index"],
            "choice": "A",
        })

    page.goto(f"{server}/report")
    page.get_by_role("button", name="Model", exact=True).click()
    page.wait_for_selector('[data-testid="agreement-card"]')
    card = page.get_by_test_id("agreement-card").inner_text()
    assert "agreed" in card

    all_count = page.get_by_test_id("report-table").inner_text()
    page.get_by_test_id("grader-human").click()
    page.wait_for_selector('[data-testid="report-table"]')
    page.wait_for_function(
        "() => document.body.textContent.includes('human verdicts only')"
    )
    assert page.get_by_test_id("grader-human").get_attribute("aria-pressed") == "true"
    del all_count  # counts differ per sampling; the badge is the assertion
