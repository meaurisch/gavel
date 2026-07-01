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
| **Task** | The coding problem to solve | `pyvrp-A`…`pyvrp-C`, `cosmos-A`, `cosmos-B` |
| **Methodology** | General-purpose instruction / skill pack (the framework under test) | `baseline`, `superpowers`, `karpathy`, `ecc` |
| **Repo-Context** | Repo-specific instructions (held fixed or varied per experiment) | `none`, `pyvrp-instructions` |
| **Model** | The LLM model | `claude-sonnet-4-6`, `claude-opus-4-8` |
| **Runner** | The execution harness | `claude-code`, `copilot-cli` (stub), `manual` |

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

**WSL required for PyVRP tasks.** PyVRP's C++ doesn't compile under MSVC, so the
`pyvrp-*` tasks build under WSL (Ubuntu). `cli.py run` handles this automatically:
when a task is an editable `pip install -e .` and we're on Windows, the gate
dispatches its build/test commands into WSL (`wsl -d <distro> -- bash -lc 'source
<venv> && cd "$(wslpath -a …)" && …'`). Cosmos/.NET tasks stay on the Windows
shell. Override the distro/venv with `SB_WSL_DISTRO` (default `Ubuntu`) and
`SB_WSL_VENV` (default `~/pyvrp-venv/bin/activate`).

The standalone task validator is not WSL-aware, so run it *inside* WSL:

```bash
wsl -d Ubuntu -- bash -c 'source ~/pyvrp-venv/bin/activate && \
  cd /mnt/c/Users/norri/studio/setup-bench && \
  python scripts/validate_tasks.py --verbose --skip-toolchain-check'
```

Claude Code CLI version used: 2.1.185

### Task fields & visible-test composition

A task lives in `tasks/<id>/task.yaml`. Beyond the required fields (`id`,
`repo_url`, `base_commit`, `instruction`, `run_cmd`, `held_out_tests_path`,
`reference_diff_path`, `build_cmd`), two fields control the **visible** tier (tier
2 of the gate — the tests the agent is allowed to see):

- `visible_test_cmd` — the command run for the visible tier.
- `visible_tests_path` — a directory of EXTRA visible test files this task injects
  into the worktree (committed before the repo-context/methodology commits, so
  they're visible to the model but never appear in its diff).

A **repo** can also declare a default visible suite once, instead of every task
repeating it. `repos.yaml` at the project root maps a repo id to its defaults:

```yaml
cosmos:
  visible_test_cmd: 'dotnet test tests/CleanArchitectureCosmosDB.UnitTests/CleanArchitectureCosmosDB.UnitTests.csproj'
```

Presence of the key IS the opt-in. `repos.yaml` lives at the project root on
purpose — never inside `repos/<repo>`, where it would leak into every worktree
and become visible to the model. The effective `visible_test_cmd` resolves as:

| `visible_test_cmd` in task.yaml | Effective visible tier |
|---|---|
| an explicit string | that string (task overrides the repo) |
| `null` / unset | the repo's `repos.yaml` cmd if it declares one, else none |
| `none` (sentinel) | none — force-skip even if the repo declares a suite |

`scripts/validate_tasks.py --validate-transitions` now also asserts the *resolved*
visible suite is green on the clean base commit (skipped when it resolves to none),
so a declared suite can't be one that doesn't build/pass.

> **Guardrail:** task-supplied visible tests must NOT duplicate the held-out
> oracle. Visible tests that ARE the hidden tests let the model trivially satisfy
> the gate. The gate already asserts held-out files aren't pre-present in the
> worktree; keep that assertion.

#### Held-out-path collision (agent writes a test where the oracle lives)

An agent can naturally create a test at a path the held-out oracle also occupies
(on the cosmos-A shakedown, opus wrote `tests/.../Mappers/AuditMapperTest.cs`).
The gate now handles this **provenance-aware**, SWE-bench style: the oracle always
wins, but only a *genuine* leak stays fatal.

**How provenance is determined.** The runner records the post-prepare, pre-agent
HEAD as a worktree-local ref (`refs/worktree/setup-bench-baseline`, see
`grading.gate.BASELINE_REF`). At gate time, for a colliding held-out path:

- **Present in the baseline tree** (came in via a setup commit — repo-context /
  methodology / visible-tests) → *setup* provenance → **genuine leak, fatal.** The
  model would have seen the oracle. The assertion still fires.
- **Present only in the agent's diff** (not in the baseline — the agent never saw
  the oracle, which lives outside the worktree until now) → *agent* provenance →
  **not a leak.** The gate overwrites the path with the true oracle and runs that;
  the agent's own content already survives in the captured diff for blind grading.
