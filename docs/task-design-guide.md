# Task Design Guide

How to build *discriminative* evaluation tasks for setup-bench. The core lesson
from the research (`docs/research-eval-frameworks.md` §4): **the strength of your
hidden tests directly determines whether your ranking is real.** Weak tests don't
just inflate scores — EvalPlus showed they *reorder rankings*, and SWE-Bench+
found 31% of "passing" patches passed only because the tests were weak.

## What makes a good task

- **Mid-difficulty (30–70% pass rate).** Tasks where some methodologies pass and
  others fail carry the most discriminative information. A task everyone passes,
  or nobody passes, contributes ~zero signal (Item Response Theory; confirmed
  empirically on agent benchmarks). Target the 30–70% band.
- **Based on real failures.** Tasks should come from real observed coding
  challenges, not synthetic puzzles. Anthropic and LangChain both warn that toy
  tasks measure the base agent, not the methodology.
- **Cross-layer scope.** Tasks spanning multiple files, languages, or
  abstractions (like the PyVRP tasks: C++ → pybind11 → Python) are more
  discriminative because they exercise how a methodology handles real complexity.
- **Clear specification.** The instruction must be unambiguous. OpenAI found
  59.4% of o3's SWE-bench failures were test/spec flaws, not model limits. A
  vague instruction tests the agent's ability to guess, not the methodology.

## Anti-patterns to avoid

- **Too easy (ceiling).** If >70% of methodologies pass, the task can't
  discriminate. Replace it or make it harder.
- **Too hard (floor).** If <30% pass, you're measuring the base agent's raw
  capability, not the methodology. Replace it or make it easier.
- **Memorizable.** Don't use public-repo tasks at commits before the model's
  training cutoff where the fix is obvious from commit history. PyVRP's approach
  (custom branch, features removed) is good — verify the fix isn't recallable.
- **Solution leakage.** The instruction must not contain the solution: no file
  paths, function signatures, or implementation hints that give the answer away,
  and agents must not be able to read the gold patch from `git log --all` /
  `git show` or the test files. 32.67% of SWE-bench "successes" were leakage.
- **Weak hidden tests.** A test that checks "does a file exist?" without verifying
  behavior is worse than useless — it gives false confidence. Every hidden test
  must verify actual behavior, not surface compliance.
