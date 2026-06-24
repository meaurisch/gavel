# Sync & Knobs Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Bring the repository's docs and tracked state into exact agreement with the code, verify tests green, set the open §7 knobs, and stand up a cross-session checklist — so the recalibration work starts from a clean, honest baseline.

**Architecture:** Pure documentation/state reconciliation plus one human decision-capture step. No production code changes. This is the first of several just-in-time per-phase plans derived from `docs/superpowers/specs/2026-06-24-sync-recalibration-design.md`. Later phases (G golden set, A axis shakedown, R Copilot, J judgment, M calibration) get their own plans when their inputs are known — writing them now would be speculative, since they depend on the rubric research, the spike outcome, and the chosen Cosmos features.

**Tech Stack:** Markdown docs, `pytest` (Windows `.venv`), WSL `validate_tasks.py` for PyVRP.

## Global Constraints

- Keep the README's four required sections present: **What it is** | **How to run it** | **Current state** | **Next up**.
- Commit messages are short and human; end with the `Co-Authored-By: Claude Opus 4.8 <noreply@anthropic.com>` trailer.
- Report verification outcomes faithfully — paste real command output, never assert green without running.
- Do not touch production code in this plan; docs and `.superpowers/` tracking only.
- Test baseline to preserve: `119 passed, 1 deselected` (the deselected test is env-gated, not a failure).

---

### Task 1: Reconcile the `prompts/README.md` status table

**Files:**
- Modify: `prompts/README.md` (the status table, rows P3.3·3 / P3.4 / P3.5 / P3.6 / P3.7 / P2.1 / P2.2)

**Interfaces:**
- Consumes: nothing.
- Produces: an accurate prompt-status table that the rest of the recalibration references.

- [ ] **Step 1: Confirm true status of each P3.x prompt against git + code**

Run:
```bash
git log --oneline | grep -iE "P3\.(3|4|5|6|7)"
```
Expected: commits showing P3.3 parts 1–2, P3.6 series. Cross-check the main `README.md` "Current state" section, which already documents P3.2–P3.6 as done.

- [ ] **Step 2: Determine whether P3.7 (README rewrite) is effectively done**

Read `prompts/P3.7-readme-rewrite.md` and compare its requirements to the current `README.md`. The current README is the comprehensive final-system description (covers all 5 axes, three-tier gate, Bradley-Terry, API-rate cost, task-quality tooling). Decide: mark P3.7 ✅ if the README already satisfies it, otherwise leave ⬜ with a one-line note on what's missing. Record the decision in the commit message.

- [ ] **Step 3: Edit the table**

In `prompts/README.md`, change the Status column:
- `P3.3·3` row: `▶️ **next**` → `✅ done`
- `P3.4` row: `⬜ pending` → `✅ done`
- `P3.5` row: `⬜ pending` → `✅ done`
- `P3.6` row: `⬜ pending` → `✅ done`
- `P3.7` row: per Step 2 decision
- `P2.1` and `P2.2` rows: keep `⬜ pending`, change the Dependency cell to note **"spike-gated"** (Phase-1.5 Copilot spike must pass first)

- [ ] **Step 4: Verify no other stale status text**

Run:
```bash
grep -nE "next|pending|▶️" prompts/README.md
```
Expected: only P2.1/P2.2 remain `⬜ pending`; no `▶️ next` markers remain.

- [ ] **Step 5: Commit**

```bash
git add prompts/README.md
git commit -m "sync: update prompt status table (P3.3-3..P3.6 done, P2.1/2.2 spike-gated)"
```

---

### Task 2: Correct the README runner overstatement

**Files:**
- Modify: `README.md` (the "Current state" runner bullet, ~line 132–135; and the test-count phrasing, ~line 125)

**Interfaces:**
- Consumes: nothing.
- Produces: a "Current state" section that does not claim `copilot-cli` is built.

- [ ] **Step 1: Confirm the copilot files are stubs**

