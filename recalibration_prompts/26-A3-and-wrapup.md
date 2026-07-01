# 26 — A3 real run, readiness check, docs reconciliation, final report

**Service:** Claude Code runs fully autonomously — no manual action during
the run. Grant permission once by launching in an autonomous permission mode.

**Run this after** `24-A2-cheap-methodologies.md` and `25-A2-custom.md`
(order doesn't matter between those two, but both should have run before
this one, so the docs reconciliation at the end reflects the true final A2
state). If either of those sessions never fully finished (e.g. `custom`
still has <3 real reps, or a methodology got stuck on the usage window),
that's fine — this session's docs step reports the honest state whatever it
is, it doesn't require perfection from 24/25.

**Context:** `23-A2-A3-real-run.md` (2026-07-01) ran A2's methodology-axis
real trials and got as far as finding + fixing two real bugs (`9b76a05`,
`6fc8e52`, `980f0e8`) before an account-level Claude usage-window cap ended
the session with partial A2 coverage. It never reached A3 (repo-context
axis) or the readiness/docs steps. This session picks up exactly there: A3's
real run, then the same readiness-check + docs-reconciliation + final-report
steps that `23` always intended to end with.

**A3 is cheap.** `baseline`/`none`/claude-haiku-4-5 already has 5 real reps
(way more than needed) from session 23 — this session only needs to add
`baseline`/`cosmos` (a repo-context never attempted yet), 3 reps, at the same
per-trial cost as the plain baseline trials (~$0.03-0.15 each). Total
expected A3 cost: well under $1. This session should comfortably fit its
usage window even combined with the wrap-up steps, which involve no new
`claude` CLI trials at all (one studio-executor `opus` dispatch for docs,
one `pytest` run).

**Important finding from session 23, carry it into the final report:** as of
that session, 0 of 6 real claude-haiku-4-5/claude-code trials on cosmos-A
passed the hidden gate (only the reference `oracle` runner passes — see
`grading_readiness()` in `core/db.py`: a "gradeable cell" needs >=2 DISTINCT
methodology values that EACH have a hidden-gate PASS, with repo_context/
model/runner held fixed). It's genuinely possible that even after sessions
24-26 add more real reps, `check_grading_ready.py` still exits 1 — that
would mean this is a *calibration* problem (the task's hidden gate may be
too strict for haiku), not a coverage problem, and it needs
`scripts/calibrate_tasks.py` + human judgment per `19-M-calibration-sweep.md`
— NOT something to fix in this session. Report the true number honestly
either way.

---

Paste the block below into a **fresh** Claude Code session, launched in an
autonomous permission mode.

---

