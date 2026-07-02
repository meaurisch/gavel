# Fable run — plan (Phase 1 checkpoint)

Date: 2026-07-02. Author: Claude Fable 5, autonomous run on branch `fable-run`.
Scope: finish and elevate setup-bench to a polished, community-ready tool.
This doc is the Phase-1 deliverable: gap analysis → ordered work → acceptance
criteria → real-sweep budget. Implementation starts only on approval.

---

## (a) Gap analysis — verified against this clone, 2026-07-02

**Baseline state (verified, not assumed):** fresh `.venv` built; full suite is
**219 passed, 1 deselected** (README claims 204 — stale). WSL Ubuntu +
`~/pyvrp-venv` present; dotnet SDK 8.0.422 present; claude CLI 2.1.198
(README pins 2.1.185 — stale).

### A. The clone cannot run a single trial (reproducibility hole)

`repos/`, `methodologies/**/vendor/`, and `results.db` are all gitignored and
absent. Worse, `cosmos-A`/`cosmos-B` pin `base_commit: 3b033a8f…` — a **locally
synthesized commit** (upstream `f8a0105` + net8 migration, branch `cosmos-base`)
that exists only in the original workspace. A community user cloning this repo
today cannot run *anything*: no bootstrap script exists, and the cosmos base is
unrecoverable from what's committed. This is the single biggest gap between
"works on the author's machine" and "a tool the community can use".

### B. The known floor gaps (all confirmed real)

