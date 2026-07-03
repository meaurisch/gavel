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
