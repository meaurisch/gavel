# setup-bench

Created: 2026-06-20

A from-scratch, local-first framework to compare agentic coding **setups**
(instruction / skill packs) across **harnesses**, **models**, and **tasks** —
scored on *would-I-merge* quality and on cost. Runs on a personal machine against
public proxy repos, with a minimal manual confirmation tier on the work machine.

## What it is

Four independent, swappable axes — Harness × Model × Setup × Task — sitting on a
single **runner abstraction**. Each trial runs in a fresh `git worktree`; held-out
tests live outside the worktree and are applied only at grade time, so test
leakage is impossible by construction. Quality is a binary held-out-test gate
followed by **blind pairwise forced-choice** ("A or B, which would I merge?").
Cost is captured in native units (Claude Code self-reports USD; Copilot via a
standalone token→USD calculator) and reconciled to a USD-equivalent.

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

## Next up
- [ ] Build the matrix driver (`P1.6`)
- [ ] Build the pairwise grading UI (`P1.7`)
- [ ] Run the Phase-1 model sweep × setup bake-off, then grade
- [ ] Set the open knobs in `IMPLEMENTATION_PLAN.md` §7 before any measurement run
