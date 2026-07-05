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
- Fresh critic pass 1 (skeptical senior engineer, no session context):
  0 blockers, 2 majors, 3 minors, 3 nits. All addressed:
  - MAJOR preview clipping: cards now render in a body portal with fixed
    positioning + viewport-bottom flip + a hover grace timer (measured:
    99px card fully visible inside the cells table; bottom-of-catalog card
    flips above its anchor and stays on-screen).
  - MAJOR /grade page overflow: grid items default to min-width:auto —
    `.grid-2/3 > * { min-width: 0 }` (same bug class as the phase-1 diff
    panes, one level up). Measured 0px overflow at 1440 and 1100.
  - Stale pre-redesign report artifacts: a fresh on-brand artifact now
    tops the newest-first list; legacy artifacts stay (immutable outputs).
  - Trial-detail dead end on DB switch → back-link + wrong-DB hint;
    "4 methodologys" → per-axis plural nouns; dark scrollbars →
    `color-scheme` follows the theme; theme toggle → labeled secondary
    button ("☾ dark"/"☀ light"); empty-model claude-code preview
    re-verified with a fetch spy — no request fires (critic's 400 was
    stale console state, validation is client-side).
  - Critic confirmed clean: blinding in both view modes (DOM sweep),
    reveal-closes-session, diff mechanics (equal panes incl. injected
    400-char line, line-number tracking, sync scroll, double-click
    idempotency, mid-session reload), SPEND gate exactness, dark-theme
    sweep, hostile localStorage/deep-link/back-forward probes.

- Fresh critic pass 2: 0 blockers, 1 major, 1 minor, 3 nits.
  - MAJOR: preview cards clipped at the viewport bottom on table-cell
    anchors at 1100×800. Two compounding causes found: (a) one-shot
    placement — a fixed-position card goes stale when its anchor scrolls or
    its height settles after first layout; (b) the SPA shell (index.html)
    was served without Cache-Control, so browsers heuristically cached it
    and kept loading OLD bundles after rebuilds (this also explains the
    "stale pre-redesign bundle" console crash both critics noticed).
    Fixes: cards now reposition continuously while open (capture-phase
    scroll + resize listeners + ResizeObserver), and the shell ships
    `Cache-Control: no-cache` (hashed assets still cache). Re-measured the
    exact repro: card flips above (618–717 vs anchor 723, fully visible)
    and tracks a 120px container scroll 1:1.
  - Minor/nits: picker resume banner adds "+N more — the dashboard lists
    them all" past 4 rows (dashboard now lists all); unknown routes get a
    back-to-dashboard link; artifacts caption renders once per section.
    The wrong-DB 404 console entry stays: browsers always log failed
    requests, and the UI recovers with the helpful error + back link —
    accepted as cosmetic devtools noise.
  - Critic-2 confirmed clean: blinding at DOM AND network layer, reveal
    closure incl. direct API 409 probe, diff geometry (equal panes with a
    500-char injected line, 0.5px row alignment), keyboard + reload
    persistence, SPEND gate exactness (case-sensitive arm/disarm), zero
    page overflow on every screen at both widths, dark theme + fonts +
    branding sweep (zero Tiltyard/setup-bench in the bundle).

- Fresh critic pass 3: 1 blocker, 1 major, 2 minors, 2 nits (it also
  retracted two of its own earlier findings after discovering they only
  reproduced on stale cached bundles — the same cache pathology as below).
  - BLOCKER: browsers that cached the SPA shell BEFORE the no-cache fix
    keep loading hashed bundles that no longer exist after a rebuild →
    dead blank page, no recovery. Fix: missing `/assets/*.js` now serves a
    tiny no-store rescue script that reloads once (sessionStorage loop
    guard, cleared on successful mount) — a reload always revalidates the
    top-level document, which then carries no-cache forever after. Hashed
    assets serve as immutable. Verified live against the critic's exact
    stale bundle name; fast tests cover rescue + immutable paths.
  - MAJOR: revealing was reachable by bare GET (URL autocomplete!) and
    auto-fired after the final judgment — one slip irreversibly closed an
    in-progress session. Fix: GET /api/reveal is read-only (locked stub
    with counts, NOTHING unblinded); closing takes an explicit POST behind
    a UI confirmation ("Strike the gavel — reveal", with a keep-judging
    escape hatch showing how many pairs remain). Verified live: bare
    navigation leaks nothing and the session stays judgeable; the
    confirmed strike closes it with only judged pairs unblinded. Fast +
    Playwright tests updated to the new flow.
  - Minors/nits: legacy `tiltyard.db` localStorage key migrates to
    `gavel.db`; Report page summary now uses the same quality-pick /
    budget-pick vocabulary as the row chips. ACCEPTED as designed: coarse
    cost/tokens/time stay visible on methodology/repo-context axes (cost
    is part of the judgment per the decision rule; already coarsened to 2
    significant figures against exact-join fingerprinting) and
    expected-flow 404/409s appearing in devtools (browsers always log
    failed requests; every case recovers gracefully in the UI).