```
You are the CONDUCTOR for this session and you run FULLY AUTONOMOUSLY. Do not
wait for approval on anything except the single cost-ceiling check in STEP 2
— make every other decision yourself and run to completion. You MAY run
cli.py directly on the main thread, but implement NO code fixes on the main
thread — dispatch a studio-executor subagent for any bug fix, TDD, one at a
time.

BACKGROUND (verified 2026-07-01 in session 23, do not re-derive — read
recalibration_prompts/26-A3-and-wrapup.md's context section first):
- Two bugs already fixed and committed (9b76a05, 6fc8e52, 980f0e8): a
  Windows subprocess encoding crash, and a bug where a claude-CLI-failed
  trial (zero tokens billed) used to get persisted permanently instead of
  staying retryable. A trial that dies in 2-5 seconds with 0 tokens billed
  is expected (account usage-window exhaustion) and cleanly retryable/free
  — do not treat it as a bug.
- baseline/none/claude-haiku-4-5/claude-code already has 5 real reps. Do not
  add more.
- scripts/check_grading_ready.py --db results.db exits 1 if every axis has 0
  gradeable cells, 0 if at least one axis has >=1. Use it as your readiness
  oracle throughout — don't hand-roll the query. See this prompt's context
  section for why it might legitimately still exit 1 even after this
  session — that's an acceptable, honestly-reportable outcome, not a failure
  of this session.

STEP 0 — CLEAN THE TREE:
- `git status --porcelain`. If any TRACKED files are modified/staged, commit
  them as ONE isolated "session: checkpoint wip" commit first. Confirm a
  clean tracked tree before proceeding.

STEP 1 — A3 real run (repo-context axis):
1. Dry-run: `.venv\Scripts\python.exe cli.py run --task cosmos-A --methodology
   baseline --repo-context all --model claude-haiku-4-5 --runner claude-code
   --reps 1 --dry-run`. Confirm `none` and `cosmos` appear and
   `pyvrp-instructions` is filtered out by task_affinity. Also confirm with
   `--full-matrix --dry-run` that the affinity override makes the nonsensical
   pairing appear (proves the filter is real, not a no-op).
2. Cross-check task_affinity the other direction (dry-run only, no cost): run
   a PyVRP task (e.g. pyvrp-A) with `--repo-context all --dry-run` and
   confirm `cosmos` is filtered out there.
3. Run for real: `.venv\Scripts\python.exe cli.py run --task cosmos-A
   --methodology baseline --repo-context all --model claude-haiku-4-5
   --runner claude-code --reps 3`. This should skip the 5 existing `none`
   trials and attempt exactly 3 fresh `cosmos` trials. If it attempts more
   than 3 new trials, STOP and check whether `none`'s existing rows were
   mis-detected as needing a retry — that would be unexpected given the
   fixes from session 23; investigate before proceeding rather than assuming
   it's fine.
4. Verify lay-down: for one new `cosmos`-context trial, inspect
   `run_result.diff` and confirm repo-context files land FIRST (before
   methodology) and actually match `repo_contexts/cosmos/`'s files, and that
   the graded diff itself contains only the agent's own work (same method
   session 23 used for karpathy — no new worktree needed unless something
   looks wrong).
5. If you find a REAL bug (wrong files, wrong lay-down order, crash) — not
   an expected hidden-gate FAIL or the known zero-token usage-window pattern
   — dispatch ONE studio-executor (model=sonnet) with a self-contained TDD
   brief. Cap at ONE fix attempt per distinct bug; if still broken, mark it
   a known issue and move on — do not loop.

STEP 2 — COST CHECK:
- Query cost_record for the trials STEP 1 just created and sum usd_equiv.
- If actual A3 spend is <= $5 (well above the ~$0.5 expected — something's
  off if you're above this): proceed straight to STEP 3, no need to ask.
- If actual A3 spend is > $5: STOP before spending more. Use
  AskUserQuestion once: report the actual spend and ask how to proceed.

STEP 3 — READINESS CHECK:
- Run `.venv\Scripts\python.exe scripts\check_grading_ready.py --db
  results.db`. Record its exit code and the per-axis table it prints. This
  is the authoritative, final state — use it, don't estimate.

STEP 4 — RECONCILE DOCS:
Dispatch ONE studio-executor (model=opus — this needs judgment about what's
now true) with this brief:

  GOAL: A2 (methodology axis: baseline/custom/ecc/karpathy/superpowers) and
  A3 (repo-context axis: none/cosmos) have now run for real against cosmos-A
  with claude-haiku-4-5/claude-code, across sessions 23 (recalibration_prompts/
  23-A2-A3-real-run.md), 24 (24-A2-cheap-methodologies.md), 25
  (25-A2-custom.md), and this session (26-A3-and-wrapup.md). Update the docs
  to reflect the actual final outcome — do not assume J1 is unblocked; check.
  FILES: docs/superpowers/recalibration-checklist.md ; RECALIBRATION_PLAYBOOK.md ;
  README.md (only the "Next up" bullet list)
  DO:
   1. Run `.venv\Scripts\python.exe scripts\check_grading_ready.py --db
      results.db` yourself to get the current, authoritative state.
   2. Query results.db for the final real-rep count per methodology and per
      repo-context (task=cosmos-A, model=claude-haiku-4-5, runner=claude-code)
      so your evidence notes cite real numbers, not estimates.
   3. In docs/superpowers/recalibration-checklist.md: tick A2 and A3 with a
      one-line evidence note each (real trial counts per value, models). If
      check_grading_ready exits 0, change the J1 line from its BLOCKED
      wording to reflect readiness (e.g. "- [ ] J1 grading UI shakedown —
      **READY: N gradeable cell(s), run `scripts/check_grading_ready.py` to
      confirm** — NEXT — CHECKPOINT"). If it still exits 1, update the J1
      line to name the blocker precisely: hidden-gate calibration (0
      claude-code trials passing cosmos-A's hidden gate across N real
      attempts), not missing axis coverage — point at
      `scripts/calibrate_tasks.py` / `19-M-calibration-sweep.md`.
   4. Update RECALIBRATION_PLAYBOOK.md's Phase J prerequisite note (added in
      commit bf50bb2) to match: either mark the A2/A3-real-run prerequisite
      satisfied (cite recalibration_prompts/23-26) with the calibration
      prerequisite still standing if relevant, or state precisely what
      remains.
   5. Update README.md's "Next up" J1 bullet to match reality (ready vs.
      blocked-on-calibration), same evidence style as commit bf50bb2 used.
  COMMIT: docs: reconcile checklist/playbook/README to final A2+A3 real-run
  outcome (sessions 23-26)
  Report back ONLY a <=4-line summary (files touched, commit SHA,
  check_grading_ready result). Do NOT paste diffs.

STEP 5 — COMMIT THE PROMPT FILES:
- `git add recalibration_prompts/23-A2-A3-real-run.md
  recalibration_prompts/24-A2-cheap-methodologies.md
  recalibration_prompts/25-A2-custom.md
  recalibration_prompts/26-A3-and-wrapup.md` (only if not already committed
  — check `git log --oneline -- recalibration_prompts/24-A2-cheap-methodologies.md`
  first). Commit as "docs: add A2/A3 real-run session prompts (23-26)" if
  needed.

STEP 6 — FINAL VERIFICATION AND REPORT:
- Run `.venv\Scripts\python.exe -m pytest -q` ONCE.
- Print a final report covering the WHOLE multi-session effort (23-26):
  - A2: final real rep count per methodology (baseline/custom/ecc/karpathy/
    superpowers), any excluded methodology + why, every bug found/fixed
    across all sessions (commit SHAs: 9b76a05, 6fc8e52, 980f0e8, plus any
    new ones from 24/25/26), total $ spent on A2 across all sessions.
  - A3: same shape (repo-context: none/cosmos), total $ spent.
  - check_grading_ready.py final exit code + per-axis table.
  - Full suite pass/deselect count.
  - Docs commit SHA from STEP 4.
  - Grand total $ spent across sessions 23, 24, 25, and this session.
- Do NOT launch the grading UI, do NOT start grading, do NOT run
  scripts/calibrate_tasks.py. Those are separate human-judgment steps
  (grading = "you are the gold standard" per RECALIBRATION_PLAYBOOK.md;
  calibration adjustments need human OK before touching a frozen golden
  task). Stop after the report.
```