- **Exact-string-match tests.** Gating on a specific warning/error message, log
  line, or output format the ticket never states. The canonical SWE-bench failure
  (scikit-learn #14520) demanded an exact `DeprecationWarning` string that appeared
  only in the gold patch — un-passable. Assert behavior, not undescribed strings.
- **Un-guessable identifiers.** Grading that requires a new function/class/variable
  name introduced only in the gold patch and never implied by the ticket. (Naming
  the *public* deliverable the ticket asks for — `ReplaceGroup` — is the spec, not
  this anti-pattern.)
- **Ambiguous-but-strictly-graded.** An under-specified ticket paired with tests
  that demand one specific un-stated behavior. Under-specification is only valid
  when the tests accept *all* reasonable interpretations.
- **Flaky / order-dependent tests.** Non-deterministic outcomes (wall-clock,
  timezone, network, randomness, test order) inject noise into the ranking. Exclude
  a task until its hidden tests are deterministic across repeated runs.

## Golden-standard rubric

A task is *golden* only when **every** line below passes. This formalises the
"strength of hidden tests" thesis at the top of this doc into a per-task gate,
drawn from how SWE-bench Verified, EvalPlus, SWE-Bench+ and the IRT mid-range
filter actually build and filter tasks. Each line is tagged with how it's checked:

- `(auto)` — `scripts/validate_tasks.py --lint` (static, no build needed)
- `(auto: transitions)` — `scripts/validate_tasks.py --validate-transitions`
- `(auto: calibrate)` — `scripts/calibrate_tasks.py`
- `(auto: leakage)` — `python -m grading.leakage --repo <repo> --terms ...`
- `(eyeball)` — human audit; see "How to audit a task by eye" below

### Facet 1 — Task description quality
- [ ] All required `task.yaml` fields present and non-empty (id, base_commit,
      instruction, run_cmd, held_out_tests_path, reference_diff_path, build_cmd). `(auto)`
- [ ] The instruction is substantive, not a one-liner stub. `(auto)`
- [ ] The instruction does NOT embed the solution as a patch/diff or a fenced code
      block. `(auto)` — and the gold fix isn't reachable from the repo's working
      tree or git log. `(auto: leakage)`
- [ ] An engineer with repo access but no ability to ask questions could decide
      what a correct solution looks like (SWE-bench Verified issue-severity 0–1). `(eyeball)`
- [ ] Scope is bounded — in-scope vs out-of-scope stated where ambiguous. `(eyeball)`
- [ ] Any task-supplied visible tests (`visible_tests_path`) do NOT duplicate the
      held-out oracle. `(eyeball)`

### Visible-test composition (tier 2)

The visible tier is the tests the agent is *allowed to see*. Two knobs feed it:

- `visible_test_cmd` (task) — the command run for the visible tier.
- `visible_tests_path` (task) — a dir of EXTRA visible test files this task
  injects. They're committed before the repo-context/methodology commits, so
  they're visible to the model but never appear in its diff.
- A **repo** can declare a shared default in `repos.yaml` (project root) so tasks
  needn't each supply a `visible_test_cmd`. Presence of the key is the opt-in.
  Keep `repos.yaml` at the project root — a file inside `repos/<repo>` would leak
  into every worktree and become visible to the model.

The effective `visible_test_cmd` resolves as:

| `visible_test_cmd` in task.yaml | Effective visible tier |
|---|---|
| an explicit string | that string (task overrides the repo) |
| `null` / unset | the repo's `repos.yaml` cmd if it declares one, else none |
| `none` (sentinel) | none — force-skip even if the repo declares a suite |

> **Guardrail:** visible tests that ARE the hidden tests let the model trivially
> satisfy the gate. Task-supplied visible tests must not duplicate the held-out
> oracle; the gate keeps asserting held-out files aren't pre-present in the worktree.

### Facet 2 — Instruction language
- [ ] Reads like a real senior-engineer issue (motivation + symptom + expectation),
      not a restated unit test; describes outcomes, not test assertions. `(eyeball)`
- [ ] Not bloated into a spec-dump (an over-long instruction is an
      over-specification smell). `(auto)`
- [ ] If intentionally UNDER-specified, it's labelled as such and the held-out
      tests accept ALL reasonable interpretations. `(eyeball)`

### Facet 3 — Tests
- [ ] Held-out tests exist and are non-trivial — real `def test...` + `assert`, not
      a file-exists check. `(auto)`
- [ ] **FAIL_TO_PASS**: held-out tests fail on the clean base commit. `(auto: transitions)`
- [ ] **PASS_TO_PASS / build-gate**: tests pass with the reference diff and the
      build succeeds, proving the env and unrelated functionality are intact. `(auto: transitions)`
- [ ] Tests assert only behavior the ticket implies — no undescribed strings,
      internal names, or output formatting (test-severity ≤1). `(eyeball)`
- [ ] **Mutation adequacy**: ≥3 plausibly-wrong implementations are all killed by
      the suite; no surviving mutant passes the gate. `(eyeball)`
- [ ] Deterministic across repeated runs (no time/network/random/order sensitivity). `(eyeball)`

### Facet 4 — Representativeness
- [ ] The reference diff is a real cross-layer change touching more than one file,
      not a single-file kata. `(auto)`
- [ ] Solving it requires reusing existing helpers/conventions, not greenfield
      code from scratch. `(eyeball)`

### Facet 5 — Difficulty & calibration
- [ ] `difficulty` logged as metadata once known (labelled by hand after a sweep). `(auto)` (WARN until present)
- [ ] Measured pass rate lands in the discriminative band **0.30–0.70**; not at a
      0%/100% ceiling/floor. `(auto: calibrate)`

### How to audit a task by eye

The `(eyeball)` lines above can't be judged mechanically. Run these as fast yes/no
checks before promoting a task:

1. **Unambiguous?** Could a competent engineer with repo access build the right
   thing without asking a question? (Issue-severity 0–1.) If two engineers would
   build materially different things, it's not ready.
2. **Issue-shaped?** Does it read like a real ticket — motivation + symptom +
   expectation — and describe user/system outcomes rather than the test assertions?
3. **Under-spec handled?** If it's a deliberate ambiguity probe, is it labelled,
   and do the held-out tests accept every reasonable interpretation?
4. **Strong oracle?** Could a plausibly-wrong patch still pass? Mentally mutate the
   reference (off-by-one, inverted condition, dropped branch) — the suite should
   catch each. Watch for assertions on un-stated strings/ordering.
5. **Representative depth?** Does a correct solution reuse existing code and
   conventions, or is it a self-contained algorithm a model could write blind?
6. **Contamination?** Is this exact repo/PR/solution findable on the public web or
   plausibly in training data? If so it tests memory, not capability.

## Test design: FAIL_TO_PASS and PASS_TO_PASS

From SWE-bench's methodology:

- **FAIL_TO_PASS** — tests that *fail on the base commit* (before any change) and
  *pass after a correct implementation*. These prove the feature was actually
  implemented. If they still fail, the agent didn't solve the task.
- **PASS_TO_PASS** — tests that *pass on the base commit* and *still pass after*
  the agent's change. These catch regressions: a methodology that "fixes" the
  problem by breaking something else should fail.

Grading is strict and binary (SWE-bench): an instance is resolved only if **all**
FAIL_TO_PASS pass **and all** PASS_TO_PASS still pass.

Document which held-out tests are which — a header comment in each test file, or a
`test_manifest.yaml` per task. setup-bench's current held-out tests are
FAIL_TO_PASS-style (they exercise the new feature); add PASS_TO_PASS regression
tests as the suite matures.

### Validating the transitions

`scripts/validate_tasks.py --validate-transitions` checks, per task:

- **build gate** — `build_cmd` succeeds on the clean base commit (the base
  environment isn't broken).
- **FAIL_TO_PASS** — hidden tests *fail* on the clean base commit. If they pass,
  the tests don't actually require the feature → too weak.
- **PASS_TO_PASS (gold)** — hidden tests *pass* after applying `reference.diff`.
  If they fail, either the tests or the reference diff are broken.
- **visible suite** — the *resolved* `visible_test_cmd` (task override, `repos.yaml`
  default, or none) is green on the clean base commit. Skipped when it resolves to
  none. This keeps a declared visible suite honest — you can't ship one that
  doesn't build/pass.

Run it in WSL (PyVRP requires Linux to build):

```bash
python scripts/validate_tasks.py --validate-transitions --verbose
```

The static rubric checks need no build toolchain and run anywhere:

```bash
python scripts/validate_tasks.py --lint
```

It checks the `(auto)` rubric lines per task (required fields, instruction length,
held-out non-triviality, multi-file diff, instruction-leakage, difficulty present)
and exits non-zero on any FAIL. WARNs (e.g. a missing `difficulty` field) are
allowed.

## Difficulty labeling

After a calibration sweep, label each task in its `task.yaml` (`difficulty:`
field, values `easy` / `medium` / `hard`):

- `easy` — >70% pass rate (sanity check; catches broken setups)
- `medium` — 30–70% pass rate (maximum discriminative power)
- `hard` — <30% pass rate (stretch goal; avoids premature saturation as
  methodologies improve)

Keep a mix: a couple easy, a majority medium, a couple hard. Assign labels by
hand after reviewing calibration output — don't auto-assign.

Generate the calibration numbers with:

```bash
python scripts/calibrate_tasks.py --db results.db
```

It reports each task's pass rate across all methodologies and reps, bands it, and
flags ceiling (>70%) and floor (<30%) effects.

## How many tasks

For ranking a handful of methodologies the binding constraint is
`repetitions × tasks`, **not tasks alone**. Start with 3–5 tasks (current: 3) and
≥3 reps; spend marginal budget on reps before adding tasks. Aim for 10+ tasks
eventually to reduce per-task variance. With only 3 tasks you are highly exposed
to ceiling/floor effects — calibrate early and treat any 0% or 100% task as
providing no signal.
