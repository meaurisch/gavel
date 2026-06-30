# Sync & Recalibration — Design

Date: 2026-06-24
Status: approved (brainstorming) — pending implementation plan

## Purpose

Two goals, in order:

1. **Synchronize** the repository so README, prompt status, docs, and tracked
   state exactly match the code, with everything committed and tests verified
   green.
2. **Recalibrate forward** — finish the two remaining prompts (P2.1 Copilot
   runner, P2.2 Copilot usage calculator, both spike-gated), build a
   golden-standard cross-repo test set, then test the whole system
   component-by-component and axis-by-axis with a notepad-driven fix loop,
   flowing each axis from a cheap functional check into a small real sweep.

This is a decision-support tool with limited statistical power; the goal of the
testing phase is a *trustworthy, un-ugly, working* system — not a published
benchmark.

## Approved decisions (from brainstorming)

- **Sequencing: Approach 1** — linear, dependency-ordered, Copilot just-in-time
  (spike before any P2.1/P2.2 build).
- **Copilot spike has NOT happened.** P2.1/P2.2 are conditional on it passing.
  If it fails, the `manual` runner covers the Copilot surface and the two
  prompts are skipped.
- **Golden test set is cross-repo:** perfect PyVRP A/B/C *and* author **two**
  Cosmos tasks — (1) the AutoMapper→hand-written-mappers slice (capped at 1–2
  aggregates) and (2) a researched candidate.
- **Testing intent: shakedown that flows into measurement** — per axis, a cheap
  functional check, then a small real sweep.
- **Open knobs settled up front** (Phase 0), not lazily.
- **Service routing:** Claude Code is the spine (all implementation + as much
  automated testing as possible). The human acts only where a real person
  naturally would (the spike, grading, the manual runner). Other Claude Pro
  services are called out only where clearly better, each with a verbatim
  prompt: **Chat+Research** = external lookups / rubric grounding; **Design** =
  UI/visual work; **Cowork** = long-form doc/triage artifacts.
- **Spec format:** this design doc + a copy-pasteable file per implementation
  step in `prompts/` + a lightweight running checklist tracked across sessions.

## Sync findings (already discovered)

- Working tree clean; all prior work committed.
- `prompts/README.md` status table is **stale**: P3.3·3, P3.4, P3.5, P3.6 are
  done but shown as next/pending; P3.7 status needs confirming against the
  current README.
- Main README "Current state" **overstates** the runner set — it implies
  `copilot-cli` is built, but `runners/copilot_cli.py` and
  `cost/copilot_usage.py` are 1-line stubs.
- Test-count drift — README says "119"; there are ~120 test functions. Re-run
  and reconcile to the true number.

---

## Phase S — Synchronization *(Claude Code, no API spend)*

1. Update `prompts/README.md` status table (P3.3·3/P3.4/P3.5/P3.6 → ✅; confirm
   P3.7; mark P2.1/P2.2 ⬜ "spike-gated").
2. Correct README "Current state" runner claim — `claude-code` built;
   `copilot-cli` is a stub pending the spike.
3. Run full `pytest` (Windows) + WSL `validate_tasks.py`; record real results;
   fix anything red.
4. Replace the "119 tests" figure with the true count.
5. Reconcile `.superpowers/sdd/progress.md` if it advertises stale state.
6. Commit as one clean sync checkpoint.

## Phase 0 — Set the open knobs (`IMPLEMENTATION_PLAN.md` §7)

Human decision sheet, recorded into the plan doc: final task set + stakes tiers
· default comparison axis per experiment · `--max-turns` cap per harness · rep
count (2 vs 3) · is `custom` methodology frozen/ready · work models (deferred to
the spike).

## Phase G — Golden cross-repo test set

**G1 — Golden-standard rubric.** Produced with **Claude Chat + Research**
(grounded in eval-design literature + `docs/research-eval-frameworks.md`), then
integrated by Claude Code into `docs/task-design-guide.md` and encoded into
`validate_tasks.py`/`calibrate_tasks.py` where checkable. Facets: description
quality (unambiguous, names entry points, no solution leakage); instruction
language (reads like a real senior-written ticket; one task deliberately
under-specified); tests (visible/hidden split, hidden strengthened beyond the
original PR, FAIL_TO_PASS/PASS_TO_PASS/build transitions validated,
leakage-clean); representativeness (believable cross-layer change);
difficulty + calibration (label + 30–70% target band).

**G2 — PyVRP A/B/C to golden.** Audit each against the rubric; fix gaps (likely
hidden-test strength, instruction language, difficulty labels); re-run
validate + leakage + transition checks in WSL.

