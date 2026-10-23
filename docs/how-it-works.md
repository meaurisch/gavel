# How gavel works — technical reference

The [README](../README.md) explains what gavel is for. This page is the detailed
reference: the axes, the gate, blind grading, the LLM judge, cost, the CLI, and
how tasks are authored. The full design rationale lives in
[`IMPLEMENTATION_PLAN.md`](../IMPLEMENTATION_PLAN.md); guidance on writing
discriminative tasks is in [`task-design-guide.md`](task-design-guide.md).

## The five axes

Five independent, swappable axes. You vary one to compare it; you hold the rest
fixed.

| Axis | What it is | Example values |
|------|-----------|----------------|
| **Task** | The coding problem to solve | `pyvrp-A`…`pyvrp-C`, `cosmos-A`, `cosmos-B`, `moreiter-A`, `studio-A`…`C`, `D4`, `F4`, `D6`, `F6` |
| **Methodology** | General-purpose instruction / skill pack (the framework under test) | `baseline`, `superpowers`, `karpathy`, `ecc`, `custom` |
| **Repo-Context** | Repo-specific instructions (held fixed or varied per experiment) | `none`, `pyvrp-instructions`, `studio-memory-*`, `e6-*` |
| **Model** | The LLM model | `claude-haiku-4-5`, `claude-sonnet-4-6`, `claude-opus-4-8` |
| **Runner** | The execution harness | `claude-code`, `manual`, `oracle`/`nop` (self-tests), `copilot-cli` (stub) |

**Methodology vs. repo-context.** Methodology is the *general* framework being
tested (a discipline pack, a skills library). Repo-context is *repo-specific*
knowledge (how this codebase is laid out, its conventions). They are separate
axes so you can test each in isolation or in combination. In the worktree they
are laid down sequentially — repo-context first, methodology on top, never merged.
Repo-contexts carry a `task_affinity` tag so nonsensical task/context pairings are
skipped by default (override with `--full-matrix`). A repo-context (or
methodology) whose payload is exported/synthesized from another repo, rather
than authored by hand in place, declares a `build: {command, source_ref}`
block in its `manifest.yaml` — `command` regenerates the payload from the
context's own directory, `source_ref` records what it was generated from.
Refresh with `python scripts/build_repo_context.py <id>` (or `--all` /
`--list`); `python cli.py doctor` lists every context that declares one.

**Comparison is axis-general.** Every axis is a comparison target. At grade time
you pick *which* axis to compare; that axis varies while every other axis is
pinned to one "cell", and **all** axis ids are redacted from the diffs — so blind
A/B works no matter which axis you're comparing.

## Execution flow

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

## Three-tier gate scorecard

Each trial gets a scorecard. The hidden gate is the definitive quality metric;
only its passers enter grading.

| Tier | Gate | Question |
|------|------|----------|
| 1 | **Compile** | Does the code build? |
| 2 | **Visible tests** | Do the tests the agent could see pass? |
| 3 | **Hidden tests** | Do the held-out tests pass? *(definitive)* |
| — | **Observational** | Whatever a task's optional `observe_cmd` asks — **recorded, never gating** |

The observational tier exists for measurements that must stay *out* of the
pass/fail decision (e.g. convention adherence): only gate-passers are gradeable,
so gating on adherence would bias the grading pool. It gets its own command
(`observe_cmd` in `task.yaml`), its own stored verdict + log
(`gate_result.observe_passed` / `observe_output`), and its own column in Browse
and in the report — and it is never served during blind comparison, since an
adherence verdict tracks the methodology axis.

## Blind pairwise grading + Bradley-Terry

Pick the comparison axis and pin the other axes to one cell — the UI offers an
axis picker plus cascading cell pickers. Anonymized diffs (every axis id
redacted) are shown side by side; you pick A, B, or Tie. Judgments feed a
Bradley-Terry model that produces Elo-style scores with 95% bootstrap confidence
intervals, ranking the chosen axis's values. Multi-rep sampling draws balanced
cross-value pairs from *all* repetitions, not just one.

