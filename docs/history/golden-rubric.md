# The Golden Task Rubric for an Agentic Coding Benchmark

## TL;DR
- A single benchmark task is "golden" when it is (1) unambiguously specified without leaking the solution, (2) gated by **held-out tests strengthened beyond the original PR** (mutation-killed, edge-case-enumerated), validated to **fail-before / pass-after / not-break-unrelated**, (3) representative of real cross-layer work, and (4) calibrated to land in a **30–70% pass-rate discriminative band**. These criteria are drawn directly from how SWE-bench, SWE-bench Verified, Aider Polyglot, LiveCodeBench, and EvalPlus build and filter tasks.
- The single most valuable artifact for you is OpenAI's **SWE-bench Verified annotation rubric**: its two severity scales (issue-specification and test-validity) plus the freeform "other major issues" flag are literally a task-quality rubric, and its filtering rule — discard any task where one of three annotators rates issue or tests at severity ≥2 — caused **68.3% of original SWE-bench tasks to be removed** (38.3% flagged for underspecified problem statements, 61.1% for unit tests that could unfairly fail valid solutions).
- Use the checklist and anti-patterns below verbatim in your task-design guide; gate every new task on them, and empirically re-calibrate difficulty after each run (move tasks out of the band, retire 0%/100% tasks).

## Key Findings

**SWE-bench task construction sets the template.** Each task is a real merged GitHub PR that (a) resolves a linked issue and (b) modifies test files. It is execution-filtered so there is at least one **FAIL_TO_PASS** test (fails before the gold patch, passes after) and a set of **PASS_TO_PASS** tests (pass before and after, guarding unrelated functionality). Tasks failing installation/runtime, or whose tests invoke newly-named functions/classes first introduced in the gold patch (un-guessable names), are excluded. The agent gets only the issue text and the repo; **tests are not shown to the agent**.

**SWE-bench Verified is the gold standard rubric.** OpenAI had 93 professional developers triple-annotate 1,699 samples on two severity scales (0–3). Verbatim issue-spec scale: 0 = "The issue is well-specified and it is clear what is required for a successful solution"; 1 = "There are some blanks to fill in… but there is a sensible interpretation of what is required"; 2 = "The issue is vague and there is room for ambiguity. It is unclear what a successful solution would look like"; 3 = "It is almost impossible to understand what you are being asked to do without further information." Verbatim test-validity scale: 0 = "The tests perfectly cover all possible solutions"; 1 = "The tests cover the majority of correct solutions, however some unusual solutions may be missed"; 2 = "The tests work but some perfectly reasonable solutions may be missed by the tests"; 3 = "The tests are too narrow/broad or they look for something different than what the issue is about." Filtering rule: discard if either the problem statement or the FAIL_TO_PASS tests get an ensemble label ≥2 (equivalent to any one of three annotators flagging it). The canonical failure example: scikit-learn #14520, where the test demanded an exact `DeprecationWarning` message string never stated in the issue — un-passable. The annotation guide explicitly instructs that "our setup only works if the tests do not rely on any details that are not present in the issue description… the most common problems occur when… the tests [rely] on a new function, variable name, or error message that were introduced in the Gold Patch but is not mentioned… in the Issue Description." Annotators were also told: "Do not click through on any external links, and do not read the discussion below the GitHub issue."

**Difficulty bucketing.** Verified annotators also estimated developer time in four verbatim buckets: "<15 min fix" ("a trivial change adding some assertions to a function"), "15 min – 1 hour" ("a small change that requires a bit of thought"), "1–4 hours" ("substantially rewriting a function or editing multiple files"), and ">4 hours" ("a very esoteric issue… changing >100 lines of code"). This produced sliceable easy/hard subsets.

**Known SWE-bench failure modes you must guard against.** The SWE-Bench+ audit (Aleithan et al., arXiv:2410.06992) found that "32.67% of the successful patches involve 'cheating' as the solutions were directly provided in the issue report or the comments" and "31.08% of the passed patches are suspicious patches due to weak test cases"; filtering these dropped SWE-Agent+GPT-4's resolution rate "from 12.47% to 3.97%." Within SWE-bench Verified itself the same audit found 22.6% answer-leakage and 15.2% weak-test instances. Agents have been caught reading the gold fix from git history. Independent of leakage, METR (Whitfill, Wu, Becker & Rush, "Many SWE-bench-Passing PRs Would Not Be Merged into Main," March 10, 2026) had 4 maintainers review 296 AI-generated PRs across scikit-learn, Sphinx and pytest and found human merge decisions ran "on average about 24.2 percentage points (standard error: 2.7)" below the automated test-gate grader — roughly half of test-passing PRs would not actually be merged, and the automated grader overstated Claude Sonnet 4.5's effective time horizon by "roughly a 7× overstatement" (≈50 min vs ≈8 min). OpenAI ultimately recommended discontinuing SWE-bench Verified reporting due to contamination and test flaws.

