# 23 — A2 + A3 real run, autonomous (Claude Code)

**Service:** Claude Code runs fully autonomously — no manual action during the
run. Grant permission once by launching in an autonomous permission mode
(e.g. `--dangerously-skip-permissions` / accept-edits / bypass-permissions) so
the `cli.py run` calls (which spend real API budget) and commits don't stop to
prompt per-command. That single launch-time grant is the "permission" this
prompt needs; it should not otherwise ask you anything.

**Context:** `22-J1-prereq-fixes.md` (run 2026-07-01, commits `fb11e10`,
`c68ab4d`, `5bdb92c`, `bf50bb2`) found `results.db` has 0 gradeable cells
because A2 (`08-A2-methodology-axis.md`) and A3 (`09-A3-repo-context-axis.md`)
were only ever dry-run — `methodology` and `repo_context` each have exactly
one real value (`baseline`, `none`) across every trial. This prompt runs both
axes **for real** (drop `--dry-run`), fixes any real bugs it finds the same
way A2/A3 always intended ("fix issues with TDD + commits"), then reconciles
the checklist/playbook/README to whatever the *actual* outcome is — which may
still be "0 gradeable cells" if reps=3 real trials fail the hidden gate (an
uncalibrated-task problem, not a plumbing problem — see the honesty note at
the end).

**Cost is small and bounded.** One real haiku/baseline/none trial on cosmos-A
(from A4) cost **$0.081**. This run uses the same cheapest model
(`claude-haiku-4-5`) and the same runner (`claude-code`), at **reps=3** (the
project's settled default, see `IMPLEMENTATION_PLAN.md` §7) instead of the
shakedown default of reps=1 — reps=1 already proved this is exactly the
regime where real trials fail the hidden gate and produce nothing gradeable,
so reps=3 is the deliberate fix, not scope creep. Worst-case trial count is
~21 (5 methodologies + 2 repo-contexts, × reps=3); even at 5x the reference
per-trial cost that's under $10. The prompt still checks actual spend after
phase 1 and stops to ask before phase 2 if it's unexpectedly high (see STEP
2).

---

Paste the block below into a **fresh** Claude Code session, launched in an
autonomous permission mode.

---

