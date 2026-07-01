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
- [ ] A2 methodology axis — **CHECKPOINT**
- [ ] A3 repo-context axis — **CHECKPOINT**
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
- [ ] J1 grading UI shakedown (HUMAN grades) — **BLOCKED: run A2 + A3 for real first, then `scripts/check_grading_ready.py --db results.db` must report >=1 gradeable cell** (0 as of 2026-07-01; see `recalibration_prompts/22`) — **CHECKPOINT**
- [ ] J2 Bradley-Terry + analyzer validated
- [ ] J3 report command + Pareto frontier built (Design) — **FINAL CHECKPOINT**

## Phase M — First calibration sweep
- [ ] tasks landed in 30-70% band; first real ranking produced