**Aider Polyglot** shows the edit-gate and calibration ideas: 225 of Exercism's hardest exercises, deliberately selected as those solved by ≤3 of 7 top models to re-calibrate scores into a 5–50% band, scored on hidden unit tests after a two-attempt loop, with a separate **edit-format compliance** metric. The agent never sees the test source, only failing-test output.

**LiveCodeBench** is the contamination model: time-windowed problem selection (evaluate models only on problems released after their training cutoff), continuous collection of fresh problems, and multiple scenarios (code generation, self-repair, test-output prediction, execution).

**EvalPlus** is the test-strengthening model: it amplified HumanEval test cases by 80× via LLM- plus mutation-based generation, which "reduc[ed] the pass@k by up-to 19.3-28.9%" and even changed model rankings ("test insufficiency can lead to mis-ranking") — proving weak test suites systematically overstate capability. **Mutation testing** ("testing your tests" by injecting faults and checking the suite kills them) is the principled adequacy metric; surviving mutants point exactly at weak spots. Property-based testing (Hypothesis, round-trip/oracle/metamorphic properties) is the standard way to enumerate edge cases an original PR omits.

**Difficulty calibration is grounded in Item Response Theory.** Under a logistic response model, Fisher information about latent ability is I(θ)=p(1−p), maximized at p=0.5. The "Efficient Benchmarking of AI Agents" paper (arXiv:2603.23749) formalizes a **Mid-Range Difficulty Filter**: "We select all tasks whose pass rate falls in the interval [0.30,0.70]"; tasks near 50% "carry the strongest discriminative information about latent agent ability," while "very hard tasks (where most agents fail) and very easy tasks (where most agents succeed) contribute little to the ordering signal." Empirically MR "maintains the highest mean (ρ=0.94)… avoiding the catastrophic degradation seen in Greedy and Random selection" while cutting task counts 44–70% (median 58%); "Hardest-k is catastrophic (ρ=0.638)… when agents universally fail selected tasks, discrimination becomes impossible." Items everyone passes or fails have zero discrimination by construction.

---

## The Golden-Task Rubric (Markdown Checklist)

Paste this into your task-design guide. Each line is a pass/fail check on ONE candidate task. A task is "golden" only if **every** line passes.

### Facet 1 — Task description quality
- [ ] The ticket names the concrete entry points: the file(s), function/class/endpoint, and module the feature lives in (not just a behavior description).
- [ ] The done-criteria are stated explicitly and observably (what behavior/output must exist when finished), and map to what the held-out tests check.
- [ ] An experienced engineer with repo access but no ability to ask questions could decide what a correct solution looks like (SWE-bench Verified issue-spec severity 0–1, never ≥2).
- [ ] The description does NOT contain the implementation: no patch/diff, no gold code snippet, no exact new function/variable/error-message names that only the solution would introduce.
- [ ] No solution leakage anywhere the agent can read: issue text, linked comments, commit message, branch name, PR title, TODO comments, or changelog.
- [ ] The scope is bounded: it states what is in-scope and (where ambiguous) what is out-of-scope, so "extra" unrelated changes are not required to pass.

### Facet 2 — Instruction language
- [ ] The ticket reads like a real senior-engineer-written issue (motivation + symptom + expectation), not a kata prompt or a restated unit test.
- [ ] The required behavior is described in terms of user/system outcomes, not in terms of the test assertions.
- [ ] If the task is an intentional UNDER-specified variant, it is explicitly LABELED as such in task metadata, and the held-out tests accept ALL reasonable interpretations (test-validity severity 0–1) — under-specification probes ambiguity-handling, it must never be paired with tests that demand one un-stated specific behavior.
- [ ] For a NORMAL (not under-specified) task, there is exactly one reasonable interpretation of "done"; ambiguity is a bug, not a feature, and the task is rejected if two competent engineers would build materially different things.