- Fresh critic pass 4: **0 blockers, 0 majors**, 1 minor, 2 nits — the
  first clean pass. The minor (subject-verb agreement when exactly one
  unjudged pair stays blind) is fixed in both reveal banners; the nits are
  the already-accepted expected-flow 404 console entries and a React crash
  found only in console HISTORY from a pre-fix bundle (not reproducible on
  the current build after three targeted attempts). Pass 4 also verified
  the new reveal-confirmation flow end to end, the stale-bundle rescue
  script, exact hover-card anchor tracking (120px scroll → 120px card
  move), and that the raw /api/session JSON is blind at the wire level.

- Fresh critic pass 5: 0 blockers, 1 major, 3 minors, 2 nits — streak
  reset. All addressed:
  - MAJOR: gutters (line numbers + markers) were static table cells, so
    horizontal scrolling of long lines pushed them off-screen (measured
    −315px). Now sticky with stacked exact offsets (3.6em + 3.6em + marker
    at 7.2em) and opaque per-row backgrounds; locked by a new Playwright
    regression (scroll 400px right → gutter pinned at pane edge); the
    fixture now has a long line in every diff so any sampled pair
    exercises overflow.
  - Reveal with zero judgments is refused (server 409 + disabled strike +
    honest copy) — reveal isn't an abandon-session mechanism; the confirm
    screen always offers a way back (Keep judging / Back to the pairs /
    Start judging).
  - The two pre-redesign report artifacts (regenerable outputs, still
    setup-bench-branded) deleted — everything the Report page links is now
    on-brand.
  - Cost-visibility on the methodology axis re-flagged (critic 3 raised it
    too): kept AS DESIGNED — the phase-1 spec requires metrics during
    comparison, the decision rule breaks quality ties on cost, and
    Design's own session mockup shows them; values stay coarsened and the
    readout now carries an explanatory tooltip so the choice is visible in
    the product, not just the docs. Model/runner axes keep withholding
    them entirely.
  - Accepted: judge keys ignored while a judgment POST is in flight
    (idempotency guard — critic confirmed UI/API stay consistent).
  - Pass 5 also confirmed clean: wire-level blinding, the reveal
    lifecycle incl. double-strike idempotency and all four
    singular/plural copy states, sticky hover-card behavior through theme
    toggles, 900x600 overflow, the rescue script, API abuse tolerance.

- Fresh critic pass 6: **0 blockers, 0 majors**, 1 minor, 2 nits — clean
  pass #1 of the convergence streak. It verified the sticky gutter fix by
  measurement (gutter held x=357.0 exactly through a 400px horizontal
  scroll while code moved 400px), the 0-judged reveal refusal, wire-level
  blinding, and zero horizontal overflow across 7 routes × 3 viewport
  sizes. The three small items were fixed anyway: loading no longer
  flashes definitive empty-state copy (resume card shows "Loading…",
  picker axis badges show "…" until the fetch resolves); judge buttons
  expose the recorded verdict via aria-pressed; byte-identical A/B sides
  (possible in seeded demo cells) get a neutral "sides are identical"
  chip with a tie-by-construction tooltip.

- Live user review (2026-07-05, watching alongside critic pass 7):
  - **Spend metrics during blind judging: now hidden on EVERY axis** (user
    decision via AskUserQuestion, confirming what critics 3 and 5 flagged).
    The user's Opus-vs-Sonnet example was already covered (model axis), but
    they chose the strict policy over the spec's original
    show-during-comparison wording: pair payloads carry no cost/token/time
    fields at all; the side header shows "cost/time hidden (blind)" with a
    pointer to Reveal/Browse/Report. The `_coarse` machinery is gone.
  - While implementing that, found and fixed a real phase-1-era leak vector:
    the diff-shape proxy (`file_list`, counts) was computed on the RAW diff,
    so instruction files appeared in the file list and an agent-created
    filename carrying an axis id (e.g. `tdd_utils.py`) would have leaked
    unredacted. The proxy is now computed on the anonymized diff (new fast
    test seeds exactly that scenario).
  - **File navigator added** (user ask: "where can I select the file?"):
    multi-file pairs show a Files: row of chips; clicking scrolls BOTH panes
    (and the three-way table) to that file. Playwright test seeds a
    two-file diff and asserts both panes land on the target.
  - **A/B header alignment** (user-reported visual bug): side-header cards
    are now flex columns with the log-expander row bottom-anchored, so
    differing text wrap between A and B can't stagger the interior rows;
    to be verified live after the running critic pass releases the browser.
  - Also explained to the user: the dark dead space around the page in the
    shared browser is Playwright viewport emulation (fixed 1100×800/900×600
    test sizes inside a large window), not an app layout issue.
