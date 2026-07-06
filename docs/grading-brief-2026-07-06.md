# Grading brief — Checkpoint 2 (2026-07-06)

Stage 2 is closed: **$19.07 of the $20 cap spent**, every trial gated and
priced in `results.db`. Everything below is ready for *you* — nobody else
grades. Launch with `.\tasks.ps1 Ui` → http://localhost:8247 → "Pick a
contest".

## The three gradeable cells

| # | Axis | Pinned cell | Contenders | Pairs |
|---|------|-------------|-----------|-------|
| 1 | **methodology** | cosmos-B · none · claude-haiku-4-5 · claude-code | 5 values × 3 passers = 15 | **30** |
| 2 | **methodology** | moreiter-A · none · claude-sonnet-4-6 · claude-code | 3 values (baseline/karpathy/superpowers) × 2 passers = 6 | **9** |
| 3 | **model** | cosmos-B · baseline · none · claude-code | haiku vs sonnet, 3 passers each | **3** |

42 pairs total. Suggested order: **1 first** (the anchor cell and the core
question — which methodology's output would you merge), then 2, then 3.

## Expected session lengths

- Cell 1: cosmos-B diffs run ~13–15 KB (custom up to ~55 KB). At 1–2 min per
  pair, expect **45–75 min**. It resumes cleanly — stop anytime; the session
  picker shows a progress bar, and a reload mid-session loses nothing.
- Cell 2: moreiter-A diffs are single-repo Python, smaller. **~15–20 min.**
- Cell 3: three pairs. **~5 min.**

## Flow reminders

- Keyboard: **A / B / T** to judge, arrows to navigate, **X** expands
  collapsed unchanged regions in the three-way view, **O** toggles
  Original|A|B. The footer shows the keycap chips.
- Cost/tokens/time are hidden during judging on every axis — by your own
  2026-07-05 decision. They come back in Reveal/Browse/Report.
- **Do not strike the gavel until you're done with a session**: revealing
  requires the explicit confirmation and then **closes the session
  permanently** (no further judgments, 409 on any attempt). Judge all pairs
  you intend to judge first.
- Bradley-Terry wants ≥3 judgments per cell to rank at all; the more pairs
  you judge, the tighter the bootstrap CIs. Partial coverage is fine —
  judge what your patience allows, cell 1 has the highest value per pair.

## Honest context to carry while judging

- Both methodology cells **saturate the hidden gate** (cosmos-B 15/15 after
  the CP1.5 oracle fix; moreiter-A 6/6 at sonnet). The gate is a floor-check
  here; the ranking signal is your merge judgment. The calibration tool
  flags cosmos-B as ceiling (100%) accordingly.
- All judgments are yours alone — the Claude-made judgment and your one
  pre-fix tie were purged with the stale trials (CP1/CP1.5); the pool
  starts at zero.

When you're done grading, say so — Stage 4 (report + decision doc) runs
after your confirmation.