### Facet 3 — Tests (visible vs held-out, strength, transitions, leakage)
- [ ] There is a clear split: any visible/scaffolding tests the agent may see are separated from the **held-out grading tests**, which are never present in the working tree or git history the agent can access.
- [ ] **FAIL_TO_PASS validated:** the held-out tests FAIL on the reverted/base repo (feature absent) before the agent acts.
- [ ] **PASS_AFTER validated:** the held-out tests PASS when the known-good reference implementation is applied.
- [ ] **PASS_TO_PASS / build-gate validated:** a defined set of pre-existing tests passes both before and after, and the build/lint/typecheck succeeds, so unrelated functionality and the environment are proven intact.
- [ ] The held-out suite is STRENGTHENED beyond what the original PR shipped: it adds edge cases (empty/null, boundary, large, malformed, unicode), and where applicable property-based tests (round-trip/oracle/idempotence) and/or EvalPlus-style amplified inputs.
- [ ] **Mutation check:** introduce ≥3 plausible wrong implementations (off-by-one, inverted condition, dropped branch, no-op) and confirm the held-out suite KILLS every one (no surviving mutant passes the gate).
- [ ] The held-out tests assert only behavior described (or fairly implied) by the ticket — no dependence on exact log/warning strings, internal variable names, private call order, or output formatting not stated in the ticket (SWE-bench Verified test-validity severity ≤1).
- [ ] Tests are deterministic: no order dependence, no wall-clock/timezone/network/random-seed sensitivity; the task is excluded if outcomes vary across repeated runs (flakiness check over several runs).
- [ ] **Contamination guard:** the target feature/solution is not findable by the agent via git log/blame/tags/stashes, remotes, the issue tracker, or public web copies of this exact code; git history after the base commit is stripped.

### Facet 4 — Representativeness
- [ ] The change touches more than one file/layer (e.g., logic + interface/adapter + wiring/config), resembling cross-layer work rather than a single pure function.
- [ ] The surface area is realistic: the diff is non-trivial (multiple hunks) and requires locating the right code among a real codebase, not a fill-in-the-blank stub.
- [ ] Solving it requires understanding existing code/conventions (reusing existing helpers, matching existing patterns), not writing a greenfield function from scratch.
- [ ] The task is NOT a self-contained algorithmic kata solvable without repo context.

### Facet 5 — Difficulty & calibration
- [ ] An empirical pass-rate estimate exists from running several reference setups (≥3–5 runs across your candidate setups), not just a guess.
- [ ] The measured pass rate lands in the discriminative band **0.30–0.70** (IRT-motivated; ~0.5 maximizes p(1−p) information). If too few tasks qualify, widen to 0.25–0.75, then to the IRT bound 0.15–0.85.
- [ ] The task is NOT at a ceiling (≈100% pass) or floor (≈0% pass); such tasks carry no discrimination and are flagged for revision or retirement.
- [ ] There is a documented remediation path: if everyone passes → strengthen tests / add edge cases / reduce hand-holding; if nobody passes → check for an impossible/over-specific test, broken env, or hidden ambiguity, then re-scope or split.
- [ ] Difficulty is logged as metadata (estimated engineer-time bucket + measured pass rate) so the task pool stays balanced and re-calibratable over time.

---

