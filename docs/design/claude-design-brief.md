# Claude Design brief — Tiltyard (setup-bench) visual design system

**Service:** Claude Design.
**Goal:** a complete visual identity + design system for the tool's web UI,
applied consistently across every screen. Phase 1 (done) rebuilt the UI
functionally with deliberately plain placeholder styling; this brief is the
input to the design pass. Phase 2 (a follow-up Claude Code session) will
implement whatever Design produces, so deliverables must be implementable:
**exportable design tokens plus either component code or precise visual
specs**.
**You do first:** have the screenshots in `docs/design/screenshots/`
attached, and skim `README.md` for what the tool does.

---

Paste to Claude Design (attach every screenshot from `docs/design/screenshots/`):

```
This is "Tiltyard" (provisional name — see below), a local-first
decision-support tool a developer runs on their own machine to compare
agentic coding setups: five axes (task × methodology × repo-context × model
× runner), a three-tier build/test gate, and blind pairwise A/B grading of
code diffs feeding a Bradley-Terry ranking. One person uses it at a desk for
long stretches: the core activity is judging anonymized diff pairs
back-to-back, potentially for hours, advancing with the keyboard. It is an
open-source project that should read as a polished, professional developer
tool on first screenshot — the current bar to beat is "local hobby project".

The functional UI is done and correct; every screen currently uses one
deliberately-plain placeholder theme (grayscale + one slate accent, system
fonts) built on a single token file. Your job is the real design:

1. IDENTITY. The provisional name is "Tiltyard" — the arena where jousts
   (one-on-one contests) were held; chosen because the tool's heart is blind
   one-on-one contests in a controlled arena. Build a visual identity around
   it (wordmark, favicon-scale mark, palette, type scale) or propose a
   refinement of the name if you have a clearly stronger candidate — the
   name is not sacred, but it must still work as a CLI/repo name.

2. ONE DESIGN SYSTEM, EVERY SCREEN. A single coherent system (color, type,
   spacing, components: buttons, badges, cards, selects, tables, nav,
   keyboard-hint chips, log expanders) applied uniformly. Deliver:
   - design tokens as CSS custom properties (the app's tokens.css defines
     the exact contract: color surfaces/text/accent/semantic/diff colors,
     a spacing scale, a type scale, radii, shadows — replace the VALUES,
     keep the names);
   - component specs or code (HTML/CSS or React+CSS) precise enough to
     implement faithfully without guessing.

3. THE SCREENS (screenshots attached, all current-state functional):
   - dashboard.png — home: DB switcher, readiness, resume-session list,
     links to every area.
   - picker-hover.png — grading picker: comparison-axis buttons with cell
     counts, gradeable-cell table, five-axis catalog, and a hover preview
     card open on a task id (these preview cards appear on every id chip
     app-wide).
   - session-two-way.png — THE core screen: blind A/B diff comparison.
     Per-side gate badges (build/visible/hidden), diff-shape stats,
     cost/tokens/time, collapsible per-tier log expanders, the two diff
     panes, and the keyboard judge bar (A / Tie / B, prev/next, view
     toggle). This screen must survive hours of repeated judgment.
   - session-three-way.png — the same screen in Original | A | B mode:
     one aligned table per file, collapsible unchanged-region gap rows.
   - reveal.png — post-session unblinding: Bradley-Terry mini-ranking,
     win/loss/tie table, every pair revealed.
   - runs-spend-gate.png — run launcher with the paid-runner confirmation
     gate open (cost estimate + typed confirmation phrase). The
     free-vs-paid distinction deserves clear visual weight: paid must feel
     consequential, not scary-red-everywhere.
   - browse.png — all-trials table: five id chips per row, gate badges,
     cost/tokens/wall columns.
   - trial-detail.png — one trial: axes, full gate scorecard with raw log
     expanders, cost breakdown, unblinded diff.
   - report.png — Bradley-Terry ranking table with CIs, tier pass rates,
     cost columns, Pareto-frontier + quality/budget pick markers.

4. CONSTRAINTS (hard):
   - Hours-long repeated judging: low visual fatigue. Muted large surfaces,
     restrained contrast outside the diff content, generous but efficient
     density. Dark mode is welcome if the token architecture carries it,
     but light mode is the primary deliverable.
   - Keyboard-first affordances: the A/B/Tie keys and navigation must be
     visually discoverable (key chips exist as a component) without
     dominating.
   - BLIND COMPARISON NEUTRALITY: during a grading session nothing may
     visually distinguish side A from side B beyond the neutral "A"/"B"
     labels — no per-side hue, iconography, or ornament that could imply
     "this side is the fancy one". Diff add/remove colors must be
     side-symmetric. (Post-session screens may celebrate winners freely.)
   - Diff legibility is the product: pick diff add/remove/context colors
     and a monospace stack that stay readable for hours; line-number
     gutters must remain visually quiet.
   - Fully local/offline at runtime: no webfont CDNs, no external assets.
     System font stacks or self-hostable (committable) font files only.
   - The three status semantics used everywhere: pass/ok (green-ish),
     fail (red-ish), warn/paid (amber-ish) plus a neutral — pick
     accessible tones that hold up on badges, table cells, and banners.

Give me: the palette (as the tokens.css variable list with values), type
scale + font stack, the wordmark/logo treatment, and per-screen mockups or
component specs I can hand to Claude Code to implement 1:1. Note anything
in the current structure you'd re-lay-out (hierarchy, grouping, density) as
concrete instructions — structural re-layout is allowed if it doesn't
change functionality.
```

---

After Design responds: take the deliverables to a fresh Claude Code session
(phase 2 of `recalibration_prompts/28-U1-ui-ux-professionalization.md`).
Implementation notes for that session:
- Tokens live in `ui/frontend/src/tokens.css`; shared component styles in
  `ui/frontend/src/base.css` and `ui/frontend/src/diff.css`. Every screen
  reads only those — a faithful implementation is mostly a value swap plus
  whatever component-level polish Design specifies.
- The blind-grading invariant is tested: `pytest -m integration
  tests/test_ui_playwright.py` must stay green after restyling (it asserts
  pane equality, line-number tracking, blinding per axis, the spend gate,
  and the keyboard marathon). Run it before and after.
- The provisional wordmark is plain text in `App.tsx` (`.wordmark`) and the
  favicon is an inline SVG placeholder in `ui/frontend/index.html`.
