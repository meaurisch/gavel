# setup-bench

Created: 2026-06-20

A local-first **decision-support tool** for comparing agentic coding setups. It
tells you which combination of methodology, repo-context, model, and runner
produces the best results for *your* tasks — and at what cost. It helps you make
an informed choice; it does not try to prove one setup is statistically superior.

> This is a decision-support tool with a handful of tasks and limited statistical
> power. Treat its rankings as evidence for a decision, not as theorems.

## What it is

Five independent, swappable axes. You vary one to compare it; you hold the rest
fixed.

| Axis | What it is | Example values |
|------|-----------|----------------|
| **Task** | The coding problem to solve | `pyvrp-A`, `pyvrp-B`, `pyvrp-C` |
| **Methodology** | General-purpose instruction / skill pack (the framework under test) | `baseline`, `superpowers`, `karpathy`, `ecc` |
| **Repo-Context** | Repo-specific instructions (held fixed or varied per experiment) | `none`, `pyvrp-instructions` |
| **Model** | The LLM model | `claude-sonnet-4-6`, `claude-opus-4-8` |
| **Runner** | The execution harness | `claude-code`, `copilot-cli`, `manual` |

**Methodology vs. repo-context.** Methodology is the *general* framework being
tested (a discipline pack, a skills library). Repo-context is *repo-specific*
knowledge (how this codebase is laid out, its conventions). They are separate
axes so you can test each in isolation or in combination. In the worktree they
are laid down sequentially — repo-context first, methodology on top, never merged.
Repo-contexts carry a `task_affinity` tag so nonsensical task/context pairings are
skipped by default (override with `--full-matrix`).

**Comparison is axis-general.** Every axis is a comparison target. At grade time
you pick *which* axis to compare; that axis varies while every other axis is
pinned to one "cell", and **all** axis ids are redacted from the diffs — so blind
A/B works no matter which axis you're comparing.

### Three-tier gate scorecard

Each trial gets a scorecard. The hidden gate is the definitive quality metric;
only its passers enter grading.

| Tier | Gate | Question |
|------|------|----------|
| 1 | **Compile** | Does the code build? |
| 2 | **Visible tests** | Do the tests the agent could see pass? |
| 3 | **Hidden tests** | Do the held-out tests pass? *(definitive)* |

### Execution flow

```
   matrix expand            fresh git worktree           gate (outside worktree)
 Task × Methodology  ──►   repo-context + methodology  ──►  compile → visible → hidden
   × Context × Model        agent runs the task              │
   × Runner × Rep                                            ▼
                                                      hidden-gate passers
                                                            │
                                                            ▼
                                              blind pairwise grading  ──►  Bradley-Terry
                                              (pick axis, pin a cell)       scores + CIs
```

**Isolated execution.** Every trial runs in a fresh `git worktree`. Held-out
tests live *outside* the worktree and are copied in only at gate time, then
removed — test leakage is impossible by construction (a leakage scanner enforces it).

**Blind pairwise grading + Bradley-Terry.** Pick the comparison axis and pin the
other axes to one cell — the UI offers an axis picker plus cascading cell pickers.
Anonymized diffs (every axis id redacted) are shown side by side; you pick A, B,
or Tie. Judgments feed a Bradley-Terry model that produces Elo-style scores with
95% bootstrap confidence intervals, ranking the chosen axis's values. Multi-rep
sampling draws balanced cross-value pairs from *all* repetitions, not just one.

**API-rate cost.** Cost is computed from token counts × published API rates (a
data-driven table in `cost/pricing.toml`, refreshable via `setup-bench pricing
fetch`), not from self-reported numbers — so it's reproducible and comparable
across models. Wall-clock time is captured as a secondary metric.

**Analyzer flags.** The analyzer automatically surfaces non-discriminating tasks
(everything passes or everything fails), flaky tasks (high variance across reps),
and cost/quality tradeoffs (an expensive methodology with no quality gain).

The full design — architecture, phasing, run protocol, decision rule — lives in
`IMPLEMENTATION_PLAN.md`. Guidance on writing discriminative tasks is in
`docs/task-design-guide.md`.

