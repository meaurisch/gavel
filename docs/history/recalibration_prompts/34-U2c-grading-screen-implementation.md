# 34-U2c — Implement the grading-screen redesign (from the 33-U2b design)

**Prerequisites:** prompt 32-U2a is done (leak closed, quick fixes in);
the Claude Design outputs from prompt 33-U2b are saved under
`docs/design/` — read them first and treat them as the spec. If a design
decision there conflicts with a measurement invariant below, the
invariant wins; note the deviation.

**Timing note:** prefer to run this AFTER the human finishes CP2 grading —
changing the instrument's presentation mid-campaign shifts what the judge
sees between pair 6 and pair 40. If the human explicitly chooses comfort
over consistency, log that choice in `docs/measurement-log.md`.

Work on a branch off `llm-judge` (or off `main` if CP2/Stage 4 has merged
by then), one commit series, merged back when green. Zero spend. Full
CLAUDE.md invariants; styling exclusively from
`ui/frontend/src/tokens.css` — no hardcoded colors.

## Scope (the four features from the design)

1. **Declutter** the grading screen per the design spec: near-invisible
   blind-note, compact gate scorecard with build output still reachable,
   compact file navigation, slim file headers, smaller hotkey footer.
   Nothing is removed outright — collapsed/relocated only.
2. **Difference minimap**: per-pane margin markers showing where A and B
   diverge from each other. Compute client-side from the already-served
   (already-anonymized) payloads — the annotation machinery in
   `ui/frontend/src/lib/diff.ts` (it already aligns both sides against
   the original for the three-way view) is the place to derive
   same/different regions. No new server data may be needed; if you
   think you need a new endpoint, stop and reconsider — anything new
   served during blind judging must go through the one blinding
   implementation (`grading/pairwise.redact_axis_ids`).
3. **Dual-monitor pop-out**: side A and/or B in separate browser
   windows per the design. The popped window must render the SAME blind
   payload (no extra fields, no axis ids, no cost/time — reuse the
   existing session fetch), carry the pair index, and follow the main
   window's pair navigation (BroadcastChannel is the natural mechanism;
   same-origin windows only). On reveal or session close, popped
   windows must lock/blank too — a stale popped window must not keep
   serving a closed session's content as if still judgeable.
4. **Resizable three-way columns**: draggable divider trading width
   between Original and the A+B pair. **A and B stay exactly equal
   width at all times** — the existing Playwright pane-equality
   assertion is a fairness invariant, not a styling accident. Update it
   to assert equality-under-resize instead of deleting it. Include
   double-click-to-reset.

## Testing bar (this diff touches nearly every blind surface)

- TDD for the diff.ts derivations (same/different region computation).
- Playwright: extend the existing suite — pane equality (default AND
  after drag), per-axis blinding assertions still green on the new
  layout, no "probe" marker on blind pages, and new coverage for the
  minimap presence and the pop-out (open, navigate, reveal-locks).
- Full fast suite green; frontend rebuilt; keyboard marathon test still
  passes (the keyboard flow must be untouched).

## Done means

- Elevation-brief Part 4 self-check run and reported (smallest diff —
  the design may propose more than the four features; implement these
  four, park the rest).
- `docs/ui-revamp-log.md` gains an entry describing what changed and
  why; README "Current state" updated if warranted;
  `RESUME-2026-08-01.md` progress log updated.
- Screenshots of the new screen (light + dark) into `docs/screenshots/`.
