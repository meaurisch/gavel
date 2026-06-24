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

> **Comparison is axis-general.** Blind pairwise can target *any* axis
> (methodology / model / repo-context / runner), holding the others fixed as a
> "cell" and redacting every axis id from the diffs. The P3.x series below builds
> toward that; methodology is just the default comparison axis.

## Order

Phase 0–2 build the engine and surfaces. The **P3.x series** is the
research-driven evolution (research report in `docs/research-eval-frameworks.md`).
Status reflects the current code state.

| # | File | Phase / purpose | Dependency | Status |
|---|---|---|---|---|
| P0.1 | `P0.1-scaffold-data-model.md` | 0 — scaffold + data model + DB | — | ✅ done |
| P0.2 | `P0.2-worktree-runners.md` | 0 — worktree + runner base + oracle/nop/manual | P0.1 | ✅ done |
| P0.3 | `P0.3-gate-leakage.md` | 0 — held-out gate + leakage checker | P0.2 | ✅ done |
| P1.1 | `P1.1-clone-cosmos.md` | 1 — clone + augment Cosmos proxy repo | P0.x | ✅ done |
| P1.2 | `P1.2-clone-pyvrp.md` | 1 — clone PyVRP + scope feature task | P0.x | ✅ done |
| P1.3 | `P1.3-task-authoring.md` | 1 — task authoring (revert + held-out + leakage) | P1.1–P1.2 | ✅ done |
| P1.4 | `P1.4-claude-code-runner.md` | 1 — Claude Code headless runner + cost capture | P0.2 | ✅ done |
| P1.5 | `P1.5-setup-packs.md` | 1 — methodology packs install/freeze + OFF ablation | P0.x | ✅ done |
| P1.6 | `P1.6-matrix-driver.md` | 1 — matrix driver + run protocol | P1.4–P1.5 | ✅ done |
| P1.7 | `P1.7-pairwise-ui.md` | 1 — blind pairwise grading UI (superseded — see P3.3 Part 3 + P3.5) | P1.6 | ✅ done |
| P2.1 | `P2.1-copilot-runner.md` | 2 — Copilot CLI runner | **spike-gated** | ⬜ pending |
| P2.2 | `P2.2-copilot-usage-calculator.md` | 2 — standalone Copilot usage calculator | **spike-gated** | ⬜ pending |
| P3.0 | `P3.0-research-eval-frameworks.md` | 3 — research: eval frameworks + test-set design | — | ✅ done |
| P3.1 | `P3.1-derive-implementation-prompts.md` | 3 — derive the P3.x prompts from the research | P3.0 | ✅ done |
| P3.2 | `P3.2-cost-calculation.md` | 3 — API-rate cost (pricing table; self-report secondary) | None | ✅ done |
| P3.3 | `P3.3-axis-refactor.md` | 3 — split setup → Methodology + Repo-Context (5-axis) | None (∥ P3.2) | ✅ Parts 1–2 done |
| P3.3·3 | `P3.3-part3-grading-axis.md` | 3 — **axis-general** blind grading + UI axis picker | P3.3 Parts 1–2 | ✅ done |
| P3.4 | `P3.4-gate-system.md` | 3 — three-tier gate scorecard (compile → visible → hidden) | P3.3 | ✅ done |
| P3.5 | `P3.5-multi-rep-pairwise.md` | 3 — multi-rep sampling + Bradley-Terry + analyzer (axis-general) | P3.4 | ✅ done |
| P3.6 | `P3.6-test-set-quality.md` | 3 — task-set quality (discrimination band, difficulty, stronger tests) | P3.4 | ✅ done |
| P3.7 | `P3.7-readme-rewrite.md` | 3 — README rewrite (last) | all P3.x | ✅ done |

**`P3-aggregation-report.md` (the original single "P3"):** folded into the P3.x
series. Its pairwise win-matrix / preponderance ranking is **superseded by P3.5**
(Bradley-Terry replaces it). Its cost-frontier + stakes decision rollup + HTML
report are **not yet built** by any P3.x prompt — they remain as post-P3.7 work
(P3.7's "Next up" lists the Pareto-frontier visualization). Kept as a pointer,
not deleted.

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
