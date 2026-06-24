# setup-bench

Created: 2026-06-20

A from-scratch, local-first framework to compare agentic coding **methodologies**
(instruction / skill packs) across **repo-contexts**, **models**, **runners**
(harnesses), and **tasks** — scored on *would-I-merge* quality and on cost. Runs
on a personal machine against public proxy repos, with a minimal manual
confirmation tier on the work machine.

## What it is

Five independent, swappable axes — Task × Methodology × Repo-Context × Model ×
Runner (harness) — sitting on a single **runner abstraction**. The *methodology*
(instruction / skill pack) and the *repo-context* (repo-specific instructions)
are laid into the worktree sequentially — repo-context first, methodology
**on top**, never merged. Repo-contexts carry a `task_affinity` tag so
nonsensical task/context pairs are skipped by default (override with
`--full-matrix`).

**Comparison is axis-general.** Any axis can be the comparison target: you pick
which axis to compare (methodology, model, repo-context, or runner), the chosen
axis varies while every *other* axis is held fixed as a "cell", and the diffs
shown to the grader redact **every** axis id — so blind A/B works for whichever
axis you're comparing. Methodology is the default; the others are selectable.

Each trial runs in a fresh `git worktree`; held-out tests live outside the
worktree and are applied only at grade time, so test leakage is impossible by
construction. Quality is a **three-tier gate scorecard** (compile → visible tests
→ hidden tests), then **blind pairwise forced-choice** ("A or B, which would I
merge?") over the hidden-gate passers, with multi-rep sampling and a
**Bradley-Terry** ranking (Elo-style scores + bootstrap confidence intervals).
Cost is computed from token counts × published API rates (data-driven pricing
table in `cost/pricing.toml`, updatable via `setup-bench pricing fetch`).
Self-reported cost is kept as a secondary reference value.

Concrete runners: `claude-code` (headless), `copilot-cli` (headless), and
`manual` (human-in-IDE), plus `oracle`/`nop` for pipeline self-tests.

The full design — architecture, phasing, definition-of-ready, run protocol, and
the decision rule — lives in `IMPLEMENTATION_PLAN.md`. The build is driven by the
ordered Claude Code prompts in `prompts/`.

## How to run it

```
.\tasks.ps1 Run
```

The project is still at the scaffolding stage — the runnable CLI
(`setup-bench run|grade|report`) gets built by working through `prompts/` in
order. `tasks.ps1` already points `Run`, `Setup`, and `Test` at the intended
commands so they light up as soon as the package exists.

Validate that all three PyVRP tasks have correct oracle/nop behavior (requires
WSL with Ubuntu — PyVRP's C++ code doesn't compile with MSVC):

```
wsl -d Ubuntu -- bash -c 'source ~/pyvrp-venv/bin/activate && cd /mnt/c/Users/norri/studio/setup-bench && python scripts/validate_tasks.py --verbose --skip-toolchain-check'
```

Before the first build session, pin the CLI (a `-p` bug shipped in one 2.1.x
release) and record the version below:

```
npm install -g @anthropic-ai/claude-code@latest
```

Claude Code CLI version used: 2.1.185

## Current state

**Phase 0 complete** — core engine scaffolded and tested (models, db, worktree,
runners, gate, leakage scanner). All P0 tests pass.

**P1.1 complete** — `repos/cosmos` cloned from
`ShawnShiSS/clean-architecture-azure-cosmos-db` at `f8a0105`. AutoMapper
replaced with hand-written multi-representation mappers for ToDoItem + Audit
aggregates (WebAPI ↔ Domain ↔ Cosmos document model). Per-pair xUnit tests
added. MappingProfile.cs deleted, AutoMapper packages removed.
Retargeted to .NET 8.0 (LTS). Build green, 14/14 tests pass.

**P1.2 complete** — `repos/pyvrp` cloned from `PyVRP/PyVRP`, pinned at branch
`pinned-post-features` (`dfbf81e` on main). Three cross-layer feature tasks
extracted, each with a reference diff and held-out tests:

| Task | Feature | Scope |
|------|---------|-------|
| `pyvrp-A` | ReplaceGroup local-search operator | C++ operator + pybind11 bindings + Python module + LocalSearch integration |
| `pyvrp-B` | Unary operator framework (RemoveOptional, RemoveAdjacentDepot) | C++ base class + two concrete operators + bindings + registration |
| `pyvrp-C` | PiecewiseLinearFunction | C++ header + pybind11 bindings + Python exports |

**P1.3 complete** — held-out tests strengthened with edge-case assertions,
oracle/nop validation passing for all three tasks. Validation requires WSL
(Ubuntu) because PyVRP's C++ doesn't compile with MSVC.

**P1.5 complete** — setup packs layer built. Six setups with manifest-driven file
placement per harness:

| Setup | Description | Claude Code files | Copilot files |
|-------|-------------|-------------------|---------------|
| `baseline` | No instructions (ablation control) | — | — |
| `repo-instructions` | User's own repo instructions (slot, empty until authored) | CLAUDE.md | copilot-instructions.md |
| `karpathy` | Karpathy coding discipline guidelines | CLAUDE.md (1 file) | copilot-instructions.md |
| `superpowers` | obra/superpowers methodology framework | CLAUDE.md + 51 skills | AGENTS.md |
| `ecc` | ECC v2.0.0 agent operating system | CLAUDE.md + 441 skills + 67 agents + 114 rules | copilot-instructions.md |
| `custom` | User's conductor/executor/validator/reviewer workflow | — (skeleton) | 7 agent files |

External packs vendored at pinned commits and frozen offline under `setups/<id>/vendor/`
(methodologies were then called *setups*; renamed to `methodologies/` in P3.3 Part 1).
Loader resolves any `(setup_id, harness)` pair into a `SetupSpec` — runners unchanged.

**P1.6 complete** — matrix driver and run protocol fully wired. `cli.py run`
expands Setup × Model × Task × Rep into trials via `core/matrix.py`, executes
through `core/executor.py` with resumability (skips trials already in DB),
configurable inter-trial delay for rate limiting, and a Rich live progress table.
`--dry-run` prints the trial grid without executing.

**P1.7 complete** — blind pairwise grading UI. FastAPI + single static page
(`ui/`). For a chosen task + model, generates all C(N,2) pairwise comparisons
among setups that passed the gate. Diffs shown side by side, anonymized (setup
instruction file hunks stripped, setup IDs replaced). Keyboard-first: A/B/T to
choose, arrows to navigate, R for optional 4-dim rubric notes (correctness,
minimality, readability, over-engineering). Objective proxies (lines changed,
files touched, new deps) shown alongside each diff. After grading, identities
revealed with win/loss/tie summary. Judgments persisted in `judgment` table.
Launch with `.\tasks.ps1 Grade` or `python cli.py grade`.

**P3.2 complete** — cost calculation refactored. USD cost now computed from
token counts × published API rates (`cost/pricing.toml`) instead of relying on
Claude's self-reported `total_cost_usd`. Pricing table covers Anthropic and
OpenAI models, fetchable from LiteLLM's open dataset via `setup-bench pricing
fetch`. Manual overrides via `setup-bench pricing add`. Self-reported cost
kept as `native_amount` for reference.

**P3.3 Part 2 complete** — added the **Repo-Context** axis (backend). The matrix
is now 5-axis: `expand()` takes `repo_contexts` and a `full_matrix` flag, and
trial ids are `{task}_{methodology}_{repo_context}_{model}_{runner}_{rep}`.
Repo-contexts live in `repo_contexts/` (migrated from `setups/repo-instructions`),
each with a manifest carrying `task_affinity`; `none` is the noop ablation
control. Runners lay repo-context files first, methodology files second (two
commits). New `core/repo_context_loader.py` mirrors the methodology loader;
`core/db.py` gains a `repo_context_spec` table and a `repo_context_id` column on
`trial`. CLI gains `--repo-context`, `--full-matrix`, a "Context" grid column,
and a warning when `baseline` is omitted.

**P3.3 Part 3 complete** — grading is now **axis-general**. `grading/pairwise.py`
takes a comparison `axis` (`methodology` / `model` / `repo_context` / `runner`):
`generate_pairs(trials, run_results, axis)` groups by that axis, and
`anonymize_diff(diff, axis_ids_by_axis)` blinds **every** axis id with its own
token. `core/db.py` gains `list_grading_cells(conn, axis)` (enumerates fixed-axis
"cells" with ≥2 distinct values) and a keyword-only multi-axis
`list_passing_trials`. The UI (`ui/server.py` + `ui/static/index.html`) replaces
the old `(task, model)` flow with `/api/axes` → `/api/cells` → `/api/pairs`: an
axis picker drives cascading cell pickers, diffs are blinded across all axes, and
the reveal tallies/header are keyed by the chosen axis. Covered by
`tests/test_pairwise.py` + `tests/test_server.py` (88 tests green).

> **DB break:** the `trial` table schema changed (new `repo_context_id` column)
> with no migration — delete any pre-existing `results.db` (or migrate it by
> hand) before running.

**P3.5 complete** — multi-rep sampling + Bradley-Terry ranking + analyzer flags
(axis-general). `generate_pairs(trials, run_results, axis, num_pairs, seed)` now
draws balanced cross-value pairs from **all reps** (pool ≈ C(M,2)·R², default
C(M,2)·3 pairs) instead of only rep 0. `grading/bradley_terry.py` fits a BT model
(MM algorithm, ties as half-wins) and returns Elo-style scores with bootstrap
95% CIs (numpy). `grading/analyzer.py` flags non-discriminating tasks, flaky
tasks, and cost/quality tradeoffs. `core/db.py` gains `list_cell_trials` (all
trials in a cell, passing and failing). `/api/reveal` now returns `bt_scores`,
`analyzer_flags`, and `pass_rates` (BT skipped below 3 judgments); a new
`/api/stats` returns per-value pass rate + mean cost + mean wall-clock. The
reveal page (`ui/static/index.html`) renders a ranked BT table (overlapping CIs
shown as indistinguishable) plus colored analyzer callouts. Covered by
`tests/test_bradley_terry.py`, `tests/test_analyzer.py`, and additions to
`tests/test_pairwise.py` / `tests/test_db.py` / `tests/test_server.py`
(107 tests green).

**P3.6 complete** — task-set quality tooling and guidance. Tasks now carry a
`difficulty` field (`easy` / `medium` / `hard`) in `task.yaml`, stored in the DB
and validated by the model layer. `scripts/calibrate_tasks.py` computes per-task
pass rates from the results DB, bands them into the 30–70% discrimination window,
and flags ceiling/floor effects. `scripts/validate_tasks.py --validate-transitions`
checks FAIL_TO_PASS / PASS_TO_PASS / build-gate correctness per task against the
clean base commit and gold patch (requires WSL). `docs/task-design-guide.md`
distills the evaluation-framework research into actionable rules for writing
discriminative tasks (119 tests green).

## Next up

The remaining `prompts/`, in order — grading is axis-general with BT ranking
(P3.3, P3.5 done):

- [ ] **P3.4** — three-tier gate scorecard (compile → visible → hidden).
- [ ] **P3.7** — README rewrite (last, describing the actual final system).
- [ ] Then: run the Phase-1 model sweep × methodology bake-off, grade, and set
      the open knobs in `IMPLEMENTATION_PLAN.md` §7 before any measurement run.