- Root cause of the user's misalignment report, found via the FIRST real-data
  session (results.db cosmos-B, 7 real .NET files): the global
  `.card + .card` stacking margin leaked into grid cells, shifting the
  second card of every grid row 16px down — session side headers, dashboard
  rows, trial detail. `.grid-2/3 > .card + .card { margin-top: 0 }`.
  Measured after: side headers topDelta 0; dashboard card tops 202/202 and
  474/474. Lesson logged: measurement-first review missed what a human
  eyeballing the screen saw immediately — later critic briefs now mandate
  reading full-size screenshots, and real-DB sessions are part of every
  verification pass.
- Real-data verification (previously only synthetic demo data was ever
  exercised): three-way view reconstructs REAL originals via git show from
  repos/cosmos (expandable gap rows work); file navigator drives 7 real
  files across both panes; gate logs are real dotnet output (identical
  lengths on both sides turned out to be deterministic builds differing
  only in equal-length worktree hashes — checked, not assumed); blinding
  holds on the real cell (no baseline/karpathy anywhere); mid-session DB
  switch errors helpfully and recovers on switch-back; paid-run estimate
  uses real history (mean of 6 cosmos-B×haiku trials ⇒ $0.22 for 2 reps,
  cross-consistent with the README's ~$0.11/trial); report on results.db
  is honest about 2 judgments < the BT minimum. Test session deleted from
  results.db afterward (no judgments were created).

- Fresh critic pass 8 (first with the explicit human-eyeball mandate +
  real-DB usage): 0 blockers, 2 majors, 4 minors, 8 nits — it found what
  the measurement-heavy passes missed, validating the user's push.
  - MAJOR: an open gate-log expander rendered a 6,000-char dotnet log in a
    third-width flex column (unreadable) → an open logbox now claims its
    full row (`.row > details.logbox[open] { flex-basis: 100% }`).
  - MAJOR: one stray click could write 55 free oracle trials into
    results.db — the SPEND gate protected money, not data. Free launches
    now take a two-click confirm whose second label names the target
    ("Confirm — write N trials into results.db"), re-arming on any target
    change.
  - Minors: preview-card sections were inline spans running together →
    display:block; catalog blurbs were raw YAML first-lines cut
    mid-sentence → normalized + word-boundary ellipsis; Report explains
    all-dash Elo/CI when 0 < judgments < 3; invalid/stale ?db= now shows
    a dismissible "switched to the default database" banner instead of
    silently rendering synthetic demo data (the real-vs-synthetic
    distinction is load-bearing).
  - Nits fixed: minutes formatting from 60s up; "(reported by the CLI)"
    instead of raw usd_self_reported; paths in diff headers break only at
    slashes via <wbr>; backticks removed from the manual-runner blurb;
    artifacts caption notes the list isn't DB-scoped. Accepted: theme
    toggle labels the action (standard pattern); three-way wraps deep
    indents (the price of aligned rows; two-way offers horizontal scroll).
  - Confirmed clean on real data: blinding in DOM + 59.5KB session JSON,
    file navigator (1433/1433 scroll lockstep), real originals with
    X-expandable gaps, sticky gutters, reveal lifecycle, spend gate with
    real $22.34 estimate. No sessions created on results.db (it resumed
    the pre-existing one read-only, 0 judgments).

- Fresh critic pass 9: **0 blockers, 0 majors**, 1 minor, 1 nit — clean
  pass #1 of the final streak. It confirmed every pass-8 fix by
  observation (full-width open logs on the real 6,046-char dotnet log,
  the two-step free confirm naming the DB, stacked preview cards, blurb
  ellipses, the under-powered-BT note, the bogus-?db= banner, minute
  formatting, slash-only path breaks) plus the standing invariants, XSS
  and path-traversal probes included. Fixes: the armed free confirm went
  stale when the SELECTION changed after arming (button offered the old
  trial count) — any parameter change now kills the whole plan preview,
  forcing a re-preview (target-DB edits only re-disarm); Playwright
  regression arms, flips a chip, asserts the plan dies. The legacy
  tiltyard.db localStorage key is now always removed.

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
