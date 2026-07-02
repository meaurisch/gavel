"""Self-contained HTML report with an inline-SVG quality/cost Pareto chart.

No external assets, no JS frameworks: inline CSS (light + dark via
prefers-color-scheme), static SVG with native <title> tooltips, direct labels
on every point, a legend, and a full data table below the chart (the
accessibility/table view). Colors follow the validated reference palette:
frontier points wear the accent blue, dominated points the muted ink; the two
stakes picks are marked with a ring + text badge, not extra hues.
"""

from __future__ import annotations

import html as _html
import math

from grading.aggregate import AxisValueSummary, ReportData

# Chart geometry
_W, _H = 780, 440
_ML, _MR, _MT, _MB = 70, 200, 28, 56


def _esc(s: object) -> str:
    return _html.escape(str(s))


def _elo(strength: float) -> float:
    return 1000.0 + 400.0 * strength / math.log(10)


def _nice_ticks(lo: float, hi: float, n: int = 5) -> list[float]:
    if hi <= lo:
        hi = lo + 1.0
    raw = (hi - lo) / max(n, 1)
    mag = 10 ** math.floor(math.log10(raw))
    for m in (1, 2, 2.5, 5, 10):
        step = m * mag
        if raw <= step:
            break
    start = math.floor(lo / step) * step
    ticks = []
    t = start
    while t <= hi + step * 0.5:
        if t >= lo - step * 0.5:
            ticks.append(round(t, 10))
        t += step
    return ticks


def _fmt_usd(v: float | None) -> str:
    if v is None:
        return "—"
    return f"${v:,.2f}" if v >= 0.10 else f"${v:,.3f}"


def _fmt_rate(v: float | None) -> str:
    return "—" if v is None else f"{v * 100:.0f}%"


