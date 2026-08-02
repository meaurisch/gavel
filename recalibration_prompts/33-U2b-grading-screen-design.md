# 33-U2b — Claude Design brief: calmer grading screen, dual-monitor mode, difference minimap

**This prompt is written for Claude Design** (it cannot read the repo — it
is fully self-contained). Attach screenshots of the current grading screen
(take fresh ones at `/grade/session/<id>`; older ones live in
`docs/screenshots/`). Paste everything below the line into Claude Design.
Save the outputs (specs/mockups/exports) under `docs/design/` for the
implementation session (prompt 34) to consume.

---

You are designing improvements to **Gavel**, a local-first web tool where
a single human reviewer spends 1–2 hour sessions blindly comparing pairs
of code diffs ("A" vs "B" — two AI coding agents' solutions to the same
task) and picking the one they'd rather merge. Keyboard-first: A / B / T
(tie) to judge, arrows to navigate, O toggles an Original|A|B three-way
view, X expands collapsed unchanged regions.

## Visual language (authoritative tokens — do not invent new hues)

- Light theme: app bg `#f4f5f7`, cards `#ffffff`, inset wells `#eef0f3`,
  borders `#e0e3e9`/`#c9cedb`; text `#20242e`, secondary `#4a5160`,
  muted `#7c8494`, faint `#a7adba`. A dark theme exists — design both.
- Single brand hue, indigo accent `#4e59c8` (hover `#3f49ad`, subtle bg
  `#eceef9`). Semantic: pass green `#27714a`/`#e4f1e8`, fail red
  `#a63d33`/`#f8eae7`, warn amber `#8a611a`/`#f6eeda`, neutral gray.
- Diff colors (side-symmetric, tuned for hours of reading): add
  `#e7f2ea`, delete `#f9ecea`, word-level emphasis `#cbe5d3`/`#f0d4cd`,
  gutters `#f7f8fa`.
- Type: IBM Plex Sans (UI), JetBrains Mono (code/diffs). Sizes 11–28px;
  diff code at 13px, line-height 1.65. Overall register: muted, dense,
  restrained — a professional instrument, not a dashboard demo.

## Hard constraints (measurement-integrity — the design must not break these)

1. **Blindness**: while judging, the screen must never show cost, tokens,
   time, model/methodology names, or ANY visual difference between sides
   beyond their content. A and B must receive exactly equal visual
   treatment — equal widths by default, same styling.
2. Everything currently on the screen exists for a reason — the redesign
   may shrink, collapse, or relocate, but only remove what the brief
   explicitly allows.
3. Keyboard-first flow must survive: the judge's hands stay on A/B/T and
   arrows for an hour straight.

## Current screen inventory (top to bottom)

- Page header: session title, pair progress ("pair 3 of 33 · 6 judged"),
  view toggles (two-way | three-way), DB name.
- A small muted note reading "cost/time hidden (blind)".
- Per-side summary chips: files touched, +added/−removed line counts, and
  a gate scorecard (compile/visible/hidden pass booleans) with expandable
  build-output logs.
- A file list (all files touched by either side) used to jump between
  files; currently a full-width vertical list.
- Side-by-side diff panes (or Original|A|B three-way), each file preceded
  by a header line with the full path and per-side change stats.
- A footer judge bar with keycap chips (A / B / T / arrows / O / X).

## Design tasks

1. **Declutter for calm** (highest value). More vertical space for the
   diffs; a more peaceful screen. Specifically: the "cost/time hidden
   (blind)" note can become nearly invisible (icon/tooltip); the gate
   scorecard + build-output access must stay but take far less space;
   the file list stays but compact (dropdown, popover, or rail);
   file-path headers stay but slimmer; the hotkey footer stays but
   smaller/auto-fading. Propose the full layout.
2. **Difference minimap**: a subtle per-pane margin/scrollbar marker
   showing WHERE A and B differ from each other (both sides changed the
   same original — most of their content is identical; the reviewer
   wants to jump to the parts where the two solutions genuinely
   diverge). Design the marker (position, width, color from the token
   set, hover/click behavior, dark theme) so it guides without shouting.
   It must treat A and B symmetrically.
3. **Dual-monitor mode**: a way to pop one side (or the three-way's
   panes) into separate browser windows so A sits on one monitor and B
   on another. Design the affordance (where the pop-out control lives),
   what the popped window contains (chrome-free: just that side's diff +
   minimal header + sync indicator), and how judging works while popped
   out (the judge bar stays in the main window; scroll sync optional —
   recommend whether it's worth it).
4. **Resizable columns** in the three-way view: the divider between
   Original and A|B is draggable. Constraint: A and B always stay
   exactly equal width to each other (fairness invariant) — dragging
   trades space between Original and the A+B pair, never between A and
   B. Include the reset affordance.

## Deliverables

- Layout spec (annotated mockup or precise written spec) for the default
  grading screen, light + dark.
- Component specs for: compact gate/scorecard treatment, compact file
  navigation, difference minimap, pop-out window, resizable divider —
  with states (hover, active, popped, judged/unjudged).
- Exact token usage per element (no new colors).
- A short interaction spec: what changes for the keyboard flow (ideally
  nothing), what's mouse-only.