Run:
```bash
wc -l runners/copilot_cli.py cost/copilot_usage.py
```
Expected: each is 1 line (a docstring stub) — confirming `copilot-cli` is NOT implemented.

- [ ] **Step 2: Reword the runner bullet**

In `README.md` "Current state", replace the runner bullet:

Old:
```
- Runners: `claude-code` and `copilot-cli` (headless), `manual` (human-in-IDE),
  plus `oracle`/`nop` for pipeline self-tests.
```
New:
```
- Runners: `claude-code` (headless) and `manual` (human-in-IDE), plus
  `oracle`/`nop` for pipeline self-tests. `copilot-cli` is stubbed pending the
  Phase-1.5 spike (P2.1/P2.2).
```

- [ ] **Step 3: Clarify the test-count phrasing**

In `README.md` (~line 125), change `119 tests green` to `119 tests green (1 env-gated test deselected)` so the count matches `pytest` output exactly.

- [ ] **Step 4: Verify the four required sections still present**

Run:
```bash
grep -nE "^## (What it is|How to run it|Current state|Next up)" README.md
```
Expected: all four headings present.

- [ ] **Step 5: Commit**

```bash
git add README.md
git commit -m "sync: README current-state reflects copilot-cli as stub"
```

---

### Task 3: Verify tests green in both environments

**Files:**
- None modified. This task records evidence.

**Interfaces:**
- Consumes: nothing.
- Produces: confirmed-green baseline before any forward work; resolution of the P3.6 deferred-manual WSL validation noted in `.superpowers/sdd/progress.md:13`.

- [ ] **Step 1: Run the Windows suite**

Run:
```bash
.venv/Scripts/python.exe -m pytest -q
```
Expected: `119 passed, 1 deselected`. If anything fails, STOP and fix before continuing (a red baseline invalidates the recalibration).

- [ ] **Step 2: Run the WSL PyVRP task validation**

Run:
```bash
wsl -d Ubuntu -- bash -c 'source ~/pyvrp-venv/bin/activate && \
  cd /mnt/c/Users/norri/studio/setup-bench && \
  python scripts/validate_tasks.py --verbose --skip-toolchain-check'
```
Expected: all three PyVRP tasks validate (this also clears the P3.6 "DEFERRED MANUAL: 3 worktree validators" note). Record the real output. If WSL/venv is missing, note it as a blocker for Phase G2 rather than silently skipping.

- [ ] **Step 3: Reconcile the progress ledger**

In `.superpowers/sdd/progress.md`, append a dated line under the P3.6 ledger recording the outcome of Step 2 (e.g. "2026-06-24: WSL task validation run, all 3 PyVRP tasks pass — deferred-manual item closed" or the actual result). Do not rewrite history; append.

- [ ] **Step 4: Commit**

```bash
git add .superpowers/sdd/progress.md
git commit -m "sync: record WSL task-validation result, close P3.6 deferred item"
```

---

### Task 4: Set the open §7 knobs (human decision capture)

**Files:**
- Modify: `IMPLEMENTATION_PLAN.md` (§7 "Open knobs to set before you execute")

**Interfaces:**
- Consumes: nothing.
- Produces: settled values that Phase G and the axis sweeps depend on.

- [ ] **Step 1: Present the decision sheet to the human**

Ask the user to settle each §7 knob (these are decisions, not code). Present current defaults from `IMPLEMENTATION_PLAN.md` §0/§7:
- **Final task set + stakes tier each** — PyVRP A/B/C + 2 Cosmos (which is the deliberately under-specified one? which is high-stakes vs routine?).
- **Default comparison axis per experiment** — methodology is the documented default; confirm or override per planned experiment.
- **`--max-turns` cap per harness** — pick a value (affects cost ceiling).
- **Rep count** — 2 or 3.
- **`custom` methodology** — is it frozen/ready to vendor, or excluded this round?
- **Work models** — explicitly DEFER to the Copilot spike (record as "TBD pending spike").

