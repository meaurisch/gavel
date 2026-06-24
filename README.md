# setup-bench

Created: 2026-06-20

A from-scratch, local-first framework to compare agentic coding **setups**
(instruction / skill packs) across **harnesses**, **models**, and **tasks** —
scored on *would-I-merge* quality and on cost. Runs on a personal machine against
public proxy repos, with a minimal manual confirmation tier on the work machine.

## What it is

Five independent, swappable axes — Task × Methodology × Repo-Context × Model ×
Runner (harness) — sitting on a single **runner abstraction**. The *methodology*
(instruction / skill pack) is the thing under test; the *repo-context* is a fixed
controlled environment (repo-specific instructions) laid into the worktree
**under** the methodology — applied sequentially, never merged. Repo-contexts
carry a `task_affinity` tag so nonsensical task/context pairs are skipped by
default (override with `--full-matrix`). Each trial runs in a fresh `git worktree`; held-out
tests live outside the worktree and are applied only at grade time, so test
leakage is impossible by construction. Quality is a binary held-out-test gate
followed by **blind pairwise forced-choice** ("A or B, which would I merge?").
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

External packs vendored at pinned commits and frozen offline under `setups/<id>/vendor/`.
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
and a warning when `baseline` is omitted. Grading/UI wiring of the new axis is
Part 3.

> **DB break:** the `trial` table schema changed (new `repo_context_id` column)
> with no migration — delete any pre-existing `results.db` (or migrate it by
> hand) before running.

## Next up
- [ ] P3.3 Part 3 — wire repo-context through pairwise grouping + grading UI
- [ ] Run the Phase-1 model sweep × methodology bake-off, then grade
- [ ] Set the open knobs in `IMPLEMENTATION_PLAN.md` §7 before any measurement run
