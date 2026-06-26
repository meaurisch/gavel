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
- [ ] A1 execution spine (Task / gate / cost) — **CHECKPOINT**
- [ ] A2 methodology axis — **CHECKPOINT**
- [ ] A3 repo-context axis — **CHECKPOINT**
- [ ] A4 model axis — **CHECKPOINT**

## Phase R — Copilot (spike-gated)
- [ ] R0 spike run + decision (HUMAN; sets work models)
- [ ] R1 P2.1 + P2.2 built (only if spike passed)
- [ ] R2 runner axis sweep — **CHECKPOINT**

## Phase J — Judgment end
- [ ] J1 grading UI shakedown (HUMAN grades) — **CHECKPOINT**
- [ ] J2 Bradley-Terry + analyzer validated
- [ ] J3 report command + Pareto frontier built (Design) — **FINAL CHECKPOINT**

## Phase M — First calibration sweep
- [ ] tasks landed in 30-70% band; first real ranking produced