def render_pareto_svg(report: ReportData) -> str:
    """The quality-vs-cost chart. Points need both a cost and a BT score;
    values missing either appear only in the table."""
    pts = [s for s in report.summaries if s.mean_usd is not None and s.bt_strength is not None]
    if not pts:
        return (
            '<div class="empty">No plottable points yet — the chart needs both '
            "cost data and blind-grading judgments. Run trials, grade them "
            "(<code>python cli.py grade</code>), then re-run the report.</div>"
        )

    xs = [s.mean_usd for s in pts]
    ylos = [_elo(s.bt_ci[0]) if s.bt_ci else _elo(s.bt_strength) for s in pts]
    yhis = [_elo(s.bt_ci[1]) if s.bt_ci else _elo(s.bt_strength) for s in pts]

    x_max = max(xs) * 1.12 or 1.0
    x_min = 0.0
    y_min, y_max = min(ylos), max(yhis)
    y_pad = max((y_max - y_min) * 0.12, 10.0)
    y_min, y_max = y_min - y_pad, y_max + y_pad

    px_w = _W - _ML - _MR
    px_h = _H - _MT - _MB

    def X(v: float) -> float:
        return _ML + (v - x_min) / (x_max - x_min) * px_w

    def Y(v: float) -> float:
        return _MT + (y_max - v) / (y_max - y_min) * px_h

    parts: list[str] = []
    parts.append(
        f'<svg viewBox="0 0 {_W} {_H}" role="img" '
        f'aria-label="Quality (Elo) versus cost (mean USD per trial) for each '
        f'{_esc(report.axis)} value">'
    )

    # Grid + ticks
    for t in _nice_ticks(y_min, y_max):
        y = Y(t)
        parts.append(f'<line class="grid" x1="{_ML}" y1="{y:.1f}" x2="{_W - _MR}" y2="{y:.1f}"/>')
        parts.append(f'<text class="tick" x="{_ML - 8}" y="{y:.1f}" dy="0.32em" text-anchor="end">{t:.0f}</text>')
    for t in _nice_ticks(x_min, x_max):
        x = X(t)
        parts.append(f'<line class="grid" x1="{x:.1f}" y1="{_MT}" x2="{x:.1f}" y2="{_H - _MB}"/>')
        parts.append(f'<text class="tick" x="{x:.1f}" y="{_H - _MB + 18}" text-anchor="middle">{_fmt_usd(t)}</text>')

    # Axis baselines
    parts.append(f'<line class="axis" x1="{_ML}" y1="{_H - _MB}" x2="{_W - _MR}" y2="{_H - _MB}"/>')
    parts.append(f'<line class="axis" x1="{_ML}" y1="{_MT}" x2="{_ML}" y2="{_H - _MB}"/>')

    # Axis titles
    parts.append(
        f'<text class="axis-title" x="{_ML + px_w / 2:.1f}" y="{_H - 14}" text-anchor="middle">'
        "Cost — mean USD per trial (lower is better)</text>"
    )
    parts.append(
        f'<text class="axis-title" transform="translate(16,{_MT + px_h / 2:.1f}) rotate(-90)" '
        'text-anchor="middle">Quality — Bradley-Terry score (Elo)</text>'
    )

    # Frontier staircase (cost ascending; step through frontier points)
    frontier = sorted((s for s in pts if s.on_frontier), key=lambda s: s.mean_usd)
    if len(frontier) > 1:
        d = f"M {X(frontier[0].mean_usd):.1f} {Y(_elo(frontier[0].bt_strength)):.1f}"
        for prev, nxt in zip(frontier, frontier[1:]):
            d += f" L {X(nxt.mean_usd):.1f} {Y(_elo(prev.bt_strength)):.1f}"
            d += f" L {X(nxt.mean_usd):.1f} {Y(_elo(nxt.bt_strength)):.1f}"
        parts.append(f'<path class="frontier-line" d="{d}"/>')

    # Points: CI bar, marker, pick ring, direct label, native tooltip
    for s in sorted(pts, key=lambda p: p.mean_usd):
        x = X(s.mean_usd)
        y = Y(_elo(s.bt_strength))
        cls = "pt-frontier" if s.on_frontier else "pt-dominated"
        ci_txt = ""
        if s.bt_ci:
            y1, y2 = Y(_elo(s.bt_ci[1])), Y(_elo(s.bt_ci[0]))
            parts.append(f'<line class="ci {cls}" x1="{x:.1f}" y1="{y1:.1f}" x2="{x:.1f}" y2="{y2:.1f}"/>')
            parts.append(f'<line class="ci {cls}" x1="{x - 4:.1f}" y1="{y1:.1f}" x2="{x + 4:.1f}" y2="{y1:.1f}"/>')
            parts.append(f'<line class="ci {cls}" x1="{x - 4:.1f}" y1="{y2:.1f}" x2="{x + 4:.1f}" y2="{y2:.1f}"/>')
            ci_txt = f"\n95% CI (Elo): {_elo(s.bt_ci[0]):.0f}–{_elo(s.bt_ci[1]):.0f}"

        badges = []
        if s.value == report.picks.get("high_stakes"):
            badges.append("quality pick")
        if s.value == report.picks.get("routine"):
            badges.append("budget pick")
        if badges:
            parts.append(f'<circle class="pick-ring" cx="{x:.1f}" cy="{y:.1f}" r="10"/>')

        title = (
            f"{s.value}\nElo {s.elo:.0f}{ci_txt}\nmean cost {_fmt_usd(s.mean_usd)}"
            f"\nhidden-gate pass {_fmt_rate(s.gate_pass_rate)} over {s.n_gated} trial(s)"
            + (f"\n{' + '.join(badges)}" if badges else "")
        )
        parts.append(
            f'<g class="{cls}"><circle class="pt" cx="{x:.1f}" cy="{y:.1f}" r="5">'
            f"<title>{_esc(title)}</title></circle></g>"
        )

        label = s.value + (f"  ({' + '.join(badges)})" if badges else "")
        parts.append(
            f'<text class="pt-label {cls}" x="{x + 12:.1f}" y="{y:.1f}" dy="0.32em">{_esc(label)}</text>'
        )

    # Legend (top-right margin space)
    lx, ly = _W - _MR + 14, _MT + 6
    parts.append(f'<circle class="pt pt-frontier" cx="{lx}" cy="{ly}" r="5"/>')
    parts.append(f'<text class="legend" x="{lx + 12}" y="{ly}" dy="0.32em">on the frontier</text>')
    parts.append(f'<circle class="pt pt-dominated" cx="{lx}" cy="{ly + 22}" r="5"/>')
    parts.append(f'<text class="legend" x="{lx + 12}" y="{ly + 22}" dy="0.32em">dominated</text>')
    parts.append(f'<circle class="pick-ring" cx="{lx}" cy="{ly + 44}" r="8"/>')
    parts.append(f'<text class="legend" x="{lx + 12}" y="{ly + 44}" dy="0.32em">stakes pick</text>')

    parts.append("</svg>")
    return "".join(parts)


