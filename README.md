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

Before the first build session, pin the CLI (a `-p` bug shipped in one 2.1.x
release) and record the version below:

```
npm install -g @anthropic-ai/claude-code@latest
```

Claude Code CLI version used: _TODO — record after pinning_

## Current state

Studio project scaffolded: README, `tasks.ps1`, `CLAUDE.md`
(base + python-script + cli-tool + agent-mode), `.studio.json`, `.gitignore`,
`.claude/` pointer, and local git initialized. The `prompts/` folder holds the
13 verbatim build prompts (P0.1 → P3), each lightly annotated where it touches
something studio already set up. No framework code is implemented yet — that
starts with `prompts/P0.1-scaffold-data-model.md`.

## Next up

- [ ] Pin the Claude Code CLI and record its version above
- [ ] Run `prompts/P0.1` → `P0.3` to scaffold the engine + prove `oracle`/`nop`
- [ ] Clone & augment the proxy repos (`prompts/P1.1`, `P1.2`)
- [ ] Author the real tasks, install/freeze the 5 setup packs (`P1.3`, `P1.5`)
- [ ] Build the Claude Code runner, matrix driver, and pairwise UI (`P1.4`, `P1.6`, `P1.7`)
- [ ] Run the Phase-1 model sweep × setup bake-off, then grade
- [ ] Set the open knobs in `IMPLEMENTATION_PLAN.md` §7 before any measurement run
