# UI revamp — final report (phases 1 + 2)

*Written 2026-07-03, branch `ui-ux-revamp` (off `fable-run`; no remote — the
human reviews and merges by hand). For the blow-by-blow session log see
`docs/ui-revamp-log.md`; for the original mandate see
`recalibration_prompts/28-U1-ui-ux-professionalization.md`.*

## What this was

The benchmarking engine (five-axis matrix, three-tier gate, blind pairwise
grading, Bradley-Terry ranking) was solid and well-tested, but the web UI
read as a "local hobby project": a single 1124-line static HTML file with a
confusing axis-first picker, a broken diff screen (uneven A/B split, line
numbers that didn't scroll with the code, no three-way view), three bare
checkmarks where rich gate data existed, and no unified entry point. The
revamp ran in two phases with a human-run Claude Design interlude between
them.

## Phase 1 — functional rebuild (deliberately plain)

Full frontend rewrite: **Vite + React + TypeScript** SPA in `ui/frontend/`,
served by the existing FastAPI backend (`ui/server.py`), engine untouched.

- **One entry point** — `python cli.py ui` (or `.\tasks.ps1 Ui`) opens a
  dashboard linking grading, a run launcher, a trial browser, and the
  report, with a database switcher. `grade` remains as an alias.
- **Picker** — all five axes visible up front with hover preview cards on
  every id (task instructions, methodology descriptions, model pricing…),
  gradeable cells listed as concrete rows.
- **Diff screen** — custom renderer from parsed unified diffs. Line numbers
  live in the same table row as their code (cannot desync); panes are
  `1fr 1fr` grid children with `min-width: 0` + internal overflow (cannot
  split unevenly); optional lockstep scrolling; a new
  **Original | A | B three-way view** aligns rows on original-file line
  anchors, reconstructing pre-agent content server-side from the task's
  base commit plus laid-down manifests (`ui/originals.py` — no worktree
  needed, and it never persists state).
- **Gate detail during comparison** — per-tier build/visible/hidden logs
  (collapsible), diff-shape stats, cost/tokens/wall-time.
- **Run launcher** — reuses `core/executor.execute_all` with its
  `on_progress` hook streamed over SSE. Free runners (`oracle`/`nop`)
  launch instantly; `claude-code` requires typing **SPEND** next to a cost
  estimate; `manual` is terminal-only by design (blocks on stdin).
- **Blinding hardened** — one redaction implementation
  (`grading.pairwise.redact_axis_ids`) covers diffs, gate logs, and
  originals; the diff-shape stats are computed on the anonymized diff (raw
  file paths could carry axis ids); cost/tokens/time are **never** served
  during blind judging on any axis (a user decision, confirming two critic
  flags — spend metrics bias the judgment; cost enters the decision after
  grading, in the Pareto step, and stays visible in Reveal/Browse/Report);
  **revealing a session requires an explicit "Strike the gavel"
  confirmation and then closes it permanently**
  (`grading_session.revealed_at`, judgments refused with 409 afterward,
  only judged pairs ever unblinded, zero-judgment sessions refused) — the
  original silently-closing GET was a real invariant hole found by a
  fresh-context critic agent.
- **Bootstrap** — `cli.py setup` builds the frontend (npm ci + build);
  `doctor` checks node/npm and the built UI. Clone-and-go stays one
  command.

## The Claude Design interlude (human-run)

Phase 1 ended with plain-styled screenshots and a brief
(`docs/design/claude-design-brief.md`). Claude Design returned
`docs/design/exports/`: a complete design system named **Gavel**.

**Naming.** Phase 1's provisional name was *Tiltyard* (the arena where
jousts happen — blind one-on-one contests). Design proposed **gavel** — the
strike of judgment: five letters, says what the tool does (you judge, it
tallies), verbs naturally, and the identity writes itself (a gavel
mid-swing as the mark, "the gavel has struck" as the session-close line).
Adopted.

