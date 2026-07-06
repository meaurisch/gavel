# 31 — J1: LLM-judge mode — adversarial shakedown + iterative hardening

**Service:** one autonomous Fable session (Fable plans, tests, fixes, and
converges itself — no conductor/executor split, matching prompt 28's model).
It runs critic passes until the mode survives them, in the same spirit as the
`fix: critic-pass-N` series that hardened the UI revamp.

**Before you start:**
- New chat, model **Claude Fable 5**, effort **xhigh**.
- Playwright MCP registered for the session (for human-eyeball screenshots;
  the pytest Playwright suite is separate and always available).
- Repo on branch **`llm-judge`** (6 commits on top of `ui-ux-revamp`), clean
  as of 2026-07-06: 371 fast tests + 22 integration tests green. The mode
  shipped working — this session's job is to try hard to break it, and to fix
  what breaks.
- Spend decision (yours, encoded below): the session may run **one** real
  claude-cli judged session, capped at **24 judge calls** on
  **claude-haiku-4-5** (subscription quota; ~$0.20–0.60 at API rates).
  Everything else uses the zero-spend `mock` provider. It must never launch
  the `claude-code` trial runner.

**How this works:** one paste. The feature is documented in
`docs/superpowers/specs/2026-07-06-llm-judge-design.md` and summarized in
CLAUDE.md/README — Fable reads those, then attacks the mode along eight axes
(blinding, parsing, races, migration, one bounded real run, UX, statistics,
cost accuracy), fixing findings TDD-style in `judge-critic-pass-N` commits
until two consecutive passes come up empty.

---

## Paste — the shakedown

```
You are stress-testing gavel's new LLM-as-judge grading mode on branch
`llm-judge`, FULLY AUTONOMOUSLY — make every decision yourself, never wait
for me, run to convergence. Your stance is adversarial: the mode was built
and tested by another session and everything is currently green; assume the
easy bugs are gone and the remaining ones hide in edge cases, races, and
dishonest numbers. Finding nothing after genuinely trying IS an acceptable
outcome for any single axis below — inventing cosmetic churn to look
productive is not. Every real finding gets a failing test first, then the
fix, then a commit.

STEP 0 — orientation and a clean tree.
- `git status --porcelain`: you must be on `llm-judge`. Commit any stray
  TRACKED changes as one isolated `chore:` commit before anything else.
  Leave untracked files (e.g. recalibration_prompts/30-E-*.md) alone.
  Never push; never merge into main or ui-ux-revamp.
- Read, in order: CLAUDE.md (the invariants), the two-modes section of
  README.md, docs/superpowers/specs/2026-07-06-llm-judge-design.md, then the
  implementation: grading/judge.py, grading/judge_providers.py,
  ui/judge_runs.py, the judge endpoints in ui/server.py, and
  ui/frontend/src/pages/{JudgeSession,GradePicker,Reveal,Report}.tsx.
- Baselines before you change anything:
  `pytest -q -m "not integration"` (expect 371 passed) and
  `pytest -m integration tests/test_ui_playwright.py -q` (expect 22 passed).
  If a baseline is already red, fixing that comes first.

PROTECTED INVARIANTS — these may never regress, and no test may be weakened
to get around them. If a fix and an invariant seem to conflict, the fix is
wrong:
1. The judge (and any blind surface) sees only anonymized diffs + gate
   scorecard booleans — never raw axis ids, cost, tokens, or wall time.
   grading.pairwise.redact_axis_ids is THE redaction implementation;
   run_pair's forbidden-token check is a safety net, not the mechanism.
2. Reveal requires explicit confirmation and closes a session permanently;
   unjudged pairs stay blind forever; a reveal racing a judge run aborts it.
3. Human and LLM verdicts never mix inside one session (judgment.grader,
   POST /api/judge refuses llm sessions, resume refuses human sessions).
4. Judge rationales and judge spend are served post-reveal only.
5. Non-free judging requires the typed JUDGE phrase server-side (the UI gate
   is convenience; the server check is the invariant).
6. The trial model never sees the held-out oracle (untouched by this work —
   keep it that way).
7. Frozen golden tasks change only with an explicit human OK — this session
   has none, so tasks/ is read-only for you.

SPEND RULES — hard limits:
- All pipeline/UI/regression work uses the `mock` provider on scratch or
  copied DBs. Axis 5 below is the ONLY real-provider work: one claude-cli
  judged session, ≤ 24 judge calls total (count them via the judge_call
  table), model claude-haiku-4-5, on a COPY of results.db — never the
  original. If the cap would be exceeded, use fewer pairs (single-pass or a
  smaller cell), don't raise the cap.
- Never launch the claude-code trial runner. Never bypass the JUDGE/SPEND
  typed gates by editing the gate code.

THE EIGHT ATTACK AXES — work them in this order. For each: probe hard, write
failing tests for real findings, fix, commit, move on.

1. ADVERSARIAL BLINDING. Build scratch DBs whose content actively tries to
   leak the varying axis into the judge's view: axis ids glued into
   identifiers (snake_case, kebab, CamelCase edges), ids in new-file PATHS in
   diff headers, ids inside JSON/string literals in the diff body, ids that
   collide with English words or substrings of each other, task instructions
   that mention a pinned axis value, sb-wt-<hex> worktree paths baked into
   committed content, and gate scorecards for trials with missing tiers.
   Assert at three layers: the prompt handed to the provider (recording mock),
   the SSE /api/judge-runs events stream, and the rendered progress-page DOM.
   Repeat for axis=model and axis=runner, not just methodology. Also verify
   the BlindingError path: when redaction genuinely can't hold, the run must
   fail closed BEFORE any provider call, with a clear error surfaced in the
   UI — never fail open.

2. VERDICT-PARSING ROBUSTNESS. Fuzz parse_verdict/_call_with_retries with
   hostile provider replies: fenced JSON, JSON with leading AND trailing
   prose, braces inside the rationale string, two JSON objects in one reply,
   single-quoted pseudo-JSON, confidence as string/NaN/negative, rubric with
   unknown keys/values, empty reply, 100KB reply, unicode punctuation. Check
   the retry loop: the correction prompt must carry the error AND stay under
   any size assumptions; a provider that fails transport-level mid-session
   must leave the session resumable with prior judgments intact (kill the
   provider on pair N and prove pairs 0..N-1 survive and resume finishes
   the rest without re-judging them).

3. CONCURRENCY AND LIFECYCLE RACES. Reveal (POST /api/reveal) while a judge
   run is mid-flight — the run must abort without writing post-reveal
   judgments. Cancel timing (cancel between pairs; cancel then resume;
   double-cancel). Two judge starts racing (only one may win). Server
   restart mid-run: judgments persist, /grade/judge/:id reattaches sanely
   (runMissing path), resume completes the remainder. Switching the DB
   picker while a run is active. Human session and llm session on the same
   cell concurrently (allowed — verify no cross-talk). SQLite contention:
   hammer /api/session reads while the worker writes.

4. SCHEMA MIGRATION ON REAL DATA. Copy the real results.db AND
   results-demo.db to scratch; open each with the new code. Assert: legacy
   sessions read as human-mode, legacy judgments as grader=human, report
   numbers for grader=all exactly match the pre-branch numbers for the same
   DB (compute the old numbers by checking out the merge-base into a
   worktree if you need ground truth), reveal of an old human session still
   works, and nothing ever writes to the originals.

5. ONE BOUNDED REAL RUN (the only real spend — see SPEND RULES). On a copy
   of results.db, judge the real cosmos-B gradeable cell with claude-cli /
   claude-haiku-4-5, double-pass if it fits the 24-call cap, else
   single-pass. Then audit honestly: did usage/cost parsing capture real
   tokens per call; did any call need the retry loop (check judge_call
   statuses); what was the position-consistency rate; and READ the
   rationales against the actual diffs — are they grounded (cite real
   differences) or generic? Compare the plan estimate shown before the run
   to the actuals in judge_call; if input-token or call-count estimates are
   off by more than 2x, fix the estimate constants in ui/judge_runs.py.
   Record the whole audit in the final report. If the claude CLI is not
   logged in, mark this axis SKIPPED with the reason — do not substitute a
   different paid path.

6. UX CRITIC PASSES (Playwright MCP, human-eyeball). Screenshot every new
   surface in light AND dark, at 1440/1100/900 widths: picker with the judge
   config panel open (available and unavailable providers; the armed and
   disarmed JUDGE phrase states), progress page in-flight / done / error /
   cancelled / stale-run-after-restart, reveal with judge stats + rationale
   column (long rationales!), report with the grader filter and agreement
   card, dashboard + picker resume lists with LLM badges. Hunt: clipping,
   overflow, contrast, focus/keyboard access, aria states, spinners that
   never resolve, copy that lies about state (e.g. progress text during
   resume), the plan banner going stale when the provider changes, and any
   surface where an unrevealed llm session shows anything cost-shaped.
   Fix what you find; after ANY frontend change, `npm run build` in
   ui/frontend, then re-run the full integration suite.

7. STATISTICAL SANITY. cohens_kappa and grader_agreement edge cases: all
   ties, one shared pair, constant labels for one rater, disjoint pairs,
   reversed orientations mixed with duplicates. Bradley-Terry fed tie-heavy
   llm sessions (swap-disagreement produces ties — confirm the ranking
   degrades gracefully, not misleadingly). Grader-filter arithmetic vs hand
   counts on a constructed DB. The report's agreement scoping when a cell
   pin is set. merge_passes truth table exhaustively.

8. COST-EFFICIENCY AUDIT. Measure real prompt sizes for the demo DB's
   diffs; check the 60k-char diff budget triggers where intended and the
   truncation marker survives to the judgment row; confirm the static
   preamble is byte-identical across pairs of a session (the caching
   assumption); look for redundant per-pair DB work in the worker loop
   (blinding map is built once — keep it that way). Tune only what
   measurement justifies.

ITERATION PROTOCOL.
- TDD for every fix: failing test → fix → full fast suite; integration
  suite after any UI or server-payload change. New regression tests stay.
- Commit per coherent batch: `fix: judge-critic-pass-N — <what>` (follow the
  existing critic-pass style in git log). Docs-only changes as `docs:`.
- A pass = one full sweep of whichever axes still have open threads.
  CONVERGENCE = two consecutive passes producing zero new findings, both
  suites green, and the real-run audit written up.
- If a finding implies a design change that would break a protected
  invariant or exceed this scope (e.g. multi-judge ensembles), do NOT build
  it — record it in the deferred list instead.

FINAL REPORT, then STOP.
- Update README's current-state section and the design doc's testing section
  with anything material you learned (the real-run audit numbers belong in
  the design doc).
- Print: findings table (axis, finding, CONFIRMED/FIXED/DEFERRED, commit
  SHA), the real-run audit (calls, tokens, $-equiv, consistency rate,
  rationale-groundedness verdict, estimate-vs-actual), final suite counts,
  and the full list of commits this session made. Then stop — do not start
  new feature work, do not merge, do not push.
```