**G3 — Two Cosmos tasks to golden.** (a) AutoMapper slice (1–2 aggregates);
(b) a researched candidate (**Chat+Research** scopes it from the repo's real PR
history and confirms C#/.NET test idioms). Confirm `.NET 5` toolchain; wire
`dotnet build`/`dotnet test` into `build_cmd`/`run_cmd`; author `task.yaml`,
`reference.diff`, `held_out_tests/`, and a Cosmos `repo_contexts/` entry with
`task_affinity`; validate transitions + leakage on C#.

**Output:** frozen validated cross-repo golden set + rubric doc. First
**notepad-fix checkpoint** here.

## Phase A — Axis shakedown → measurement

Per-axis pattern: (1) functional check (oracle/nop, `--dry-run`, Haiku, 1 rep);
(2) small real sweep; (3) notepad-fix checkpoint.

- **A1 · Execution spine (Task + gate + cost).** Each golden task through the
  full pipeline: `oracle` passes the gate, `nop` fails; then `claude-code`
  Haiku 1 rep. Validates worktree isolation, file lay-down order, three-tier
  scorecard, cost from `pricing.toml` (+ self-report secondary), leakage
  scanner.
- **A2 · Methodology axis.** baseline/karpathy/superpowers/ecc/custom on one
  task, cheap model; per-harness manifest lay-down; baseline lays nothing.
- **A3 · Repo-Context axis.** `none` vs `pyvrp-instructions`; `task_affinity`
  filtering + `--full-matrix` override.
- **A4 · Model axis.** Haiku/Sonnet/Opus on one cell; cost deltas visible.

Each → notepad-fix checkpoint.

## Phase R — Copilot (spike-gated)

- **R0 · Spike (Phase 1.5).** Claude Code preps a throwaway worktree; **the
  human** runs `copilot -p` on one golden task and judges representative +
  permitted. Decision gate.
- **R1 · If pass — build P2.1 + P2.2** (Claude Code, TDD): `copilot_cli.py`
  against the Runner protocol; standalone `copilot_usage.py` calculator with a
  hand-worked math test and zero setup-bench dependency, plus the thin adapter.
- **R2 · Runner axis** sweep: claude-code vs copilot-cli on one cell, cost
  joined via the usage calculator on `trial_id`. → checkpoint.
- **If fail —** `manual` runner covers the surface; skip P2.1/P2.2; Runner-axis
  test uses `manual`.

## Phase J — Judgment end *(human acts)*

- **J1 · Grading UI shakedown.** Launch pairwise UI on real hidden-gate
  passers; axis picker + cascading cells; confirm blinding (no axis id leaks).
  Human grades. **Claude Design** for UI critique/polish. → checkpoint.
- **J2 · Bradley-Terry + analyzer.** Real judgments → BT ranking + bootstrap
  CIs; analyzer flags (non-discriminating / flaky / cost-quality).
- **J3 · Report + Pareto frontier.** Build the `report` command (currently a
  stub) and the quality-vs-cost Pareto viz (**Claude Design**). → final
  checkpoint + consolidation.

## Phase M — First calibration sweep (close-out)

Small real sweep that lands each task in the 30–70% band and produces the first
genuine ranking — the measurement the shakedowns flowed toward.

## Notepad-fix loop (every checkpoint)

The human hands over the notepad (paste or file). Triage into **bug / ugly /
enhancement**; fix must-fixes before advancing; park enhancements in a backlog
to avoid rabbit-holing. For a large dump, **Cowork** structures the triage
first.

## Service routing summary

| Where | Service | Why |
|---|---|---|
| All impl + automated testing | **Claude Code** | the spine |
| R0 spike, J1 grading, manual runner | **Human** | real-person action points |
| Rubric grounding, Cosmos feature scoping, C# idioms | **Chat + Research** | external authority |
| Grading UI polish, Pareto viz | **Design** | visual work |
| Large notepad triage | **Cowork** | long-form artifact |

Each non-Code handoff carries a verbatim prompt in its `prompts/` step file.

## Deliverables

- Synced repo (README, prompts/README, docs, test count) + green tests.
- Settled §7 knobs recorded in `IMPLEMENTATION_PLAN.md`.
- Golden rubric in `docs/task-design-guide.md`; golden PyVRP A/B/C + two Cosmos
  tasks, all validated.
- P2.1/P2.2 implemented (if spike passes) or explicitly skipped.
- A `report` command + Pareto frontier viz.
- First calibration ranking.
- One `prompts/` file per implementation step + a running checklist.

## Out of scope

- Full statistical-power measurement campaigns (this sizes a decision, not a
  paper).
- Work-machine confirmation tier beyond what the manual runner already covers.
- Task-suite expansion beyond the cross-repo golden set this round.