**The system.** One indigo accent on near-monochrome surfaces (hours-long
judging stays calm), IBM Plex Sans + JetBrains Mono (both OFL,
self-hosted), full light + dark token sets, and per-component specs:
pill-in-track nav, keycap keyboard chips, one neutral mono chip style for
all five axes (never color-coded — the axis is given by context),
side-symmetric equal-lightness diff tints, and a hard rule that amber
means paid/spend only.

## Phase 2 — applying the design

- `ui/frontend/src/tokens.css` now carries Design's token values and names
  verbatim (light + `[data-theme="dark"]`), with a marked compatibility
  alias block for phase-1 names. `base.css`/`diff.css` implement the
  component specs. A labeled theme toggle persists the choice;
  `color-scheme` follows it so native scrollbars match.
- Fonts ship via fontsource packages, bundled locally by Vite — zero
  network at runtime. Diff/log code disables font ligatures (a grader must
  see the literal `->`, not `→`).
- Screens follow the mockups: dashboard stat strip (trials / passers /
  judgments / total spend) and resume progress bars; "Pick a contest"
  picker with Cell / Contenders / Pairs columns (exact expected pair
  count); compact B✓V✓H✕ gate triplets in tables; "The verdict" reveal
  with a session-winner chip; the SPEND field armed in mono; three-way
  unchanged regions collapse into gap rows expandable by click or the
  X key.
- The standalone HTML report artifact (`grading/report_html.py`) wears the
  same palette and mark — the UI and the artifact are no longer two
  visually unrelated products.
- Identity propagated: favicon + `<title>` "gavel", `gavel doctor`,
  pyproject package `gavel` (legacy `setup-bench` script alias kept),
  README + CLAUDE.md rewritten.

## Verification

- Full fast suite: **305 passed** (`pytest`; 1 env-gated test deselected).
- Browser regression suite: **18 passed**
  (`pytest -m integration tests/test_ui_playwright.py`) — measured pane
  equality with 600-char lines, line-number tracking at four scroll
  offsets, sticky gutters AND file/hunk headers under horizontal scroll,
  full-width open log expanders with three logs per side, three-way
  alignment, per-axis blinding on the full rendered DOM, worktree-hash and
  timing scrubbing in blind logs, the file navigator landing both panes
  exactly, an 18-pair keyboard marathon with a mid-session reload, the
  reveal-confirmation rule, plan invalidation, and the spend gate.
- Convergence: **14 fresh-context critic rounds** (no session memory,
  Playwright access, the full definition of done, later rounds with an
  explicit human-eyeball mandate and real-database usage) reviewed the
  live app. Every finding was fixed or explicitly accepted with reasoning;
  iteration stopped when two consecutive rounds (13 and 14) found nothing
  above minor polish. Highlights of what the rounds caught: a bare GET
  that irreversibly closed sessions, browser-cached shells serving deleted
  bundles, a log-expander fix that demo data had masked, and two
  deliberate-join deblinding channels (worktree hashes, machine-timing
  lines) — all closed.
- A mid-effort live review by the project owner redirected two policies:
  spend metrics are hidden during blind judging on every axis (not just
  model/runner), and testing must exercise real measurement data, not just
  the synthetic demo — which immediately surfaced bugs the demo had
  hidden.

## Explicitly deferred (and why)

- **Structured per-test gate parsing** (pytest/trx → per-test names and
  failures): the raw per-tier logs are served in full instead. Parsing is
  strictly better but is instrumentation work, not presentation — and the
  logs already answer "which tests failed".
- **Word-level intra-line diff highlighting**: the Gavel tokens for it
  exist (`--diff-word-add/del`) but the renderer feature is deferred; the
  line-level view is correct and legible without it.
- **Copilot runner** remains a stub (no plan available) — visible in the
  catalog, refused by the launcher, labeled honestly.
- **Legacy report artifacts** generated before the redesign keep their old
  styling (they're immutable outputs); everything generated now is
  on-brand.

## How to run it

```powershell
.\tasks.ps1 Setup   # venv + deps + task repos + web UI build + doctor
.\tasks.ps1 Ui      # → http://localhost:8247
python cli.py demo  # zero-spend synthetic DB to try grading/report
pytest              # fast suite
python -m playwright install chromium
pytest -m integration tests/test_ui_playwright.py   # browser suite
```