- [ ] **Step 2: Record the answers into §7**

Rewrite `IMPLEMENTATION_PLAN.md` §7 from an open-questions list into a settled-values table (keep a one-line "set 2026-06-24" note). Leave work-models as "TBD — pending Phase-1.5 spike".

- [ ] **Step 3: Verify no open knob left unanswered**

Run:
```bash
grep -nA15 "Open knobs" IMPLEMENTATION_PLAN.md
```
Expected: every bullet has a settled value (or an explicit deferral with reason).

- [ ] **Step 4: Commit**

```bash
git add IMPLEMENTATION_PLAN.md
git commit -m "sync: settle open knobs (task set, axis, max-turns, reps)"
```

---

### Task 5: Stand up the cross-session recalibration checklist

**Files:**
- Create: `.superpowers/sdd/recalibration-checklist.md`

**Interfaces:**
- Consumes: the phase structure from the design spec.
- Produces: a single living checklist that tracks checkpoint progress across sessions (the artifact requested in the spec's "spec + prompts/ + checklist" format).

- [ ] **Step 1: Create the checklist mirroring the spec phases**

Write `.superpowers/sdd/recalibration-checklist.md` with unchecked items grouped by phase, each notepad-fix checkpoint called out explicitly:

```markdown
# Recalibration Checklist

Source spec: docs/superpowers/specs/2026-06-24-sync-recalibration-design.md
Plans: docs/superpowers/plans/ (one per phase, written just-in-time)

## Phase S — Sync
- [ ] prompts/README status table reconciled
- [ ] README runner overstatement corrected
- [ ] tests verified green (Windows + WSL)
- [ ] §7 knobs settled
- [ ] checklist created

## Phase G — Golden cross-repo test set
- [ ] G1 rubric (Chat+Research) integrated into task-design-guide + validators
- [ ] G2 PyVRP A/B/C raised to golden + validated
- [ ] G3a Cosmos AutoMapper task authored + validated
- [ ] G3b Cosmos researched-candidate task authored + validated
- [ ] CHECKPOINT: notepad triage + fix

## Phase A — Axis shakedown -> measurement
- [ ] A1 execution spine (Task/gate/cost) — CHECKPOINT
- [ ] A2 methodology axis — CHECKPOINT
- [ ] A3 repo-context axis — CHECKPOINT
- [ ] A4 model axis — CHECKPOINT

## Phase R — Copilot (spike-gated)
- [ ] R0 spike run + decision (HUMAN)
- [ ] R1 P2.1 + P2.2 built (if spike passed)
- [ ] R2 runner axis sweep — CHECKPOINT

## Phase J — Judgment end
- [ ] J1 grading UI shakedown (HUMAN grades) — CHECKPOINT
- [ ] J2 Bradley-Terry + analyzer validated
- [ ] J3 report command + Pareto frontier built — FINAL CHECKPOINT

## Phase M — First calibration sweep
- [ ] tasks landed in 30-70% band; first real ranking produced
```

- [ ] **Step 2: Commit**

```bash
git add .superpowers/sdd/recalibration-checklist.md
git commit -m "sync: add cross-session recalibration checklist"
```

---

## Self-Review

**Spec coverage (this plan covers Phase S + Phase 0 only, by design):**
- Sync findings — prompts/README table (Task 1), README runner overstatement (Task 2), test-count phrasing (Task 2), re-verify green (Task 3), progress.md reconciliation (Task 3). ✓
- Phase 0 knobs — Task 4. ✓
- Checklist artifact — Task 5. ✓
- Phases G/A/R/J/M — explicitly deferred to just-in-time per-phase plans (stated in Architecture). ✓

**Placeholder scan:** No "TBD/implement later" except the one *intentional* deferral (work-models pending spike), which is a real decision, not a plan gap. ✓

**Type consistency:** No code types in this plan (docs/state only). File paths verified against the repo layout. ✓