What is hidden while judging: every axis id (one redaction implementation,
`grading/pairwise.redact_axis_ids`, covers diffs, gate logs and reconstructed
originals), agent planning folders, and **cost, tokens and time** — those bias
the judgment and appear only after the reveal. Revealing a session asks for
confirmation and closes it permanently.

**Consistency probes.** Human sessions insert ~10% (min 2) deliberate repeat
pairs with sides swapped, indistinguishable on every blind surface. Their
verdicts are excluded from the ranking and yield two instrument numbers —
self-agreement and side-swap flip rate — at reveal and in the report.

## Two grading modes: you, or an LLM judge

Every gradeable cell offers *Grade myself* (the blind manual flow) or *LLM
judge* — an automated judge that receives **exactly the blind payload a human
sees** (anonymized diffs + gate scorecard; never axis ids, cost, tokens, or
timing) and returns rubric-anchored verdicts as strict JSON. Position bias is
controlled by judging each pair twice with the sides swapped; if the passes
disagree the pair scores a tie. Judge providers:

| Provider | Auth | Billing |
|----------|------|---------|
| `claude-cli` (default) | your installed `claude` CLI login — a Claude Pro/Max **subscription needs no API key** | subscription quota (est. shown at API rates) |
| `gh-models` | any GitHub token (`GITHUB_TOKEN` / `gh auth login`) — free tier, or an **org/enterprise** paid tier for higher limits | metered by GitHub |
| `mock` | none | free — deterministic, for demos/tests |

