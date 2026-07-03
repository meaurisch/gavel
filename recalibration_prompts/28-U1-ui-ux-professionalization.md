# 28 — UI/UX professionalization + rebrand (two-phase Fable session + Claude Design interlude)

**Service:** one Fable session run in two turns, with a human-driven Claude
Design interlude between them — not the studio-conductor/executor split used
by earlier prompts in this directory (Fable plans and executes this itself).

**Before you start:**
- New chat, model **Claude Fable 5**, effort **xhigh**.
- Playwright MCP registered for the session (as before — see prompt-file
  history if you need the setup command).
- A Claude Design account for the interlude (Pro/Max/Team/Enterprise — it's a
  research preview) — that step is yours, not Fable's; Fable cannot call
  Claude Design itself, it's a separate human-facing product, not an MCP
  tool or API.
- Repo clean on `fable-run` as of 2026-07-03 (267 tests green).

**How this works:** this is deliberately two pastes into the *same* session,
not one. Phase 1 builds and functionally verifies everything — data
plumbing, the unified dashboard, the redesigned picker, the fixed diff
screen, the run launcher — using deliberately plain, unstyled-looking
defaults, because a bespoke visual pass done twice (once by Fable guessing,
once redone to match Claude Design's output) is wasted work. Phase 1 ends by
screenshotting the real, working screens and writing its own Claude Design
brief from them — grounded in actual screens and actual data, not a
speculative text description — then it stops, because the next step
genuinely requires you. You take that brief into Claude Design yourself,
iterate, and export the result. Phase 2 resumes the same session, implements
Claude Design's output onto the already-correct functional base, re-verifies
nothing broke, and converges.

---

## Paste 1 — Phase 1: build it right, style it plain

```
You are doing a rebuild of `setup-bench`'s web UI, in two phases. This is
phase 1. Read `README.md`, `CLAUDE.md`, and `IMPLEMENTATION_PLAN.md` first —
they are the spec and describe the engine you are NOT here to rebuild. The
engine, gate, and grading math are correct and well-tested (267 tests green);
the problem this whole effort is fixing is presentation and UX. The person who
built this wants it to eventually be shared publicly, at a quality bar that
would win recognition on GitHub — something a stranger could clone,
understand, and enjoy using within minutes, judged by someone seeing a
screenshot for the first time.

======================================================================
WHY THIS IS SPLIT INTO TWO PHASES — READ THIS BEFORE YOU START STYLING ANYTHING
======================================================================

Phase 1 (this paste) is structure and correctness ONLY. Get every screen
built, wired to real data, and functionally verified — but deliberately
*plain looking*: default/neutral colors, system fonts, no hand-tuned visual
polish, no bespoke logo treatment. Do not spend effort making this look good
yet. The reason: at the end of this phase you will hand real screenshots of
these screens to Claude Design (Anthropic's visual-design product) to build
the actual design system and mockups, and then a phase 2 (a later message in
this same session, after a human-driven Claude Design interlude you cannot
do yourself) will implement that design onto the functional base you build
now. Any bespoke visual effort you spend in phase 1 gets thrown away in
phase 2 — so don't spend it. What phase 1 SHOULD get right structurally,
because redoing it in phase 2 would be expensive: correct information
architecture, correct data flowing to every screen, a real (if boringly
styled) design-token scaffold (see below), and correctness of the trickier
interactive bugs (diff layout, scroll tracking, blind-grading safety).

Build your CSS/component layer so restyling in phase 2 is a token/value swap,
not a rebuild: define one shared set of design tokens (CSS custom properties
or your framework's equivalent — color, spacing, type scale) used by every
screen, and one shared set of base components (buttons, badges, cards,
selects, nav, tables) used everywhere rather than one-off styles per page.
Give the tokens boring placeholder values now (e.g. grayscale + one accent) —
phase 2 replaces the values, not the architecture.

======================================================================
OPERATING MODE
======================================================================

You are operating autonomously through phase 1. Nobody is watching in real
time and nobody can answer questions mid-task, so make the call yourself on
anything reversible — which, on a local git branch with no remote, is nearly
everything — and keep going. The one genuine stop is the end of phase 1
itself (see "END OF PHASE 1" below): that's a real external dependency, not
a check-in habit.

Before ending any turn before that point, check your last paragraph: if it's
a plan, an analysis, or a promise about work you haven't done, go do that work
now instead of ending the turn.

You have ample context and time for this — it's meant to run for hours,
don't stop or suggest a follow-up session on account of length.

Don't add features, refactor, or introduce abstractions beyond what's asked
below; don't design for hypothetical future requirements. At the same time,
don't leave things half-done — every item in phase 1's definition of done
needs to be fully finished or explicitly, visibly deferred with a reason in
your end-of-phase report. No silent gaps.

Ground every progress claim in an actual tool result from this session. If
you say a bug is fixed, it's because you drove the running app (via
Playwright) and observed the fix, not because the code looks right.

Keep a running notes file at `docs/ui-revamp-log.md`: one line per
significant decision or fix, what and why and how you verified it. This is
your memory across a long session — check it before assuming you haven't
tried something yet.

Delegate freely. Use subagents for independent verification passes — in
particular, a fresh-context "picky senior open-source maintainer" critic
that drives the live app with Playwright and tries to find what's still
wrong, with none of your context to anchor on. Keep working on the next
slice while a subagent runs rather than blocking on it where the two are
independent.

======================================================================
GIT WORKFLOW
======================================================================

Confirm the tree is clean, then create a new branch off the current HEAD
(e.g. `ui-ux-revamp`) and do all work there. Commit incrementally with real,
descriptive messages as you finish each piece — mirror the existing commit
style (`git log` for examples). Do not merge into `fable-run` or `main`, and
do not push anywhere — there's no remote configured; the human reviews and
merges by hand.

======================================================================
THE USER'S RAW FEEDBACK ON THE CURRENT UI (verbatim — this is your actual spec)
======================================================================

"Everything about the UI screams 'local hobby project' instead of
'professional looking project of great programmer with help from best LLM
available'. This should be fixed." (Note: the VISUAL half of this is phase
2's job via Claude Design. The STRUCTURAL half — confusing flow, hidden
functionality, missing information — is yours now.)

"I can only select 'Methodology' in the 'Select axis...' drop down. But in
general: I should be able to select runs and what repository I want to use,
in some way. How is this chosen right now? EDIT: I see that later, I can
choose task, repo context, model and runner. I do not see why this should
only be visible after selecting the axis. UX is bad here too. One of the many
flaws: I do not know which task 'cosmos-B' is. User should get some preview or
something on hover (just first idea that pops up, can be solved differently)
to get reminded what task it is. Same for all other choices."

"It is very confusing to me how to use the app. We should have one central
point of entry, from where all functionality can be reached."

"After having chosen all options, I am looking at the diff screen. I like the
concept: split screen without many distractions, clear A and B. What I want
additionally: the option to have a three-way split screen: original (neither
change applied) | A | B. The current view should also be available."

"Other than that, the diff screen does not work at all, because there are
many very big bugs. To name just a few: line numbers do not change when
scrolling, so they are practically always next to the wrong line; the split
of the screen is not in the middle, but A gets far more screen space than B;
but there are many more."

"I do not see how I can get insight in whether a run passed all tests. User
should get far more info than only the check marks for 'Build', 'Visible' and
'Hidden'."

Also apply the general, unstated bar behind these comments: the grading UI
needs to hold up for real, hours-long grading marathons (many pairs judged
back-to-back), not just look good in a single screenshot. Keyboard-first
flow, low fatigue, no dead ends, no state loss.

(The naming/logo/palette comment from the original feedback is intentionally
NOT listed above — that's what the Claude Design interlude is for. See
"NAMING — provisional only" below for what phase 1 should do about it.)

======================================================================
DECISIONS ALREADY MADE (don't re-litigate these)
======================================================================

1. FRONTEND: a full modern rewrite is approved — the current UI is a single
   1124-line static HTML file, no framework, no build step. Replace it with
   whatever stack you judge best for a maintainable, polished result (a
   React/Vite/TypeScript-class stack is a reasonable default). Keep the
   backend in Python/FastAPI.

   HARD CONSTRAINT: setup must stay "clone and go" — minutes, not hours, for
   someone who is not you. Whatever frontend tooling you introduce MUST be
   folded into the existing one-shot bootstrap so a fresh clone still becomes
   runnable with the single existing command (`.\tasks.ps1 Setup` → `python
   cli.py setup`). Extend `cli.py setup` and `python cli.py doctor` to
   install/build the frontend and check Node/npm readiness the same way they
   already check git/dotnet/WSL. Update `README.md`'s Quickstart to match.
   No new paid services, no accounts, no cloud build — fully local and
   offline.

2. UNIFIED ENTRY POINT: build one home dashboard that is the single
   documented way to use the tool, reachable with one command. It must let
   the user browse existing results/DBs, launch a grading session (with the
   redesigned picker below), view reports/rankings, AND launch new trial
   runs with live progress streamed into the browser — all cross-linked, no
   dead ends back to a bare terminal.

   Don't reinvent the runner for the "launch runs" piece: `core/executor.py`'s
   `execute_all(trials, conn, delay=..., on_progress=..., ...)` already takes
   a progress callback (see how `cli.py`'s `run` command wires it into a Rich
   `Live` table today). Reuse that hook — call `execute_all` from a
   background task and push `on_progress` updates to the browser (SSE or
   WebSocket) instead of building a second execution path.

   HARD CONSTRAINT — spend safety: running real trials with the
   `claude-code` runner spends real API money (see `CLAUDE.md`). The browser
   run-launcher MUST default to a free runner (`oracle`/`nop`/`manual`) and
   MUST require an explicit, unmissable confirmation before it will invoke a
   paid runner, plus show whatever cost estimate you can derive from
   `cost/pricing.toml` and historical trials. When YOU test this yourself,
   only ever exercise it with `oracle`/`nop`/`manual` against the demo DB or
   a scratch DB — never trigger a real billed `claude-code` trial.

3. NAMING — provisional only: pick a working project name now (you'll need
   one for page titles, `pyproject.toml`, a placeholder favicon, etc.) and
   document your one-line reasoning in `docs/ui-revamp-log.md`, but treat it
   as provisional — a plain text wordmark, no logo, no special typography.
   The actual visual identity (logo/wordmark treatment, palette, type) is
   Claude Design's job in the interlude below; don't invest design effort in
   the name's presentation yet, just pick something real to build against
   instead of leaving "setup-bench" as an afterthought.

======================================================================
CRITICAL INVARIANT — DO NOT BREAK BLIND GRADING
======================================================================

This is the one thing in this whole effort that would be a real regression,
not just a UX nit, if you get it wrong. Read `grading/pairwise.py`'s
`anonymize_diff()` and `CLAUDE.md`'s "Protected invariants" section before
touching anything grading-related.

The whole point of the pairwise grading screen is that the grader cannot tell
which VALUE of the comparison axis produced side A vs. side B. Every feature
you add that surfaces more information (hover previews, gate log details,
cost/tokens, anything) must respect this:
- On the axis/cell PICKER screen (before a grading session starts), showing
  full detail about every methodology/task/model/etc. is fine — nothing is
  blind yet.
- Once a grading session is showing an actual A/B pair, anything displayed
  about that pair must reveal nothing about the value of the
  CURRENTLY-VARYING axis. Info about the pinned/fixed axes is fine. If
  you're unsure whether a piece of data (a log line, a file path in a stack
  trace, a cost/token count that might correlate with a specific model)
  leaks the varying axis, don't show it during comparison, or redact it the
  same way `anonymize_diff` already redacts axis ids from the diff text.
- Write an automated test that actually asserts this — start a grading
  session on each axis and check the rendered page for every raw id string
  of every OTHER value of that axis. This test must still exist and pass
  after phase 2 restyles everything — a phase-2 instruction below tells you
  (future you) to re-run it, but write it durably now.

======================================================================
WHAT'S ALREADY BEEN TRACED — verify by testing, but you don't need to
re-diagnose these from scratch
======================================================================

Diff-screen bugs in the current `ui/static/index.html` (being fully replaced
by your rewrite — root causes below are context for building the new
version correctly, not a description of code you need to patch):
- Unequal A/B width: `.diff-columns { grid-template-columns: 1fr 1fr; }`
  looks right, but neither it nor its children set `min-width: 0`. CSS Grid
  items default to `min-width: auto` (their content's intrinsic min-width),
  so one long unwrapped code line (the vendored diff2html CSS forces
  `white-space: nowrap` on code lines) blows out that column past `1fr` and
  steals width from the sibling. Any split-pane layout needs `min-width: 0`
  on the flex/grid children plus `overflow-x: auto` (scroll, don't blow out)
  on the scrollable content — verify this holds with an actual measured
  bounding-rect assertion, not "the CSS looks like 50/50."
- Line numbers not tracking scroll: diff2html's line-number gutter is
  `position: absolute`, dropped into a plain scrolling `<div>` with no
  positioning context reinforced for it, so its containing block ends up
  wrong and it doesn't move with the code as you scroll. Whatever diff
  renderer you use, verify line numbers move in lockstep with content by
  scrolling programmatically (Playwright) and measuring the line-number
  element's position relative to the code line it labels.
- No sync between the two panes, no three-way view, and diff2html was used
  in single-column mode independently in each pane — the A/B split is
  entirely the app's own two divs, not diff2html's own side-by-side mode.
  Pick whatever diff-rendering approach gives you the least bug surface for
  correct line numbers and a clean three-way layout.

Data that's already captured but never reaches the picker or the comparison
screen — mostly backend plumbing, not new instrumentation:
- `methodologies/<id>/manifest.yaml` and `repo_contexts/<id>/manifest.yaml`
  already have a human `description:` field, parsed by `core/manifest.py`
  then dropped — `core/methodology_loader.py`/`core/repo_context_loader.py`
  never carry it into `MethodologySpec`/`RepoContextSpec` (`core/models.py`).
  Task instruction text and a `difficulty` field already live in `task.yaml`
  and the `task_spec` DB table, but no `/api/*` endpoint returns them.
- `GateResult` (`core/models.py`, `gate_result` table) already stores the
  full raw `compile_output`/`visible_output`/`hidden_output` (stdout+stderr
  of every gate tier — see `grading/gate.py`), plus `CostRecord` (tokens,
  USD) and `RunResult.wall_seconds` per trial — none of it reaches the
  browser today; `ui/server.py`'s pairs endpoint narrows the gate to three
  booleans. There is no structured per-test parsing anywhere (no test
  names/counts/failure messages), only opaque combined console output.
  Surfacing the raw logs (e.g. a collapsible "view build/test output" per
  side, plain `<details>` markup is fine for now — phase 2 restyles it) is
  straightforward since the data exists; parsing `pytest`/`dotnet test`
  output into structured per-test results (via `--junit-xml`/a trx logger)
  is strictly better but bigger — use your judgment, and if you skip it, say
  so explicitly in your end-of-phase report.
- For the three-way "Original | A | B" view: there's no field that hands
  you "the file content before the agent touched it," but the system is
  fully deterministic — a task's `base_commit` plus its
  `repo_contexts/<id>` and `methodologies/<id>` manifests fully determine
  the pre-agent starting point. Investigate `core/worktree.py`,
  `runners/base.py`, and `grading/gate.py`'s `BASELINE_REF` to see whether a
  pre-agent commit is durably recorded post-teardown; if not, the clean
  solution is likely reconstructing "Original" on demand (replay
  repo-context + methodology onto the task's base commit in a throwaway
  checkout, same as trial prep does) rather than persisting more state.
  Design this properly — it's worth getting right once.
- "Far more info than 3 checkmarks" should include at minimum: the raw
  per-tier logs, and cost/tokens/wall-time visible DURING comparison
  (currently only visible later in Reveal/stats).

Also note: `README.md`'s "Current state" section claims the grading UI "was
shaken out with Playwright," but no Playwright test exists anywhere in the
repo — that exploration was never captured as a real regression test. Fix
that here: your own Playwright work should leave behind real, committed,
passing tests, not just a claim in a doc.

======================================================================
TESTING METHODOLOGY
======================================================================

Work in small vertical slices (e.g. "picker screen with hover previews,"
"diff screen layout + three-way toggle," "unified dashboard shell," "run
launcher") and for each slice: build it, drive the real running app with
Playwright (MCP tools if available; otherwise Python `pytest-playwright`,
which fits this repo's `pytest` convention — see `CLAUDE.md`) and actually
exercise the feature — scroll the diff panes and measure whether line
numbers track, measure both panes' bounding-box widths, hover every picker
option and check the preview renders correct content, start a grading
session and grep the rendered page for other axis values (the blinding
check), simulate a longer session (many pairs) and check nothing degrades.
Turn the meaningful checks into committed, passing automated tests (follow
this repo's existing `integration` marker convention in `pyproject.toml` for
anything needing a live server/browser, so default `pytest` stays fast and
`CLAUDE.md`'s "full suite must stay green" still holds). Log what you found
and fixed in `docs/ui-revamp-log.md`, then move to the next slice.

======================================================================
END OF PHASE 1 — do this, then STOP
======================================================================

When every item in phase 1's definition of done (below) is met:

1. Commit everything. Confirm `pytest` is fully green.
2. Using Playwright, take real screenshots of every key screen in its
   current (functionally correct, plain-styled) state: the unified
   dashboard/home, the axis+cell picker with a hover preview visible, the
   diff comparison screen (both the existing two-way and the new three-way
   view), the run launcher, and the report/ranking view. Save them under
   `docs/design/screenshots/`.
3. Write a Claude Design brief to `docs/design/claude-design-brief.md`,
   following the same shape this project already uses for Design handoffs
   (see `recalibration_prompts/15-J1-design-ui-critique.md` for the
   pattern/tone — yours is bigger in scope but the same idea: describe what
   the tool is and who uses it, attach/reference the screenshots, list every
   screen that needs a real visual design pass, and state the constraints
   Design needs to respect). Include explicitly:
   - What `setup-bench` is and who uses it (a developer comparing coding-
     agent setups, judging blind A/B diffs repeatedly for potentially hours).
   - The provisional name you picked and why, asking Design to build a real
     visual identity around it (or propose a refinement) — logo/wordmark,
     color palette, type scale.
   - One design system used consistently across every screen (this is a
     hobbyist-vs-professional signal called out explicitly in the original
     feedback) — request exportable design tokens plus either component
     code or precise visual specs you can implement faithfully.
   - The full screen inventory with your screenshots attached/referenced:
     dashboard/home, picker (with the hover-preview interaction described),
     diff comparison (two-way AND three-way), run launcher (including the
     paid-runner confirmation gate), report/ranking view.
   - Constraints Design must respect: needs to stay comfortable across
     hours-long repeated-judgment sessions (low visual fatigue, clear
     keyboard-first affordances); must not introduce any visual pattern that
     would let a grader distinguish sides during blind comparison (no
     per-side iconography/color that could imply "this is the X one" beyond
     the neutral "A"/"B" labels); no external font/asset dependencies that
     require network access at runtime (self-contained, local-first, same as
     the rest of this project).
4. End your turn with a short, plainly-written message (not a continuation
   of your working shorthand — the human is reading this cold) stating: what
   phase 1 built and fixed, that tests are green, where the brief and
   screenshots are, and that you're stopping here because phase 2 needs a
   human-run Claude Design session you cannot do yourself. Do not attempt
   phase 2 work after this point in this turn.

======================================================================
PHASE 1 DEFINITION OF DONE
======================================================================

- [ ] Every specific bug quoted in the user's feedback above is verifiably
      fixed — each backed by an automated Playwright assertion.
- [ ] One unified dashboard is the single entry point: grading, reports/
      rankings, browsing past results, and launching new runs (with the
      spend-safety gate), all cross-linked.
- [ ] Task/methodology/repo-context/model/runner are all visible and
      previewable up front (not hidden behind picking an axis first); the
      blind-grading invariant is verified by an automated test, not assumed.
- [ ] Diff screen: A/B split measurably equal, line numbers measurably track
      scroll, a three-way Original | A | B view exists alongside the
      existing two-way view.
- [ ] Test/gate results show materially more than three checkmarks (raw
      per-tier output, cost, tokens, wall-time, visible during comparison).
- [ ] One shared design-token/component scaffold is used by every screen
      (boring placeholder values are fine — the architecture is what
      matters for phase 2).
- [ ] Tool installs and runs from a fresh clone via the existing one-command
      setup flow in a few minutes; `doctor` reflects any new prerequisites.
- [ ] Committed, passing Playwright regression tests exist for all of the
      above; full `pytest` suite green.
- [ ] Screenshots + Claude Design brief written to `docs/design/`; turn
      ended with the human-facing summary described above.
```

---

## Interlude — you, not Fable: Claude Design

Once Fable's phase-1 turn ends, open `docs/design/claude-design-brief.md`
and look at `docs/design/screenshots/`. Take the brief into a Claude Design
session (paste it, attach the screenshots). Iterate until you're happy with
the design system and the mockups for each screen. Export what Design gives
you — design tokens/CSS, any generated component code (React/HTML/SVG), and
final mockup images — and save it into the repo under `docs/design/exports/`
(or just have it ready to attach when you send the next message; either
works, but saving it into the repo means it's a durable artifact like the
existing screenshots under `docs/screenshots/`).

If Claude Design isn't available to you for some reason, phase 2 below still
works — just tell Fable to use its own judgment on the visual system instead
of Design's output, and skip the "implement Design's output" instructions.

---

## Paste 2 — Phase 2: apply the design, verify, converge

```
This is phase 2, same session as phase 1. Claude Design's output is at
`docs/design/exports/` (or attached to this message) — treat it as the
authoritative visual spec. Implement it onto the functional base you already
built in phase 1: apply the real design tokens/component styles across every
screen (dashboard, picker, diff comparison, run launcher, report view,
favicon, page titles) so the whole app reads as one consistent, deliberately
designed product — this is the "hobby project vs. professional" fix the
whole effort exists for.

You are still operating autonomously and still under all the phase-1
constraints: don't break blind grading, don't touch the paid runner
yourself, keep the git workflow (same branch, incremental commits, no
merge/push), keep `docs/ui-revamp-log.md` updated, ground every claim in an
actual tool result, and don't stop early — see phase 1's "OPERATING MODE"
section above, it still applies.

Restyling is exactly the kind of change that can reintroduce the bugs you
already fixed once (a new component layout can just as easily forget
`min-width: 0`, or a redesigned diff view can lose the line-number-to-content
binding). Don't just eyeball the result — re-run the specific Playwright
assertions from phase 1 (A/B width equality, line-number scroll tracking,
the blind-grading redaction check) against the restyled app and confirm they
still pass. Re-run the full `pytest` suite.

Then converge: dispatch a fresh-context subagent with no memory of this
session, playing a skeptical senior engineer reviewing an open-source PR.
Give it Playwright access and the definition of done below (plus phase 1's),
and have it actually use the running app end to end. Fix whatever it finds
and re-run it. Stop iterating once two consecutive fresh critic passes turn
up nothing new above minor polish.

Finally: update `README.md`, `CLAUDE.md`, and `tasks.ps1` to reflect the
final reality (name, commands, setup steps, screenshots) — no stale claims
like the untested-Playwright one you already fixed in phase 1. Write a final
report: what changed across both phases, the branding/design rationale
(yours from phase 1, Design's from the interlude), anything explicitly
deferred and why, and how to run it — written for someone re-grounding cold,
not a continuation of your working shorthand.

PHASE 2 DEFINITION OF DONE (in addition to phase 1's, which must still hold):
- [ ] Every screen visually matches Claude Design's exported system/mockups,
      applied consistently — no screen looks like it came from a different
      project than another.
- [ ] The phase-1 correctness assertions (A/B width, line-number tracking,
      blind-grading redaction) still pass after restyling.
- [ ] Two consecutive fresh-context critic passes find nothing beyond minor
      polish.
- [ ] Full `pytest` suite green; `doctor` green (or correctly reflects
      prerequisites).
- [ ] `README.md`/`CLAUDE.md`/`tasks.ps1` updated to match final reality.
- [ ] Final report written as described above.
```