def render_report_html(report: ReportData, generated_at: str = "") -> str:
    cell_txt = ", ".join(f"{k}={v}" for k, v in report.cell.items()) or "all cells"

    rows = []
    for s in sorted(report.summaries, key=lambda x: -(x.bt_strength if x.bt_strength is not None else -1e9)):
        ci = f"{_elo(s.bt_ci[0]):.0f}–{_elo(s.bt_ci[1]):.0f}" if s.bt_ci else "—"
        badges = []
        if s.value == report.picks.get("high_stakes"):
            badges.append('<span class="badge badge-q">quality pick</span>')
        if s.value == report.picks.get("routine"):
            badges.append('<span class="badge badge-b">budget pick</span>')
        rows.append(
            "<tr>"
            f"<td>{_esc(s.value)} {' '.join(badges)}</td>"
            f"<td class='num'>{f'{s.elo:.0f}' if s.elo is not None else '—'}</td>"
            f"<td class='num'>{ci}</td>"
            f"<td class='num'>{s.n_comparisons}</td>"
            f"<td class='num'>{_fmt_rate(s.tier_pass_rates.get('compile'))}</td>"
            f"<td class='num'>{_fmt_rate(s.tier_pass_rates.get('visible'))}</td>"
            f"<td class='num'>{_fmt_rate(s.tier_pass_rates.get('hidden'))}</td>"
            f"<td class='num'>{s.n_trials}</td>"
            f"<td class='num'>{_fmt_usd(s.mean_usd)}</td>"
            f"<td class='num'>{_fmt_usd(s.total_usd)}</td>"
            f"<td>{'yes' if s.on_frontier else ('—' if s.bt_strength is None else 'no')}</td>"
            "</tr>"
        )

    flags_html = ""
    flag_items = (
        [f"non-discriminating task: {t}" for t in report.flags.non_discriminating_tasks]
        + [f"flaky task: {t}" for t in report.flags.flaky_tasks]
        + list(report.flags.cost_quality_notes)
    )
    if flag_items:
        lis = "".join(f"<li>{_esc(f)}</li>" for f in flag_items)
        flags_html = f'<h2>Analyzer flags</h2><ul class="flags">{lis}</ul>'

    picks_html = ""
    if report.picks.get("high_stakes"):
        picks_html = (
            '<div class="picks">'
            f"<div><span class='badge badge-q'>quality pick</span> "
            f"<strong>{_esc(report.picks['high_stakes'])}</strong> — for high-stakes work, "
            "take the quality winner regardless of cost.</div>"
            f"<div><span class='badge badge-b'>budget pick</span> "
            f"<strong>{_esc(report.picks['routine'])}</strong> — for routine work, the cheapest "
            "value whose confidence interval overlaps the winner's (statistically "
            "indistinguishable).</div></div>"
        )

    n_note = (
        f"{report.n_judgments} blind judgment(s) across {report.n_sessions} grading session(s). "
        "Overlapping confidence intervals mean the values are statistically "
        "indistinguishable — treat this as decision support, not a theorem."
    )

    return f"""<!doctype html>
<html lang="en">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>setup-bench report — {_esc(report.axis)} axis</title>
<style>
  :root {{
    --surface: #fcfcfb; --page: #f9f9f7;
    --ink: #0b0b0b; --ink-2: #52514e; --muted: #898781;
    --grid: #e1e0d9; --axis: #c3c2b7; --border: rgba(11,11,11,0.10);
    --accent: #2a78d6; --badge-q: #2a78d6; --badge-b: #006300;
  }}
  @media (prefers-color-scheme: dark) {{
    :root {{
      --surface: #1a1a19; --page: #0d0d0d;
      --ink: #ffffff; --ink-2: #c3c2b7; --muted: #898781;
      --grid: #2c2c2a; --axis: #383835; --border: rgba(255,255,255,0.10);
      --accent: #3987e5; --badge-q: #3987e5; --badge-b: #0ca30c;
    }}
  }}
  * {{ box-sizing: border-box; }}
  body {{
    margin: 0; padding: 32px 16px; background: var(--page); color: var(--ink);
    font: 15px/1.5 system-ui, -apple-system, "Segoe UI", sans-serif;
  }}
  main {{ max-width: 900px; margin: 0 auto; }}
  h1 {{ font-size: 22px; margin: 0 0 4px; }}
  h2 {{ font-size: 16px; margin: 28px 0 8px; }}
  .sub {{ color: var(--ink-2); margin: 0 0 20px; }}
  .card {{
    background: var(--surface); border: 1px solid var(--border);
    border-radius: 8px; padding: 20px; margin: 16px 0;
  }}
  svg {{ width: 100%; height: auto; display: block; }}
  .grid {{ stroke: var(--grid); stroke-width: 1; }}
  .axis {{ stroke: var(--axis); stroke-width: 1; }}
  .tick, .legend {{ fill: var(--muted); font-size: 11px; font-variant-numeric: tabular-nums; }}
  .axis-title {{ fill: var(--ink-2); font-size: 12px; }}
  .pt-frontier .pt, circle.pt-frontier {{ fill: var(--accent); }}
  .pt-dominated .pt, circle.pt-dominated {{ fill: var(--muted); }}
  .pt {{ stroke: var(--surface); stroke-width: 2; }}
  line.ci {{ stroke-width: 2; opacity: 0.55; }}
  line.ci.pt-frontier {{ stroke: var(--accent); }}
  line.ci.pt-dominated {{ stroke: var(--muted); }}
  .frontier-line {{ fill: none; stroke: var(--accent); stroke-width: 1; stroke-dasharray: 4 4; opacity: 0.6; }}
  .pick-ring {{ fill: none; stroke: var(--ink); stroke-width: 1.5; }}
  .pt-label {{ font-size: 12px; fill: var(--ink); }}
  text.pt-label.pt-dominated {{ fill: var(--ink-2); }}
  .picks {{ display: grid; gap: 8px; margin: 12px 0; }}
  .badge {{
    display: inline-block; padding: 1px 8px; border-radius: 999px;
    font-size: 11px; font-weight: 600; color: #fff;
  }}
  .badge-q {{ background: var(--badge-q); }}
  .badge-b {{ background: var(--badge-b); }}
  table {{ width: 100%; border-collapse: collapse; font-size: 13.5px; }}
  th, td {{ text-align: left; padding: 6px 10px; border-bottom: 1px solid var(--grid); }}
  th {{ color: var(--ink-2); font-weight: 600; white-space: nowrap; }}
  td.num, th.num {{ text-align: right; font-variant-numeric: tabular-nums; }}
  .flags li {{ color: var(--ink-2); }}
  .note {{ color: var(--muted); font-size: 13px; }}
  .empty {{ color: var(--ink-2); padding: 24px; text-align: center; }}
  .tablewrap {{ overflow-x: auto; }}
</style>
</head>
<body>
<main>
  <h1>setup-bench report — comparison axis: {_esc(report.axis)}</h1>
  <p class="sub">Scope: {_esc(cell_txt)}{f" · generated {_esc(generated_at)}" if generated_at else ""}</p>

  {picks_html}

  <div class="card">
    <h2 style="margin-top:0">Quality vs. cost — Pareto frontier</h2>
    {render_pareto_svg(report)}
    <p class="note">{n_note}</p>
  </div>

  <h2>All values</h2>
  <div class="card tablewrap">
    <table>
      <thead><tr>
        <th>{_esc(report.axis)}</th><th class="num">Elo</th><th class="num">95% CI</th>
        <th class="num">Comparisons</th>
        <th class="num">Compile</th><th class="num">Visible</th><th class="num">Hidden</th>
        <th class="num">Trials</th><th class="num">Mean $</th><th class="num">Total $</th>
        <th>Frontier</th>
      </tr></thead>
      <tbody>{"".join(rows)}</tbody>
    </table>
  </div>

  {flags_html}
</main>
</body>
</html>
"""
