# Progress log (archived from the README, 2026-08)

The detailed build history that used to live in the README. Kept for
reference; the README now carries only a short status. Dated decisions and
measurement results are in [`../measurement-log.md`](../measurement-log.md).

## State as of 2026-08

The full pipeline is built and tested (464 fast tests green plus a 24-test
Playwright UI suite behind the `integration` marker, 1 env-gated test
deselected) — engine, 5-axis matrix, three-tier gate, axis-general blind
grading in **two modes** (manual double-blind and LLM judge), Bradley-Terry
ranking, API-rate cost, the report command with the quality-vs-cost Pareto
frontier, and task-quality tooling. The task set spans two repos/languages
(PyVRP C++/Python and a .NET Cosmos DB service).

**LLM-judge mode (2026-07-06).** A second grading mode judges blind pairs
automatically: provider seam (`grading/judge_providers.py`) with `claude-cli`
(subscription, no API key), `gh-models` (GitHub free/org/enterprise), and a
deterministic zero-spend `mock`; position-swapped double passes with
disagreement→tie; strict-JSON verdicts with a self-correction retry loop; a
`judge_call` usage-audit table; typed `JUDGE` spend gate; blind progress page;
reveal enriched with rationales, swap-consistency, and judge spend; report
grader filter + human↔LLM agreement (Cohen's κ). Design notes in
`docs/superpowers/specs/2026-07-06-llm-judge-design.md`.

**Judge-mode adversarial hardening (2026-07-07).** A dedicated critic session
stress-tested the mode across blinding, parsing, races, migration, stats,
cost, and UX (commits `judge-critic-pass-1…7`): the task instruction now goes
through the same redaction as diffs, BlindingError fails closed without
naming the leaked id, hostile provider replies (NaN confidence, non-dict
rubric, 100KB prose) degrade into the retry loop instead of killing runs,
failed pairs still land their billed calls in the `judge_call` audit, a
reveal racing an in-flight provider call discards the verdict, claude-cli
usage is recorded honestly (cache-creation tokens + the CLI's own cost — a
one-shot `claude -p` call parks ~24k prompt-side tokens in cache), plan
estimates are measured per provider, and diff-budget truncation persists to
the judgment row and reveal. One bounded real run (cosmos-B model axis,
claude-haiku-4-5, 6 calls, 3/3 swap-consistent, rationales verified against
the diffs) is written up in the design doc's testing section.

**Consistency probes (E2.1, 2026-08-01).** Human grading sessions now measure
the judge as well as the contenders: session construction inserts ~10% (min 2)
deliberate repeat pairs with sides swapped, placed after their originals at
random positions (`grading/pairwise.insert_probes`). Probes are
indistinguishable on every blind surface (Playwright-asserted); their verdicts
are stamped (`judgment.is_probe`), excluded from Bradley-Terry and win/loss
summaries, and yield two instrument numbers — self-agreement and side-swap
flip rate — at reveal, in the report UI/CLI, and in the HTML artifact. Schema
changes are additive (`grading_session.probe_of`); legacy sessions and
LLM-judge sessions (which already measure consistency via position-swapped
double passes) are unaffected.

**Blinding-leak fix (2026-08-02).** Agents sometimes *commit* their own
planning/progress artifacts, which no pack lays down and the leakage scanner
therefore never sees — yet a `.agent-plans/` folder in a served diff names the
methodology on sight. The single serve-side stripper
(`grading.pairwise.METHODOLOGY_DIR_PREFIXES`, which governs blind diffs, the
diff-shape proxy and the reconstructed-originals endpoint) now drops it at any
depth, covering recorded and future runs without touching the frozen packs or
the runner's diff capture.

**A fresh clone is fully reproducible.** Task base commits are locally
synthesized (a task's feature reverse-applied onto a pinned upstream anchor;
for cosmos, a csproj/sln-only net8 migration patch) and are rebuilt by
`python cli.py setup` with pure git plumbing under fixed metadata — every
machine derives the same base shas, locked in
`tasks/_repo_setup/repos.lock.yaml`. All five tasks re-validate on the
rebuilt bases: oracle PASS / nop FAIL (pyvrp via WSL, cosmos via dotnet 8).

**The whole decision loop has run end-to-end.** The web UI carries a
committed Playwright regression suite (`pytest -m integration
tests/test_ui_playwright.py` after `python -m playwright install chromium`):
measured pane-width equality, line-number/scroll tracking, three-way view
alignment, per-axis blinding on the rendered page, an 18-pair keyboard
marathon with a mid-session reload, and the paid-runner spend gate. The
grading flow was also shaken out on both the synthetic demo DB and real
pipeline data: four
manual-runner cosmos-B trials (two hand-authored solution variants) passed
the hidden gate, were graded blind through the UI — with blinding verified on
the served diffs — and produced a Bradley-Terry ranking and report, at zero
API cost. A minimal real sweep (cosmos-A × baseline/karpathy ×
claude-haiku-4-5 × 2 reps, $1.23 total) exercised the claude-code runner,
per-methodology lay-down, the gate tiers, token-priced cost capture, and the
retry-on-transient-failure path against the live CLI. Hidden-gate passes:
0/3 — cosmos-A remains uncalibrated for haiku (a known, measured gap; see
Next up).

That shakedown also caught and fixed a founder bug: the grading UI's diff
panes had never rendered (wrong diff2html global — blank panes by
construction, invisible until gradeable data existed). Sessions are now
persisted (rankings survive a server restart), judgments are
latest-wins-per-pair (re-grading can't double-weight Bradley-Terry), diff
blinding matches whole tokens without mangling identifiers, and errored-but-
billed trials are counted in the run-summary cost total.

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

## Next up as of 2026-08

- [x] **A2/A3 measurement runs** — done 2026-07-03 ($11.71 total, 26 billed
      trials): all five methodologies and both repo-contexts ran for real on
      cosmos-A (haiku), plus a calibration slice on cosmos-B and moreiter-A.
      First real gradeable cell (cosmos-B: baseline + karpathy hidden-gate
      passers) produced and blind-graded.
- [ ] **Calibration decisions** — measured pass rates: cosmos-B 33% (in the
      30–70% band, discriminative), cosmos-A 0/17 and moreiter-A 0/3 (floor
      effect for claude-haiku-4-5). Decide per task: ease the hidden gate, or
      scope the task to stronger models. Frozen golden tasks change only with a
      human OK (`recalibration_prompts/19-M-calibration-sweep.md`).
- [ ] **Grow the real ranking** — one blind judgment exists on the real cell;
      Bradley-Terry needs ≥3 comparisons. More reps on cosmos-B (cheap:
      ~$0.11/trial) and/or your own grading session gets there. The pre-existing
      judgment lives in session `c38ed5475724451ab3bb8caedf5d2e2b` (graded by
      Claude, not you — delete that session's judgment rows if you want a pure
      human gold standard).
- [x] **Pure-Python starter task** — `moreiter-A` (more-itertools
      running-aggregates family): pip+pytest gate, no WSL, no dotnet.
      oracle=PASS / nop=FAIL on Windows; base rebuilt deterministically like
      the others.
- [~] **Phase R (Copilot) — DEFERRED (2026-07-01)** — no Copilot account/plan on
      hand. Runner axis stays coverable via the `manual` runner. Revive prompts
      11–13 if a Copilot plan appears.
- [x] **UI/UX rebuild + rebrand to gavel** — single web entry point, axis
      picker with hover previews, equal-width diff panes with tracked line
      numbers, three-way Original | A | B view, full gate scorecard, Gavel
      design tokens (light + dark). Log: [`../ui-revamp-log.md`](../ui-revamp-log.md);
      original brief: `recalibration_prompts/28-U1-ui-ux-professionalization.md`.