1. **`report` is a stub** (`cli.py:175-178` exits 1). `grading/aggregate.py` is
   an *empty* one-line module. No cost rollup, no Pareto frontier, no
   stakes-based pick, and — notably — **no adapter from persisted `judgment`
   rows to Bradley-Terry comparison tuples** (`fit_bradley_terry` wants
   `(value_a, value_b, outcome)` on axis values; nothing translates judgments
   into that outside the UI server's in-memory session).
2. **No Pareto visualization** anywhere.
3. **Grading UI shakedown blocked on gradeable data.** A gradeable cell needs
   ≥2 distinct comparison-axis values that *each* have a hidden-gate passer
   with the other axes pinned (`core/db.py:373-390`). This clone has no
   `results.db` at all; history says real haiku trials went 0/6 on the
   cosmos-A hidden gate, and oracle reps produce byte-identical diffs
   (useless for pairwise). So grading needs *engineered* gradeable data, not
   just "run more trials".
4. **`cli.py` cost-summary bug** (recalibration prompt 27): `total_usd` sums
   only non-errored trials, silently dropping real billed cost. Confirmed
   still unpatched at `cli.py:142-146`.

### C. Sibling bugs found in the sweep (each verified in source)

1. **Timeout path drops billed cost and burns the trial ID**
   (`runners/claude_code.py:100-104`): on `TimeoutExpired` the trial is
   persisted as a normal completed trial — `error=None`, no cost record —
   despite potentially hours of billed work; it is never retried and its
   partial diff can even reach the gate unflagged.
2. **Blind-diff over-redaction** (`grading/pairwise.py:160-162`):
   `anonymize_diff` substitutes every axis id case-insensitively with **no
   word boundaries**. The repo-context id `none` therefore clobbers Python's
   `None` throughout any PyVRP diff, wrecking readability and potentially
   *revealing* rather than hiding information.
3. **Grading sessions are memory-only** (`ui/server.py:76`): a server restart
   404s `/api/judge` and `/api/reveal`; Bradley-Terry results cannot be
   recomputed from the persisted `judgment` table. Also what blocks `report`
   from consuming past grading sessions.
4. **`/api/pairs` KeyError 500** (`ui/server.py:280-318`): a gate-passing
   trial with no `run_result` row raises an unhandled KeyError.
5. **Non-atomic trial persistence** (`core/executor.py:89-93` + per-insert
   commits in `db.py`): a crash between `insert_trial` and the later inserts
   leaves an orphan trial row that is skipped forever by resume dedup.
6. **Inconsistent pass-rate denominators**: `/api/reveal` counts only trials
   with a gate row (`server.py:504`), `/api/stats` counts all (`server.py:557`).
7. **`tasks.ps1 Watch` is a lie** — it just runs `pytest` once (duplicate of
   `Test`); no Report/Setup-for-repos verbs.
8. Minor: `/api/stats` endpoint is dead (never called by the UI); readiness
   message can report "2 distinct passing values" while 0 cells are gradeable
   (global vs per-cell count); stray `ui/static/vendor/requirements.txt`.

### D. Community-readiness gaps (the "elevate" axis)

- **No quickstart that works**: README documents flags, not a path from
  `git clone` to first ranking. No environment doctor, no bootstrap, no way to
  try the grading UI or report without spending money on real trials.
- **Every task requires WSL or the dotnet SDK** — there is no plain-Python
  task a newcomer can run cross-platform in minutes.
- **No LICENSE file** — not open-sourceable at all until one exists (proposal
  below). No screenshots; nothing in the README shows what the tool looks like.
- README "Current state"/"Next up" and the checklist/playbook describe the
  *original* workspace's data, not what a fresh clone contains.

---

## (b) Ordered work plan

**W0 — commit this plan; wait for approval.** *(you are here)*

**W1 — Correctness fixes, TDD, one commit each** *(independent of repos;
starts immediately)*
1. `cli.py` `_summarize()` extraction + errored-but-billed cost fix, per
   prompt 27's spec (regression test first).
2. Timeout path: persist a `RunResult` with `error="timeout after Ns"`,
   attempt cost parse of any captured stdout, and log loudly. A timed-out
   trial must never look like a clean $0 trial.
3. `anonymize_diff`: word-boundary matching; short/common ids (e.g. `none`)
   redacted only as whole tokens; regression tests with a realistic PyVRP diff.
4. `/api/pairs`: skip (with warning) passers lacking a `run_result`.
5. Persist grading sessions (new `grading_session` + pair tables or
   deterministic pair reconstruction) so `/api/reveal` survives restart and
   `report` can consume judgments. This is also the report's data spine.
6. Wrap per-trial persistence in one transaction.
7. Align the two pass-rate denominators; wire or remove `/api/stats`;
   per-cell readiness message.
8. `tasks.ps1`: honest verbs — `Watch` gains pytest-watch or is removed;
   add `Setup` (deps + bootstrap), `Report`, `Demo`.

**W2 — Reproducible bootstrap (the long pole; unblocks everything real)**
1. `scripts/bootstrap_repos.py` + `cli.py setup`: clone each task repo at its
   pinned commit into `repos/`, vendor methodology packs
   (`vendor_setup.py --all`), verify toolchains (`cli.py doctor`: git, claude
   CLI, dotnet, WSL + pyvrp venv), print a green/red readiness table.
2. **Reconstruct `cosmos-base` reproducibly**: redo the net8 migration on
   upstream `f8a0105`, guided by the committed `reference.diff` context and
   held-out tests; capture it as a tracked patch
   (`tasks/_repo_setup/cosmos-net8.patch`) applied by bootstrap with pinned
   author/committer/date → **deterministic sha on every machine**; update both
   cosmos task.yamls to the new sha (divergence from the original workspace
   sha documented in the task.yaml comment).
3. Golden validation on this machine: oracle PASS + nop FAIL for all 5 tasks
   (pyvrp via WSL dispatch, cosmos via dotnet 8), `validate_tasks.py` green.

**W3 — `report` command + Pareto frontier (the headline feature)**
1. Implement `grading/aggregate.py` for real: judgment→BT-comparison adapter,
   per-axis-value cost rollup (means + totals, errored-but-billed included),
   BT fit + bootstrap CIs + Elo display, Pareto frontier computation
   (dominated vs frontier), stakes-based picks per IMPLEMENTATION_PLAN §6
   (high-stakes → quality winner; routine → cheapest within CI overlap of the
   winner). Pure functions, fully unit-tested.
2. `cli.py report --axis … [--db …]`: Rich terminal summary (ranking table
   with CIs, gate tier pass-rates, cost rollup, analyzer flags, the two picks)
   +   a self-contained HTML artifact under `reports/` with an inline-SVG
   quality-vs-cost chart: CI bars, frontier marked, the two picks labeled, a
   legend a non-statistician can read (per prompt 18's design brief; no CDN,
   no heavy framework).
3. Tests: aggregation logic exhaustively; HTML generation smoke-tested.

**W4 — Gradeable data + UI shakedown (zero API spend)**
1. `cli.py demo`: seed a self-contained demo DB (synthetic but realistic
   trials/diffs/gate/cost across methodologies and models, clearly labeled
   demo) so any user can try grade → report in five minutes without a dollar.
   Doubles as the fixture source for report tests.
2. Real-pipeline gradeable data at $0: author 2–3 *distinct correct* solution
   variants for one task (stylistic derivatives of the reference diff that
   still pass the hidden tests), run them through the genuine
   worktree → `manual` runner → gate path under distinct methodology ids in a
   dedicated DB — real gate passers, really distinct diffs, no tokens.
3. Drive the UI end-to-end with Playwright (install as dev tool): axis picker
   → cell → blind A/B with keyboard → reveal with BT ranking. Capture
   screenshots into `docs/screenshots/`, inspect them, fix what looks broken
   or unpolished (including verifying blinding on the anonymization fix).

**W5 — Minimal real sweep (the only paid step; see (d))**
cosmos-A × {baseline, karpathy} × claude-haiku-4-5 × reps 2 = 4 trials.
Verify runner → gate → cost → resume on real model output; then grade/report
whatever passes (falling back to W4 data if 0/4 pass the hidden gate, which
history says is likely). Hard cap ≈ $2.

**W6 — Task-suite broadening (community on-ramp)**
Add **one pure-Python task** on a small upstream-pinnable repo (pip + pytest
gate, no WSL/dotnet) authored to the golden rubric: reference diff, held-out
tests, difficulty + stakes tags, oracle/nop validated. This becomes the
README quickstart task any user can run anywhere. A second one only if the
first lands smoothly under budget/time.

**W7 — Docs, license, final polish**
- README rewrite where stale (test count, CLI version, Current state, Next
  up), new **Quickstart** (clone → `setup` → `doctor` → `demo` → grade →
  report), screenshots embedded, honest WSL/dotnet requirements per task.
- Reconcile `RECALIBRATION_PLAYBOOK.md` + checklist to this clone's true state.
- **Add MIT LICENSE** (proposed — flag: your name goes on the copyright line;
  approving this plan approves MIT unless you say otherwise).
- Remove dead stubs (`copilot_cli` stays as a *documented* deferred runner
  that errors with a clear message — it is spec'd as deferred, not dead).

**W8 — Final verification + report**
Full suite green; `tasks.ps1` verbs exercised; fresh-clone bootstrap rehearsed
(delete `repos/` + vendor, re-run `setup`, golden re-validation); Playwright
visual pass re-run; final written report (what changed, what was left out,
next steps, exact real-sweep spend).

Commit discipline: small, logical commits throughout; subagents used for
parallelizable grunt work (W1 fixes, variant authoring, screenshot drives);
I own integration and verification.

---

## (c) Acceptance criteria / definition of done

1. **Tests**: full suite green (219+ existing + new; only the pre-existing
   env-gated deselect remains). Every W1 fix has a regression test that fails
   on the old code.
2. **Reproducibility**: from a fresh state (no `repos/`, no vendor, no db),
   `python cli.py setup && python cli.py doctor` reaches a state where
   `validate_tasks`-level golden checks pass: oracle PASS / nop FAIL on all
   tasks, cosmos base sha matches task.yaml deterministically.
3. **Report**: `python cli.py report` produces the Rich summary and the HTML
   artifact (BT ranking + CIs, gate pass-rates, cost rollup, analyzer flags,
   Pareto SVG with frontier + two labeled picks) against both the demo DB and
   the real-sweep DB.
4. **Grading**: UI exercised end-to-end on gradeable data (≥1 full session:
   pick axis → grade all pairs → reveal shows a BT ranking); sessions survive
   server restart; blinding verified on PyVRP-style diffs; screenshots in
   `docs/screenshots/` and embedded in README.
5. **Real sweep**: completed within the cap; footprint (trials, tokens, USD)
   reported; results persisted in `results.db` and rendered by `report`.
6. **Docs**: README quickstart is executable as written on a fresh clone;
   Current state / Next up truthful; LICENSE present; no secrets; clean
   history; nothing described as working that isn't.

## (d) Real-sweep size & justification

**4 paid trials** (cosmos-A × {baseline, karpathy} × haiku × 2 reps),
expected ≈ **$0.35–0.65** (reference: $0.081/trial for haiku/baseline on
cosmos-A), **hard cap $2.00**. Rationale: this is the smallest run that
exercises the *real* runner → gate → cost → resume path on two distinct
methodology lay-downs with a real model. It deliberately does **not** try to
buy hidden-gate passers (haiku went 0/6 historically; forcing passes would
mean opus-class spend for no additional pipeline proof) — the grade → rank
path is instead proven on $0 real-pipeline data (manual-runner variants) plus
the demo DB. Every other validation in this plan is token-free.

## Explicitly out of scope (and why)

- **Copilot runner (Phase R)** — deferred by decision 2026-07-01; no plan.
- **First calibration sweep (Phase M)** — needs real multi-model spend and
  human judgment on frozen tasks; out of budget and out of mandate.
- **LLM judge, cloud execution, Docker** — v1 skips per the plan's locked
  decisions.
- Rewrites of working subsystems (gate, matrix, runners, BT math) — they pass
  their tests; only the listed defects get touched.

## Top risks

1. **cosmos-base reconstruction** may fight me (net8 migration must satisfy
   reference.diff contexts + hidden tests). Mitigation: diff contexts pin the
   touched files; validation loop is free; worst case cosmos tasks stay
   validated-under-original-workspace and the clone documents that honestly —
   but I don't expect to need that fallback.
2. **Usage-window exhaustion** during W5 (seen in session 23/24): zero-token
   failures are already cleanly retryable; I retry in a later window rather
   than looping.
3. **Playwright on Windows** flakiness: screenshots are evidence, not a test
   dependency; UI correctness stays covered by pytest.