- **No baseline ref** (nop / oracle / manual don't record one) → provenance is
  unprovable → **fatal**, exactly as before. We only relax where provenance is
  proven.

This keeps the protected invariant intact — *the model never sees the oracle, and
the gate runs the true oracle* — while no longer failing an agent that merely
guessed the same test path. The overwritten agent file is restored after the run
(leave-no-trace), mirroring the oracle-file cleanup.

## Current state

The full pipeline is built and tested (204 tests green (1 env-gated test deselected)) — engine, 5-axis matrix,
three-tier gate, axis-general blind grading, Bradley-Terry ranking, API-rate cost,
and task-quality tooling. The task set now spans two repos/languages (PyVRP C++/Python
and a .NET Cosmos DB service). The execution spine is shaken out end-to-end on Windows:
the `claude-code` runner (prompt via stdin), the three-tier gate — which now auto-dispatches
PyVRP build/test into WSL — and the leakage scanner all run green on the golden tasks
(oracle PASS / nop FAIL for every task).

A **Model-axis shakedown** (cosmos-A, baseline, haiku/sonnet/opus, 1 rep) exercised
the runner against real models and surfaced a batch of runner/gate bugs, all now
fixed. The two headline ones: `collect()` diffed against live HEAD, so a committing
agent's entire diff vanished (the sonnet trial recorded a 0-length diff after $1.84
of real work) — it now diffs against the setup baseline captured before the agent
runs; and the runner's default turn cap (25) contradicted the settled §7 cap (60),
truncating cross-layer tasks — now reconciled. The follow-ups then landed:
`RunResult.error` is now persisted to `results.db` (it was dropped at insert), an
empty agent diff is surfaced as an explicit error (a real no-op signal now that the
diff-loss bug is fixed), `collect()` requires an explicit baseline (no silent HEAD
default for the next committing runner to trip over), and the held-out-path collision
(agent writes a test where the oracle lives) is now handled **provenance-aware**:
overwrite-and-run for the agent's own file, still fatal for a genuine setup leak. All
three models priced correctly at their own API rate. The next step is the first real
measurement sweep.

**Engine & tasks (P0–P1)**
- Core engine: models, DB, worktree isolation, runners, gate, leakage scanner.
- Runners: `claude-code` (headless) and `manual` (human-in-IDE), plus
  `oracle`/`nop` for pipeline self-tests. `copilot-cli` stays a stub — the
  Phase-1.5 spike (P2.1/P2.2) is **deferred** (Copilot out of scope for now; see
  Next up).
- Tasks: three cross-layer PyVRP features (`pyvrp-A` ReplaceGroup operator,
  `pyvrp-B` unary-operator framework, `pyvrp-C` PiecewiseLinearFunction) plus two
  .NET 8 Clean-Architecture/Cosmos DB tasks — `cosmos-A` (refactor: replace
  AutoMapper with hand-written mappers for the ToDoItem + Audit aggregates) and
  `cosmos-B` (feature: add a complete/reopen lifecycle across domain → MediatR
  handlers → controller, plus an `isCompleted` search filter) — each with a
  reference diff and held-out tests; oracle/nop validation passing.
- Validator is repo/language-agnostic: it runs each task's own `build_cmd`/
  `run_cmd` (PyVRP `pip install -e .`, Cosmos `dotnet build`/`dotnet test`),
  resolves the repo via an explicit `repo:` field, and lints C# as well as
  Python held-out tests.
- Methodologies: `baseline`, `karpathy`, `superpowers`, `ecc`, `custom`
  (external packs vendored at pinned commits, frozen offline). `custom` (the
  user's own conductor/executor/validator/reviewer agents) is authored for both
  the `copilot` harness (`.github/agents/`) and the `claude-code` harness
  (`CLAUDE.md` + `.claude/agents/`, adapted from the Copilot originals).
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
  static rubric lint (`validate_tasks.py --lint`), and the golden-task rubric in
  `docs/task-design-guide.md`.

> **DB note:** the `trial` schema gained a `repo_context_id` column with no
> migration. Delete any pre-P3.3 `results.db` before running.

## Next up

- [x] **Model-axis shakedown** — ran cosmos-A across haiku/sonnet/opus; fixed the
      diff-loss (baseline-ref) and max-turns (25→60) runner bugs it surfaced.
- [ ] **First calibration run** — a small real sweep to land each task's pass
      rate in the 30–70% discrimination window.
- [x] **Persist `RunResult.error`** — added the `run_result.error` column (+ backfill);
      parse/exit/gate-crash errors now survive to `results.db`, and an all-no-op
      (empty-diff) trial is flagged as an explicit error.
- [x] **Provenance-aware leakage assertion** — held-out-path collisions now
      overwrite-and-run for agent-provenance files while staying fatal for genuine
      setup leaks (see the gate guardrail note).
- [ ] **J1 — grading UI shakedown (NEXT)** — launch the pairwise UI and grade
      real trials end-to-end (blind A/B, axis picker, anonymization). This is the
      immediate next step now that Phase R is parked.
- [~] **Phase R (Copilot) — DEFERRED (2026-07-01)** — no Copilot account/plan on
      hand; the R0 spike isn't worth a paid trial now. Runner axis stays coverable
      via the `manual` runner. Revive prompts 11–13 if a Copilot plan appears.
- [x] **Second repo/language landed** — `cosmos-A`/`cosmos-B` add .NET (one
      refactor, one feature), authored and validated.
- [ ] **Task-suite expansion** — add more cross-repo tasks to broaden coverage.
- [ ] **Pareto frontier visualization** — plot quality vs. cost so the
      tradeoffs the analyzer flags are visible at a glance (`report` command is
      still a stub).
- [x] Open knobs in `IMPLEMENTATION_PLAN.md` §7 settled (reps=3, max-turns=60,
      `custom` in scope, comparison axis per-experiment; work models **deferred** —
      Copilot out of scope for now, see the deferred Phase R above).
- [ ] **Sync & recalibration** in progress — golden cross-repo test set, then
      axis-by-axis shakedown. See `docs/superpowers/recalibration-checklist.md`.
