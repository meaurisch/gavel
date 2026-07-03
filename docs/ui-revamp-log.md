# UI revamp log — phase 1 (functional rebuild, plain styling)

Running notes: one line per significant decision/fix, what/why/how verified.
Branch: `ui-ux-revamp`. Spec: `recalibration_prompts/28-U1-ui-ux-professionalization.md`.

## Decisions

- **Provisional name: "Tiltyard"** — the core interaction is blind one-on-one
  contests (pairwise A/B jousts) held in a controlled arena; a tiltyard is
  exactly that. Distinctive, brandable, no known dev-tool collision, and the
  benchmark metaphor (lists, tilts, rankings) extends naturally. Plain text
  wordmark only in phase 1; Claude Design owns the visual identity.
- **Frontend stack: Vite + React + TypeScript** in `ui/frontend/`, built to
  `ui/frontend/dist/`, served by the existing FastAPI app with an SPA
  fallback. Node/npm become doctor-checked prerequisites; `cli.py setup`
  runs `npm install` + `npm run build` so the one-command bootstrap holds.
- **Diff rendering: own renderer from parsed unified diffs** (small TS parser,
  no diff lib). Line numbers live in the same grid row as their code line, so
  they cannot desync from scroll by construction; pane equality is a
  `grid-template-columns: 1fr 1fr` + `min-width: 0` + `overflow-x: auto`
  contract asserted by Playwright bounding-rect tests. Three-way
  Original | A | B aligns rows on original-file line anchors.
- **"Original" reconstruction without worktrees**: task is never the
  comparison axis (AXIS_FIELDS has methodology/model/repo_context/runner), so
  base_commit is common within a session. Original file content resolves as
  methodology.files > repo_context.files > tasks/<id>/visible_tests/ >
  `git show base_commit:path` in `repos/<repo>`; unresolvable (demo tasks,
  agent-created files) → empty original, rendered as "new file". Served
  originals get the same axis-id redaction as diffs.
- **Blinding for new surfaces**: gate logs (compile/visible/hidden output) are
  redacted with the same whole-token axis-id redaction as `anonymize_diff`
  before serving during comparison. Cost/tokens/wall-time are shown during
  comparison for methodology/repo_context axes but withheld (with an explicit
  "hidden to preserve blinding" note) when the varying axis is model or
  runner, where they directly fingerprint the value.
- **Run launcher scope**: browser launcher offers `oracle`/`nop` freely,
  requires an explicit typed confirmation + cost estimate for `claude-code`,
  and lists `manual` as terminal-only (its runner blocks on stdin `input()`).
  Reuses `core.executor.execute_all` with `on_progress` → SSE; no second
  execution path.
- **DB selection is per-request** (`?db=` query param, validated against
  `*.db` files in the project root) instead of a single global connection, so
  the dashboard can browse results.db / results-demo.db / scratch DBs without
  server restarts.

## Fixes / verifications

(chronological)

- Backend expansion landed (295 fast tests green): per-request `?db=`
  selection + `/api/dbs`; `/api/catalog` (descriptions, task instructions,
  difficulty, pricing, runner registry — the data the old picker dropped);
  `/api/pairs` now carries per-tier gate logs (redacted through the same
  `redact_axis_ids` as diffs, truncated at 100k chars) and cost/tokens/wall
  metrics (withheld with an explicit reason on model/runner axes);
  `/api/session/{id}` + `/api/sessions` for resume-without-state-loss;
  `/api/pair-originals` (three-way view data, redacted, `new` vs
  `unavailable` distinguished); `/api/report` JSON + artifact listing;
  `/api/trials` browser; run launcher (`plan`/start/cancel/SSE) with
  single-flight, free-runner default, typed `SPEND` confirmation for
  claude-code, and manual/copilot refused with reasons. `redact_axis_ids`
  extracted from `anonymize_diff` so every blind surface shares ONE redaction
  implementation. Old `ui/static/` (diff2html UI) deleted.
- `/api/dbs` fix: the configured default DB now always wins its name slot —
  previously a root `results.db` shadowed a `--db`-configured file of the
  same name (caught by test_dbs_lists_default).
