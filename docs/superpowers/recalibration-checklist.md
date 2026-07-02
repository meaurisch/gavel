# Recalibration Checklist

Living tracker for the sync & recalibration effort. Check items as checkpoints clear.

- Source spec: `docs/superpowers/specs/2026-06-24-sync-recalibration-design.md`
- Plans: `docs/superpowers/plans/` (one per phase, written just-in-time)
- SDD ledger (git-ignored scratch): `.superpowers/sdd/progress.md`

## Phase S — Sync
- [x] prompts/README status table reconciled (commit 8c38cd4)
- [x] README runner overstatement corrected (commit 30f9249)
- [x] tests verified green — Windows 119 passed/1 deselected; WSL pyvrp-A/B/C oracle=PASS nop=FAIL (expected — nop does nothing; closes P3.6 deferred-manual item)
- [x] §7 knobs settled (commit cd2cf72) — reps=3, max-turns=60, custom in scope, axis per-experiment, work-models TBD pending spike
- [x] cross-session checklist created

## Phase 0 — Knobs
- [x] settled and recorded in IMPLEMENTATION_PLAN.md §7

## Phase G — Golden cross-repo test set
- [x] G1 rubric (Chat+Research) integrated into task-design-guide + validators
- [x] G2 PyVRP A/B/C raised to golden + validated
- [x] G3a Cosmos AutoMapper task authored + validated
- [x] G3b Cosmos researched-candidate task authored + validated
- [x] stakes tier tagged per task; deliberately under-specified task marked
- [x] **CHECKPOINT: notepad triage + fix**

## Phase A — Axis shakedown -> measurement
- [x] A1 execution spine (Task / gate / cost) — verified via results.db (cosmos-A oracle+nop+claude-code; pyvrp-A/B/C oracle+nop trials) — **CHECKPOINT**
- [x] A2 methodology axis — done 2026-07-03: baseline/karpathy/ecc/superpowers at
      3 real reps each + custom at 1 real rep (its 2-attempt budget; 1 attempt
      errored-but-billed) on cosmos-A/none/claude-haiku-4-5. 0/17 hidden-gate
      passes on cosmos-A -> calibration finding, not plumbing — **CHECKPOINT**
- [x] A3 repo-context axis — done 2026-07-03: baseline x {none, cosmos} x 3 reps;
      task_affinity verified both directions (+ --full-matrix override) — **CHECKPOINT**
- [x] A4 model axis — verified via results.db (cosmos-A/baseline/none/claude-code across haiku+sonnet+opus) + follow-up fixes 5c9fea7, df1bfd5, 7a5121d, 686cf00 — **CHECKPOINT**

## Phase R — Copilot (spike-gated) — DEFERRED (2026-07-01)
Skipped for now: no Copilot account/subscription on hand, and the R0 spike isn't
worth a paid trial at this stage. The Runner axis stays coverable via the `manual`
runner if/when revisited. Revive this phase (prompts 11–13) if a Copilot plan
becomes available. Work-models row in IMPLEMENTATION_PLAN.md §7 marked deferred.
- [~] R0 spike — SKIPPED (decided 2026-07-01: Copilot out of scope for now)
- [~] R1 P2.1 + P2.2 — not built (deferred with the phase)
- [~] R2 runner axis sweep — deferred (`manual`-runner fallback available)

## Phase J — Judgment end
- [x] J1 grading UI shakedown — done 2026-07-02, unblocked differently than planned:
      gradeable data came from (a) the synthetic demo DB (`python cli.py demo`) and
      (b) four REAL manual-runner cosmos-B trials (two hand-authored solution
      variants, all hidden-gate PASS, `check_grading_ready` reported the project's
      first gradeable cell). Driven end-to-end with Playwright (screenshots in
      `docs/screenshots/`), blinding verified on the served diffs. Found+fixed the
      founder bug: diff panes had NEVER rendered (wrong diff2html global). Sessions
      now persist across server restarts; judgments are latest-wins per pair.
- [x] J2 Bradley-Terry + analyzer validated — exercised live via /api/reveal and
      `cli.py report` on demo + real data; covered by tests/test_bradley_terry.py,
      test_analyzer.py, test_aggregate.py.
- [x] J3 report command + Pareto frontier built — `cli.py report`: BT ranking with
      bootstrap CIs, gate tiers, cost rollup, analyzer flags, stakes picks, and a
      self-contained HTML artifact with the inline-SVG frontier chart. — **FINAL
      CHECKPOINT** done via an 8-angle adversarial review (8 findings, all fixed).

## Phase M — First calibration sweep
- [~] calibration data measured 2026-07-03 (scripts/calibrate_tasks.py): cosmos-B
      33% (2/6) — in band, discriminative; cosmos-A 0% (0/17) and moreiter-A 0%
      (0/3) — floor effect for claude-haiku-4-5. First REAL gradeable cell
      produced (cosmos-B/none/haiku/claude-code: baseline + karpathy passers) and
      blind-graded (1 pair; session c38ed5475724451ab3bb8caedf5d2e2b — Claude's
      judgment, not the human gold standard; purge that session's rows to
      re-grade yourself). A Bradley-Terry ranking needs >=3 comparisons — more
      passers/reps or a human grading pass are the remaining step. Task
      adjustments (easing cosmos-A / moreiter-A for cheap models, or scoping them
      to stronger models) are proposals only — frozen tasks change with human OK.
