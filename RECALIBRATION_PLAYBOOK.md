# Recalibration Playbook

A fool-proof, do-this-then-that guide for finishing and validating setup-bench.
Follow the steps top to bottom. Each step says **which Claude service** to use
and **which exact prompt file** to paste. Verbatim prompts live in
[`recalibration_prompts/`](recalibration_prompts/).

- **Design spec:** `docs/superpowers/specs/2026-06-24-sync-recalibration-design.md`
- **Progress tracker:** `docs/superpowers/recalibration-checklist.md` (tick as you go)
- **Enhancement backlog:** `docs/superpowers/recalibration-backlog.md` (auto-created at first checkpoint)

## How to read this

- **Service** = where you paste the prompt: **Claude Code** (the terminal agent,
  the spine), **Chat + Research**, **Design**, **Cowork**, or **YOU** (a manual
  human action).
- Each prompt file has a `<<<PASTE …>>>` marker where YOU must fill something in
  before sending; the file says what.
- **CHECKPOINT** = stop, hand your notepad to Claude Code via
  `recalibration_prompts/00-checkpoint-notepad-triage.md`, fix BUG+UGLY items,
  park ENHANCEMENTs. Do not skip these — they are the point of the whole effort.
- Keep a notepad open the entire time. Write down everything broken/ugly/slow.

## Conventions used in the prompts

- Run the CLI with the venv python directly: `.venv\Scripts\python.exe cli.py …`
- Tests: `.venv\Scripts\python.exe -m pytest -q`  (expect `119 passed, 1 deselected`, growing as we add tests)
- PyVRP tasks build only under **WSL**; Cosmos tasks build under **Windows/.NET**.
- Models: `claude-haiku-4-5` (cheap), `claude-sonnet-4-6` (mid), `claude-opus-4-8` (top).

---

## ✅ Already done (Phase S + Phase 0)

Sync and knobs are complete and merged to `main`: docs reconciled, tests green
(Windows + WSL), §7 knobs settled (reps=3, max-turns=60, `custom` in scope,
comparison axis per-experiment, work-models pending the spike). Nothing to do
here — start at Phase G.

---

## Phase G — Build the golden cross-repo test set

| Step | Service | Paste this prompt | Then |
|---|---|---|---|
| **G1a** | Chat + Research | `recalibration_prompts/01-G1-rubric-research.md` | Save the rubric it returns |
| **G1b** | Claude Code | `recalibration_prompts/02-G1-rubric-integrate.md` | Tick **G1** |
| **G2** | Claude Code | `recalibration_prompts/03-G2-pyvrp-golden.md` | You pick the under-specified task; tick **G2** |
| **G3a** | Claude Code | `recalibration_prompts/04-G3a-cosmos-automapper.md` | Tick **G3a** |
| **G3b-i** | Chat + Research | `recalibration_prompts/05-G3b-cosmos-research.md` | You pick the feature |
| **G3b-ii** | Claude Code | `recalibration_prompts/06-G3b-cosmos-author.md` | Finalize task-set + stakes in §7; tick **G3b** |
| **CHECKPOINT** | Claude Code (+Cowork if big) | `recalibration_prompts/00-checkpoint-notepad-triage.md` | Fix BUG+UGLY before Phase A |

---

## Phase A — Axis shakedown → measurement

Each row: Claude Code runs the sweep, YOU watch and note friction, then a
CHECKPOINT.

| Step | Service | Paste this prompt | Then |
|---|---|---|---|
| **A1** Execution spine (Task/gate/cost) | Claude Code | `recalibration_prompts/07-A1-spine-shakedown.md` | CHECKPOINT → tick **A1** |
| **A2** Methodology axis | Claude Code | `recalibration_prompts/08-A2-methodology-axis.md` | CHECKPOINT → tick **A2** |
| **A3** Repo-Context axis | Claude Code | `recalibration_prompts/09-A3-repo-context-axis.md` | CHECKPOINT → tick **A3** |
| **A4** Model axis | Claude Code | `recalibration_prompts/10-A4-model-axis.md` | CHECKPOINT → tick **A4** |

(The CHECKPOINT each time is `recalibration_prompts/00-checkpoint-notepad-triage.md`.)

---

## Phase R — Copilot (spike-gated) — DEFERRED (2026-07-01)

> **Skipped for now.** No Copilot account/subscription on hand, and the R0 spike
> isn't worth a paid trial at this stage. Phase R is parked — **jump straight from
> Phase A to Phase J.** The Runner axis stays coverable via the `manual` runner
> if/when this is revisited. Revive the phase (the three prompts below) if a
> Copilot plan becomes available. See IMPLEMENTATION_PLAN.md §7 (work-models row).

| Step | Service | Paste this prompt | Then |
|---|---|---|---|
| **R0** Spike (decision gate) | YOU (+ Claude Code prep) | `recalibration_prompts/11-R0-copilot-spike.md` | Decide PASS/FAIL; tick **R0** |
| **R1** Build P2.1 + P2.2 — **only if R0 PASSED** | Claude Code | `recalibration_prompts/12-R1-build-copilot.md` | Tick **R1** |
| **R2** Runner axis | Claude Code | `recalibration_prompts/13-R2-runner-axis.md` | CHECKPOINT → tick **R2** |

> **If R0 FAILED (or Phase R stays deferred):** skip R1. Cover the Runner axis with
> the `manual` runner in place of `copilot-cli` (prompt 13 explains how) if/when
> you want it, then continue to Phase J.

---

## Phase J — The judgment end (where you act)

| Step | Service | Paste this prompt | Then |
|---|---|---|---|
| **J1** Grading UI shakedown | Claude Code launch + **YOU grade** | `recalibration_prompts/14-J1-grading-shakedown.md` | — |
| **J1-design** UI visual polish | Design | `recalibration_prompts/15-J1-design-ui-critique.md` | CHECKPOINT → tick **J1** |
| **J2** Bradley-Terry + analyzer | Claude Code | `recalibration_prompts/16-J2-bt-analyzer.md` | Tick **J2** |
| **J3** Report command + Pareto | Claude Code | `recalibration_prompts/17-J3-report-build.md` | — |
| **J3-design** Frontier visual | Design | `recalibration_prompts/18-J3-design-pareto.md` | FINAL CHECKPOINT → tick **J3** |

---

## Phase M — First calibration sweep (close-out)

| Step | Service | Paste this prompt | Then |
|---|---|---|---|
| **M** Calibrate + first ranking | Claude Code | `recalibration_prompts/19-M-calibration-sweep.md` | Final CHECKPOINT → tick **M** → done |

---

## Quick decision reminders (yours to make)

- **G2/G3:** which single task is the deliberately under-specified one; stakes
  tier per task → record in `IMPLEMENTATION_PLAN.md` §7.
- **R0:** ~~is Copilot CLI representative + permitted; which work models → §7~~
  — **deferred 2026-07-01** (Phase R parked; no Copilot plan).
- **J1:** the blind grades themselves — you are the gold standard.

When everything is ticked in `docs/superpowers/recalibration-checklist.md`, the
system is shaken out and you have your first real ranking. Run `bye` to
commit/push and refresh the README "Current state".