- Frontend SPA landed (Vite+React+TS in ui/frontend, tokens.css + base.css as
  the shared design scaffold) and verified live on the demo DB via Playwright
  MCP: dashboard (DB switcher, readiness, resume list), picker (axis buttons
  with cell counts, cell rows, five-axis catalog reference, hover preview
  confirmed to show cosmos-B's full instruction), grading session (pane
  widths measured EXACTLY equal 442.5/442.5, gate badges + logs + metrics
  visible, keyboard 'a' judged and advanced, no axis-value leak in body
  text), three-way Original|A|B (renders new-file pairs correctly), browse →
  trial detail (raw tier logs + unblinded diff), report (BT ranking + picks
  match cli.py report's demo output).
- Diff bug found by driving the app: new-file hunks (`@@ -0,0 +1,N @@`)
  anchored insertions at old line -1 (git's zero-count convention means
  "after line N", not "at N-1"), so three-way tables rendered ZERO rows for
  created files. Fixed in lib/diff.ts annotate(); verified 29 aligned rows
  render for the demo pair afterward.
- Setup/doctor integration: `cli.py setup` now builds the web UI (npm ci +
  build via scripts/frontend_setup.py, --skip-frontend to opt out); doctor
  gained required `node + npm` and `web UI build` rows (verified green
  live); `cli.py ui` is the documented entry point (grade = alias landing on
  /grade); tasks.ps1 gained `Ui`; README Quickstart rewritten around the
  single-entry-point flow with the Node 18+ prerequisite.
- Run launcher verified LIVE end-to-end in the browser: paid path
  (claude-code) shows the spend banner with pricing rates + honest "no
  historical data" note and a disabled launch until the SPEND phrase is
  typed (never launched); free path ran a real nop trial on moreiter-A into
  scratch-ui-live.db — SSE progress streamed to the table, status done,
  gate FAIL (correct for nop: build ✓ visible ✓ hidden ✗), and the trial
  browsable after switching the UI to the scratch DB via ?db=. Scratch DB
  deleted afterward.
- Note for automation: the run-launcher multi-pick buttons derive toggle
  state from props, so same-tick programmatic clicks race React's rerender —
  click sequentially with a settle delay in tests (humans are unaffected).
- Fresh-context critic pass (subagent driving the live app) found 1 blocker,
  1 major, 10 minors/nits; all fixed and re-verified live + by tests:
  - BLOCKER: `/grade/session/<id>/reveal` unblinded ALL pairs of an
    in-progress session and the session kept accepting judgments. Fix:
    reveal permanently closes the session (`grading_session.revealed_at`,
    migrated via _ensure_column), `/api/judge` returns 409 on a revealed
    session (persisted — survives restart), reveal exposes JUDGED pairs
    only (unjudged assignments could deblind future sessions over the same
    trials), UI swaps the judge bar for a "session closed" bar. Verified
    live (UI keyboard ignored, direct API 409) + fast tests + a dedicated
    Playwright test.
  - MAJOR: stale `tiltyard.db` in localStorage (e.g. a deleted scratch DB)
    half-bricked the app while the switcher showed the default as selected.
    Fix: DbSwitcher self-heals to the server default when the stored name
    isn't in /api/dbs. Verified live.
  - Deliberate decision on metric fingerprinting (critic #3): cost/tokens/
    wall stay visible on methodology/repo-context axes (cost is part of the
    judgment per the tool's decision rule) but are now server-side rounded
    to ~2 significant figures so they can't be joined 1:1 against the
    unblinded Browse table.
  - Demo three-way cleanup: created files report status "new" with a
    "new file" note instead of an internal-exception banner; unavailability
    note only appears when a shown file is actually unreconstructable.
  - Picker gained an unfinished-session resume banner (was dashboard-only);
    "Session not found" now offers a back-link + wrong-DB hint; runner
    select lists all real runners (copilot-cli disabled as not-runnable,
    db-only ids like demo-runner excluded); claude-code plan without a
    model is validated client-side; "Write results to" placeholder names
    the actual active DB; Elo CIs render "x to y" (negative-bound
    readability); artifact list notes its filenames are UTC; axis picker
    persists in the URL (?axis=) and toggles carry aria-pressed.

## Phase 2 — implementing the Gavel design system

- Claude Design's exports landed in `docs/design/exports/`: tokens.css
  (light + dark), the full design-system doc with per-component specs and
  per-screen mockups, and a proposed name refinement — **"gavel"** (the
  strike of judgment) over phase 1's provisional Tiltyard. Adopted: it's
  shorter, verbs well, and the identity (mid-swing mark, one indigo accent,
  playfully-professional voice) is built around it.
- Tokens: adopted Design's token NAMES wholesale (they're the system of
  record now) with a marked compatibility-alias block so phase-1 inline
  var() references keep resolving to the same values. Dark theme shipped as
  `[data-theme="dark"]` + a persisted nav toggle; verified live (every
  surface flips, including the mark's dark lockup variant).
- Fonts: IBM Plex Sans + JetBrains Mono (OFL) self-hosted via fontsource
  packages — bundled into dist/assets by Vite, zero network at runtime
  (checked: the built CSS references only local hashed woff2). Diff/log
  code disables font ligatures: a grader must see the literal `->`, not
  `→` (caught this live on the restyled session screen).
- base.css/diff.css rebuilt to the component specs: pill-in-track nav,
  one-primary buttons + focus rings, neutral mono id chips with accent
  hover, keycap kbd chips, segmented view toggles, caps-11 table headers +
  right-aligned mono numerics, banner semantics (amber = paid/spend ONLY;
  informational = neutral — reveal/closed banners switched accordingly),
  log expanders with char counts, side-symmetric equal-lightness diff
  tints with sign-colored quiet gutters, leading-code 1.65.
- Screens per mockups: dashboard stat strip (new `total_usd` on /api/dbs)
  + resume progress bars; picker = "Pick a contest" with
  Cell/Contenders/Pairs columns (new exact `n_pairs` on /api/cells, same
  arithmetic as generate_pairs); browse uses the compact B/V/H triplet;
  reveal = "The verdict" with a session-winner chip and the gavel-has-
  struck close notice; runs launcher arms via a mono SPEND field with the
  caps SPENDS-REAL-API-BUDGET chip; three-way gaps expand via click or the
  X key ("unchanged region — N aligned rows collapsed").
- The standalone report artifact (grading/report_html.py) restyled to the
  same palette+mark — the original feedback called out the UI and artifact
  as two disconnected themes.
- Naming surfaces: pyproject → `gavel` (with `setup-bench` legacy script
  alias), `gavel doctor` table title, README retitle, CLAUDE.md facts
  rewritten. In-app microcopy uses the real command (`python cli.py run`),
  not the mockup's `gavel run`, since the documented flow doesn't pip-install
  the package.
- Verified after restyle: full fast suite 299 green; all 15 Playwright
  integration tests green (pane equality, line-number tracking, blinding,
  marathon, spend gate — the exact phase-1 assertions).

## End of phase 1

- Final state: 299 fast tests green + 15 Playwright integration tests green
  (1 env-gated test deselected, as before). Tree clean on `ui-ux-revamp`.
- Screenshots of every key screen (functionally correct, deliberately plain)
  captured live from the demo DB at 1440×900 into
  `docs/design/screenshots/`: dashboard, picker with an open hover preview,
  two-way session (gate logs expanded, coarsened metrics visible), three-way
  session (new-file originals), reveal (BT mini-ranking), runs with the
  spend gate open, browse, trial detail (raw tier logs), report.
  `docs/screenshots/grading-compare.png` (referenced by the README) replaced
  with the current two-way session shot — the old image showed the deleted
  diff2html UI.
- Claude Design brief at `docs/design/claude-design-brief.md` (follows the
  `recalibration_prompts/15` handoff shape). Phase 2 = human runs Claude
  Design with brief + screenshots, then a follow-up session implements the
  design onto tokens.css/base.css/diff.css and re-runs the Playwright suite.