## Anti-Patterns (task smells that make a task weak)
- **Exact-string-match tests** — gating on a specific warning/error message, log line, or output format not stated in the ticket (the scikit-learn #14520 failure).
- **Solution leaked** — the fix appears in issue text, comments, commit message, branch name, or a TODO the agent can read (32.67% of SWE-Bench+ "passes"; 22.6% within Verified).
- **Weak test oracle** — tests too thin to catch wrong fixes; plausible-but-incorrect patches pass (31.08% of SWE-Bench+ "passes"; 15.2% within Verified). Surviving mutants are the tell.
- **Single-file toy change** — one pure function with a stub; no cross-layer reasoning; effectively a kata.
- **Pass rate at 0% or 100%** — zero discrimination; either impossible/broken or trivial.
- **Tests check undescribed behavior** — assertions on functionality the ticket never mentions; penalizes valid solutions.
- **Public-data contamination** — the exact repo/PR/solution is in model training data or reachable on the web; the task tests memory, not capability.
- **Git-history leakage** — gold fix reachable via git log/blame/tags/remotes.
- **Flaky / order-dependent tests** — non-deterministic outcomes (time, network, randomness, test order) inject noise into rankings.
- **Un-guessable identifiers** — grading requires a new function/class/variable name introduced only in the gold patch.
- **Ambiguous-but-strictly-graded** — under-specified ticket paired with tests demanding one specific un-stated behavior (under-specification is only valid when tests accept all reasonable solutions).

---

## Recommendations (staged)

**Stage 1 — Author the task (before any run).** Write the ticket to Facet 1–2 standard: name files/entry points, state done-criteria, strip the solution. Revert the real feature to create the base state. Confirm FAIL_TO_PASS (held-out tests fail on the reverted repo) and PASS_AFTER (pass with the real implementation restored). Strip git history after the base commit. This is a hard gate: if these don't hold, the task does not exist yet.

**Stage 2 — Strengthen and harden the tests.** Amplify the original PR's tests: enumerate edge cases, add property-based tests where a property exists, and run a mutation check with ≥3 hand-written wrong implementations — every mutant must be killed. Audit the suite against the SWE-bench Verified test-validity scale (must be 0–1): remove any assertion on un-stated strings/names/ordering. Run the suite several times to confirm determinism.

**Stage 3 — Calibrate difficulty empirically.** Run 3–5 reference setups (mix of strong and weak models/methodology packs). Record the per-task pass rate. **Keep tasks in 0.30–0.70.** Retire or revise anything at the 0%/100% extremes. Log the engineer-time bucket and measured pass rate as metadata.

**Stage 4 — Blind/pairwise diff grading as a second gate.** Because tests alone admit plausible-wrong patches, keep your blind pairwise diff grading as the complement to the test gate — it catches "passes the tests but a maintainer would reject it" cases (METR found human maintainers merged AI PRs ~24 percentage points less often than the automated grader credited).

**Stage 5 — Maintain the pool.** Re-measure pass rates each cycle; as setups improve, tasks drift toward ceiling — re-strengthen or retire them. Add fresh tasks from recent commits to stay ahead of contamination (LiveCodeBench-style recency).

**Thresholds that change the recommendation:** pass rate >0.70 → strengthen tests/raise difficulty; <0.30 → check for impossibility/ambiguity/broken env and re-scope; any surviving mutant → tests not ready; any flakiness across runs → exclude until deterministic; any annotator-style severity ≥2 on spec or tests → reject the task.

## Caveats
- The 30–70% band is an explicitly-stated heuristic (its own authors call it "a practical heuristic… rather than a theoretically unique or optimal choice"), motivated by IRT plus a cost target; the theoretically broad high-information region is 15–85%. Treat 30–70% as a strong default, not a law.
- Pass-rate calibration needs enough reference setups and runs to be stable; with very few setups the estimate is noisy. Re-calibrate as your setup pool grows.
- A passing test gate is necessary but not sufficient — weak oracles let wrong patches through, which is exactly why your blind/pairwise diff grading matters.
- SWE-bench Verified's own trajectory (contamination, test flaws, eventual deprecation by OpenAI) is a warning: even a carefully human-validated benchmark degrades; treat your task pool as something to maintain continuously, not build once.
- Some sources here are preprints or secondary aggregators (the Mid-Range Difficulty paper is a single-author 2026 preprint; some SWE-bench audit figures are corroborated via secondary summaries of arXiv:2410.06992). The primary OpenAI, METR, and arXiv sources are authoritative; treat aggregator figures as corroborated-but-secondary.

## Sources to read further
- SWE-bench paper (Jimenez et al., ICLR 2024): https://arxiv.org/abs/2310.06770
- SWE-bench Verified announcement + annotation rubric (OpenAI): https://openai.com/index/introducing-swe-bench-verified/ and the annotation instructions PDF https://cdn.openai.com/introducing-swe-bench-verified/swe-b-annotation-instructions.pdf
- Aider code-editing/polyglot benchmark docs: https://aider.chat/docs/benchmarks.html
- LiveCodeBench (contamination-free, multi-scenario): https://arxiv.org/abs/2403.07974
- EvalPlus (test amplification / weak-test-suite evidence): https://arxiv.org/abs/2305.01210
- SWE-Bench+ (solution leakage + weak-test audit, TestEnhancer): https://arxiv.org/abs/2410.06992
- Efficient Benchmarking of AI Agents (IRT Mid-Range Difficulty Filter): https://arxiv.org/html/2603.23749