Non-free providers require typing **JUDGE** after a per-session call/token
estimate. Human and LLM verdicts are never mixed inside one session; the
report can rank by *all / human / LLM* judgments and shows a **human ↔ LLM
agreement** card (raw rate + Cohen's κ) wherever both graded the same pairs —
so you can calibrate how much to trust the judge before letting it scale your
grading. Rationales and judge spend appear only after the reveal. Design notes:
[`superpowers/specs/2026-07-06-llm-judge-design.md`](superpowers/specs/2026-07-06-llm-judge-design.md).

## Cost and analyzer flags

**API-rate cost.** Cost is computed from token counts × published API rates (a
data-driven table in `cost/pricing.toml`, refreshable via `python cli.py
pricing fetch`), not from self-reported numbers — so it's reproducible and
comparable across models. Wall-clock time is captured as a secondary metric.
Manage the table with `python cli.py pricing list|fetch|add`.

**Analyzer flags.** The analyzer automatically surfaces non-discriminating tasks
(everything passes or everything fails), flaky tasks (high variance across reps),
and cost/quality tradeoffs (an expensive methodology with no quality gain).

**Decision rule.** The report draws the quality-vs-cost Pareto frontier and
makes two stakes-based picks: the **quality pick** (highest score, for
high-stakes work) and the **budget pick** (the cheapest value whose confidence
interval overlaps the winner's, for routine work).

## Command line

`tasks.ps1` wraps `cli.py`:

```powershell
.\tasks.ps1 Setup     # venv + deps + clone task repos + rebuild task bases + build web UI + doctor
.\tasks.ps1 Ui        # web UI: dashboard, grading, run launcher, browse, report
.\tasks.ps1 Run       # execute trials from the terminal (passes args to `cli.py run`)
.\tasks.ps1 Grade     # web UI landing on the grading picker (alias)
.\tasks.ps1 Report    # rank an axis: BT scores + CIs, cost, Pareto frontier
.\tasks.ps1 Watch     # run tests on every file change
```

Running trials:

```bash
python cli.py run --task all --methodology all --repo-context all \
    --model claude-sonnet-4-6 --reps 3 --dry-run
```

- `--task / --methodology / --repo-context` — an id, comma-separated ids, or `all`
- `--model` — comma-separated model ids (required)
- `--runner` — execution harness (default `claude-code`)
- `--reps` — repetitions per cell (default 3)
- `--full-matrix` — ignore `task_affinity` and run every task/context pairing
- `--dry-run` — print the trial grid and exit
- `--delay` — seconds between trials (rate limiting)
- `--keep-worktree` — don't tear down worktrees (debug: inspect laid-down
  files); clean them up later with `python cli.py worktrees --prune` (or list
  them first with `python cli.py worktrees`)

After grading, `python cli.py report --axis methodology` prints the
Bradley-Terry ranking (Elo + bootstrap CIs), three-tier gate pass rates, the
cost rollup, analyzer flags, and the two stakes-based picks — and writes a
self-contained HTML artifact under `reports/` with the quality-vs-cost Pareto
frontier.

`python cli.py setup` makes a fresh clone fully runnable: it clones the task
repos, **deterministically rebuilds the synthesized task base commits** (a
task's feature reverse-applied onto a pinned upstream anchor, rebuilt with pure
git plumbing under fixed metadata — same sha on every machine, locked in
`tasks/_repo_setup/repos.lock.yaml`), vendors the methodology packs, and builds
the web UI. `python cli.py doctor` prints a green/red readiness table.

## Per-task toolchains

`moreiter-A` runs anywhere Python does — start there if you have neither WSL
nor the dotnet SDK. `cosmos-*` needs the .NET 8 SDK.

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
  cd "$(wslpath -a <path-to-gavel>)" && \
  python scripts/validate_tasks.py --verbose --skip-toolchain-check'
```

## Task fields & visible-test composition

A task lives in `tasks/<id>/task.yaml`. Beyond the required fields (`id`,
`repo_url`, `base_commit`, `instruction`, `run_cmd`, `held_out_tests_path`,
`reference_diff_path`, `build_cmd`), two fields control the **visible** tier (tier
2 of the gate — the tests the agent is allowed to see):

- `visible_test_cmd` — the command run for the visible tier.
- `visible_tests_path` — a directory of EXTRA visible test files this task injects
  into the worktree (committed before the repo-context/methodology commits, so
  they're visible to the model but never appear in its diff).

A task may also declare `observe_cmd`: an observational command whose exit code
and output are recorded on the scorecard but never gate. Use it instead of
smuggling extra checks through `run_cmd` — `run_cmd`'s exit code IS the hidden
gate, so anything non-functional folded into it would decide who is gradeable.

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

`scripts/validate_tasks.py --validate-transitions` also asserts the *resolved*
visible suite is green on the clean base commit (skipped when it resolves to none),
so a declared suite can't be one that doesn't build/pass.

> **Guardrail:** task-supplied visible tests must NOT duplicate the held-out
> oracle. Visible tests that ARE the hidden tests let the model trivially satisfy
> the gate. The gate already asserts held-out files aren't pre-present in the
> worktree; keep that assertion.

### Held-out-path collision (agent writes a test where the oracle lives)

An agent can naturally create a test at a path the held-out oracle also occupies
(on the cosmos-A shakedown, opus wrote `tests/.../Mappers/AuditMapperTest.cs`).
The gate handles this **provenance-aware**, SWE-bench style: the oracle always
wins, but only a *genuine* leak stays fatal.

The runner records the post-prepare, pre-agent HEAD as a worktree-local ref
(`grading.gate.BASELINE_REF`). At gate time, for a colliding held-out path:

- **Present in the baseline tree** (came in via a setup commit — repo-context /
  methodology / visible-tests) → *setup* provenance → **genuine leak, fatal.** The
  model would have seen the oracle.
- **Present only in the agent's diff** → *agent* provenance → **not a leak.** The
  gate overwrites the path with the true oracle and runs that; the agent's own
  content already survives in the captured diff for blind grading.
- **No baseline ref** (nop / oracle / manual don't record one) → provenance is
  unprovable → **fatal**.

This keeps the protected invariant intact — *the model never sees the oracle, and
the gate runs the true oracle* — while no longer failing an agent that merely
guessed the same test path. The overwritten agent file is restored after the run.

## Tests

```powershell
.venv\Scripts\python -m pytest                       # fast suite
.venv\Scripts\python -m pytest -m integration tests/test_ui_playwright.py   # browser regression
```

The Playwright suite (needs `python -m playwright install chromium`) asserts the
diff layout and the blinding invariants on the rendered page — run it after any
UI change.