## How to run it

```powershell
.\tasks.ps1 Run       # execute trials
.\tasks.ps1 Grade     # launch the pairwise grading UI
```

Under the hood these call `cli.py`. The main options:

```bash
python cli.py run --task all --methodology all --repo-context all \
    --model claude-sonnet-4-6 --reps 3 --dry-run
```

- `--task / --methodology / --repo-context` — an id or `all`
- `--model` — comma-separated model ids (required)
- `--runner` — execution harness (default `claude-code`)
- `--reps` — repetitions per cell (default 3)
- `--full-matrix` — ignore `task_affinity` and run every task/context pairing
- `--dry-run` — print the trial grid and exit
- `--delay` — seconds between trials (rate limiting)

Manage the pricing table with `python cli.py pricing list|fetch|add`.

**WSL required for PyVRP tasks.** PyVRP's C++ doesn't compile under MSVC, so
running and validating the `pyvrp-*` tasks needs WSL (Ubuntu):

```bash
wsl -d Ubuntu -- bash -c 'source ~/pyvrp-venv/bin/activate && \
  cd /mnt/c/Users/norri/studio/setup-bench && \
  python scripts/validate_tasks.py --verbose --skip-toolchain-check'
```

Claude Code CLI version used: 2.1.185

## Current state

The full pipeline is built and tested (119 tests green (1 env-gated test deselected)) — engine, 5-axis matrix,
three-tier gate, axis-general blind grading, Bradley-Terry ranking, API-rate cost,
and task-quality tooling. Nothing has been run at scale yet; the next step is the
first real measurement sweep.

**Engine & tasks (P0–P1)**
- Core engine: models, DB, worktree isolation, runners, gate, leakage scanner.
- Runners: `claude-code` (headless) and `manual` (human-in-IDE), plus
  `oracle`/`nop` for pipeline self-tests. `copilot-cli` is stubbed pending the
  Phase-1.5 spike (P2.1/P2.2).
- Tasks: three cross-layer PyVRP features (`pyvrp-A` ReplaceGroup operator,
  `pyvrp-B` unary-operator framework, `pyvrp-C` PiecewiseLinearFunction), each
  with a reference diff and held-out tests; oracle/nop validation passing.
- Methodologies: `baseline`, `karpathy`, `superpowers`, `ecc`, `custom`
  (external packs vendored at pinned commits, frozen offline).
- Matrix driver + run protocol: resumable execution, inter-trial delay, Rich live
  progress table, `--dry-run` grid.

**P3 evolution**
- **P3.2** — API-rate cost from `cost/pricing.toml` (LiteLLM-fetchable), self-
  reported cost kept as a reference value.
- **P3.3** — Repo-Context axis (matrix now 5-axis); grading made axis-general
  with an axis picker + cascading cell pickers, all axis ids redacted.
- **P3.4** — three-tier gate scorecard (compile → visible → hidden).
- **P3.5** — multi-rep sampling, Bradley-Terry ranking with bootstrap CIs, and
  the analyzer flags.
- **P3.6** — task-set quality tooling: per-task `difficulty`, `calibrate_tasks.py`
  pass-rate bands, transition validation (FAIL_TO_PASS / PASS_TO_PASS / build),
  and `docs/task-design-guide.md`.

> **DB note:** the `trial` schema gained a `repo_context_id` column with no
> migration. Delete any pre-P3.3 `results.db` before running.

## Next up

- [ ] **First calibration run** — a small real sweep to land each task's pass
      rate in the 30–70% discrimination window.
- [ ] **First grading session** — exercise the UI end-to-end on real trials.
- [ ] **Task-suite expansion** — add tasks beyond PyVRP to broaden coverage.
- [ ] **Pareto frontier visualization** — plot quality vs. cost so the
      tradeoffs the analyzer flags are visible at a glance (`report` command is
      still a stub).
- [ ] Set the open knobs in `IMPLEMENTATION_PLAN.md` §7 before any measurement run.