```
You are the CONDUCTOR for this session and you run FULLY AUTONOMOUSLY. Do not
wait for approval on anything except the single cost-ceiling check in STEP 2 —
make every other decision yourself and run to completion. You MAY run cli.py
directly on the main thread (running the harness is not "implementation"), but
implement NO code fixes on the main thread — dispatch a studio-executor
subagent for any bug fix, TDD, one at a time.

BACKGROUND (verified 2026-07-01, do not re-derive):
- Goal: get real gradeable data for the methodology (A2) and repo-context (A3)
  axes so J1 (grading UI shakedown) is unblocked. Currently results.db has
  methodology="baseline" and repo_context="none" on every trial — A2/A3 never
  ran for real.
- Reference cost: one real claude-haiku-4-5/claude-code/baseline/none trial on
  cosmos-A cost $0.081 (51 input / 11624 output tokens). Methodologies pack:
  baseline, custom, ecc, karpathy, superpowers. Repo-contexts: none, cosmos,
  pyvrp-instructions (task_affinity should filter pyvrp-instructions out for a
  Cosmos task — confirm this, don't assume it).
- scripts/check_grading_ready.py --db results.db (added in commit 5bdb92c)
  exits 1 if every axis has 0 gradeable cells, 0 if at least one axis has >=1.
  Use it as your readiness oracle throughout — don't hand-roll the query.

STEP 0 — CLEAN THE TREE:
- `git status --porcelain`. If any TRACKED files are modified/staged, commit
  them as ONE isolated "session: checkpoint wip" commit first. Leave untracked
  scratch alone. Do NOT push. Confirm a clean tracked tree before proceeding.

STEP 1 — A2 real run (methodology axis):
1. Dry-run to confirm the grid: `.venv\Scripts\python.exe cli.py run --task
   cosmos-A --methodology all --repo-context none --model claude-haiku-4-5
   --runner claude-code --reps 1 --dry-run`. If `custom` errors or is clearly
   not ready (per IMPLEMENTATION_PLAN.md §7, it may not be — that's a known,
   accepted gap, NOT a bug to fix), exclude it from the real run and note why
   in your final report; otherwise include it.
2. Run for real at reps=3 (drop --dry-run, keep reps=3):
   `.venv\Scripts\python.exe cli.py run --task cosmos-A --methodology
   <baseline,custom,ecc,karpathy,superpowers minus any excluded> --repo-context
   none --model claude-haiku-4-5 --runner claude-code --reps 3`
3. Verify lay-down correctness using persisted data (no need to keep
   worktrees): for a couple of the new trial ids, inspect `run_result.diff` in
   results.db (or an equivalent already-built inspection path) and confirm
   each methodology's files show up per its manifest.yaml, baseline injects
   nothing, and repo-context ('none' here) contributes nothing. If the
   persisted diff genuinely can't answer this, run ONE additional reps=1
   `--keep-worktree` pass across the 5 methodologies just for inspection,
   then `git -C repos/cosmos worktree remove --force <path>` +
   `git -C repos/cosmos worktree prune` for each before continuing — don't
   leave stray worktrees.
4. If you find a REAL bug (wrong files, wrong lay-down order, crash) — not an
   expected hidden-gate FAIL — dispatch ONE studio-executor (model=sonnet)
   with a self-contained TDD brief describing exactly what's wrong and where.
   Append: "Work TDD: write the failing test first. Commit with a short honest
   message. Report back ONLY a <=4-line summary (files touched, commit SHA,
   test result). If you cannot get tests green, revert your own changes and
   report FAILED with a one-line reason." Cap at ONE fix attempt per distinct
   bug; if still broken after that, mark it a known issue in your final report
   and move on — do not loop.

STEP 2 — COST CHECK (the one place you may need to ask):
- Query cost_record for the trials STEP 1 just created and sum usd_equiv.
- If actual A2 spend is <= $10: proceed straight to STEP 3, no need to ask.
- If actual A2 spend is > $10 (5x+ the reference estimate — something is off):
  STOP before spending more. Use AskUserQuestion once: report the actual A2
  spend and ask permission to continue to A3 at the same rate. Wait for the
  answer before proceeding. (This is the only point in this run where you may
  pause for a human.)

STEP 3 — A3 real run (repo-context axis):
1. Dry-run: `.venv\Scripts\python.exe cli.py run --task cosmos-A --methodology
   baseline --repo-context all --model claude-haiku-4-5 --runner claude-code
   --reps 1 --dry-run`. Confirm `none` and `cosmos` appear and
   `pyvrp-instructions` is filtered out by task_affinity. Also confirm with
   `--full-matrix --dry-run` that the affinity override makes the nonsensical
   pairing appear (proves the filter is real, not a no-op).
2. Cross-check task_affinity the other direction (dry-run only, no cost): run
   a PyVRP task (e.g. pyvrp-A) with `--repo-context all --dry-run` and confirm
   `cosmos` is filtered out there.
3. Run the sensible set for real at reps=3: `.venv\Scripts\python.exe cli.py
   run --task cosmos-A --methodology baseline --repo-context none,cosmos
   --model claude-haiku-4-5 --runner claude-code --reps 3`
4. Verify repo-context files land FIRST (before methodology) and `none` adds
   nothing, same method as STEP 1.3. Same bug-fix protocol as STEP 1.4 (one
   studio-executor sonnet attempt per distinct real bug, cap at one retry).

STEP 4 — READINESS CHECK:
- Run `.venv\Scripts\python.exe scripts\check_grading_ready.py --db
  results.db`. Record its exit code and the per-axis table it prints.
- If it exits 0 (>=1 gradeable cell somewhere): good, the axis-coverage
  problem is solved.
- If it STILL exits 1: this is expected-possible (reps=3 real trials can
  still all fail an uncalibrated task's hidden gate) and is now a
  *calibration* problem, not an axis-coverage problem — do NOT attempt to fix
  the gate or the task yourself; that needs `scripts/calibrate_tasks.py` and
  human judgment per `19-M-calibration-sweep.md`. Just record the honest
  finding for your report and for STEP 5 to describe accurately.

STEP 5 — RECONCILE DOCS:
Dispatch ONE studio-executor (model=opus — this needs judgment about what's
now true) with this brief:

  GOAL: A2 and A3 (methodology axis, repo-context axis) have now run for real
  against cosmos-A with claude-haiku-4-5/claude-code at reps=3. Update the
  docs to reflect the actual outcome — do not assume J1 is unblocked; check.
  FILES: docs/superpowers/recalibration-checklist.md ; RECALIBRATION_PLAYBOOK.md ;
  README.md (only the "Next up" bullet list)
  DO:
   1. Run `.venv\Scripts\python.exe scripts\check_grading_ready.py --db
      results.db` yourself to get the current, authoritative state (don't
      trust a stale summary).
   2. In docs/superpowers/recalibration-checklist.md: tick A2 and A3 with a
      one-line evidence note each (trial counts, models, real methodology/
      repo-context values now present). If check_grading_ready exits 0, change
      the J1 line from its current BLOCKED wording back to reflecting it's
      ready (e.g. "- [ ] J1 grading UI shakedown — **READY: N gradeable
      cell(s), run `scripts/check_grading_ready.py` to confirm** — NEXT —
      CHECKPOINT"). If it still exits 1, update the J1 line to name the NEW
      blocker precisely: hidden-gate calibration, not missing axis coverage —
      point at `scripts/calibrate_tasks.py` / `19-M-calibration-sweep.md`.
   3. Update RECALIBRATION_PLAYBOOK.md's Phase J prerequisite note (added in
      commit bf50bb2) to match: either mark the A2/A3-real-run prerequisite
      satisfied (cite recalibration_prompts/23) with the calibration
      prerequisite still standing if relevant, or state precisely what remains.
   4. Update README.md's "Next up" J1 bullet to match reality (ready vs.
      blocked-on-calibration), same evidence style as commit bf50bb2 used.
  COMMIT: docs: reconcile checklist/playbook/README to A2+A3 real-run outcome
  Report back ONLY a <=4-line summary (files touched, commit SHA, check_grading_ready
  result). Do NOT paste diffs.

STEP 6 — FINAL VERIFICATION AND REPORT:
- Run `.venv\Scripts\python.exe -m pytest -q` ONCE.
- Print a final report:
  - A2: trials run, any excluded methodology + why, any bug found/fixed
    (commit SHA) or FAILED-and-skipped, actual $ spent.
  - A3: same shape.
  - check_grading_ready.py final exit code + per-axis table.
  - Full suite pass/deselect count.
  - Docs commit SHA from STEP 5.
  - Total $ spent across this whole run.
- Do NOT launch the grading UI, do NOT start grading, do NOT run
  scripts/calibrate_tasks.py. Those are separate human-judgment steps
  (grading = "you are the gold standard" per RECALIBRATION_PLAYBOOK.md;
  calibration adjustments need human OK before touching a frozen golden task).
  Stop after the report.
```
