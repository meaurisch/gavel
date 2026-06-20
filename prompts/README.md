# prompts/

The ordered Claude Code build prompts for setup-bench, one per file. Paste them
into Claude Code **in order** — each assumes the prior steps are done.

Each file contains the **verbatim** prompt from the implementation plan. Where a
prompt collides with the studio setup (already-created files, conflicting
conventions), there is a short `> **Studio adjustment**` note at the top. The
note is the only addition; the prompt body below it is untouched so it stays
copy-pasteable.

## Before P0.1 — pin the CLI

A `-p` bug shipped in one 2.1.x Claude Code release. Pin first, then record the
version in the repo `README.md`:

```
npm install -g @anthropic-ai/claude-code@latest
```

## Order

| # | File | Phase |
|---|---|---|
| P0.1 | `P0.1-scaffold-data-model.md` | 0 — scaffold + data model + DB |
| P0.2 | `P0.2-worktree-runners.md` | 0 — worktree + runner base + oracle/nop/manual |
| P0.3 | `P0.3-gate-leakage.md` | 0 — held-out gate + leakage checker |
| P1.1 | `P1.1-clone-cosmos.md` | 1 — clone + augment Cosmos proxy repo |
| P1.2 | `P1.2-clone-pyvrp.md` | 1 — clone PyVRP + scope feature task |
| P1.3 | `P1.3-task-authoring.md` | 1 — task authoring (revert + held-out + leakage) |
| P1.4 | `P1.4-claude-code-runner.md` | 1 — Claude Code headless runner + cost capture |
| P1.5 | `P1.5-setup-packs.md` | 1 — setup packs install/freeze + OFF ablation |
| P1.6 | `P1.6-matrix-driver.md` | 1 — matrix driver + run protocol |
| P1.7 | `P1.7-pairwise-ui.md` | 1 — blind pairwise grading UI |
| P2.1 | `P2.1-copilot-runner.md` | 2 — Copilot CLI runner (pending spike) |
| P2.2 | `P2.2-copilot-usage-calculator.md` | 2 — standalone Copilot usage calculator |
| P3 | `P3-aggregation-report.md` | 3 — aggregation, frontier, decision rollup |

## Studio reconciliation, at a glance

- **Project already exists.** Studio's `new` process created the folder, git repo,
  `README.md`, `.gitignore`, `CLAUDE.md`, `.studio.json`, `tasks.ps1`, and the
  `.claude/` pointer. P0.1 should populate the package *inside* this folder, not
  re-create the project or overwrite these files.
- **Dependency management.** The plan says "uv-managed". Studio convention is
  `python -m venv .venv` + pinned `requirements.txt`. Pick one and note it; the
  prompts default to the studio convention unless you decide otherwise.
- **CLI library.** The plan uses Typer; studio's `cli-tool.md` says argparse.
  Either is fine — Typer is a thin layer — just keep `--help`, stderr/stdout
  separation, and exit codes 0/1/2 per studio.
- **Run interface.** `tasks.ps1 Run` is the canonical entry point. Wire it to the
  `setup-bench` CLI as that CLI comes to life (already stubbed in `tasks.ps1`).
- **Agent mode is ON.** This project enabled conductor/executor. Multi-file
  prompts (most of these) should route through `studio-conductor` for a plan
  first, then `studio-executor`.
