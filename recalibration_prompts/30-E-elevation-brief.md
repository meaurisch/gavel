# 30-E — Elevation brief: from working instrument to trusted instrument

**Status:** authored 2026-07-06 on `ui-ux-revamp`, while the first real
measurement campaign sits at Checkpoint 2 (42 blind pairs awaiting the human
judge, $19.07 of the $20 cap spent — `docs/measurement-log.md`).

**Supersedes** the repo-agnostic `elevation-plan-brief.md` an earlier LLM
drafted. That brief was written blind, full of `[[ placeholders ]]`, and —
this matters — **most of what it proposes is already built and tested in this
repo** (see Part 0). Executing it as written would burn sessions rebuilding
existing invariants and never touch the actual frontier. This brief replaces
it with tasks grounded in what the campaign actually measured.

**How to use it:**

1. Close the open campaign first (Part 2). Nothing in Part 3 starts before
   Stage 4 lands and this branch merges to `main`.
2. Run each E-task as its own scoped session/request on its own branch off
   `main` — one task, one diff, one commit series, one review. Never batch.
3. Start every session with the Stage-0 verify ritual (Part 2). End every
   task with the self-check (Part 4).
4. Frozen-task changes and paid spend always stop at a human checkpoint.
   This brief authorizes **zero** new API spend by itself.

---

## Part 0 — Already built: do not rebuild (ledger against the old brief)

Every claim below is verifiable in the code; a future session should spot-check
rather than re-derive, and must not "implement" any of these again.

| Old-brief task | Reality in this repo |
|---|---|
| A1 blinding-leak audit / normalization | Built and regression-tested. One redaction implementation (`grading/pairwise.py::redact_axis_ids` + `anonymize_diff`) covers diffs, gate logs, reconstructed originals; instruction files stripped from served diffs; worktree hashes scrubbed; whole-token matching that survives snake_case gluing without mangling identifiers; leakage scanner + provenance-aware oracle-collision handling in `grading/gate.py` (`BASELINE_REF`); Playwright suite asserts blinding on the rendered page. Fourteen critic passes hardened it (see git log). |
| A2 position/order bias | **Half built.** Left/right is randomized per pair (`generate_pairs`, coin flip at `grading/pairwise.py:107`) with rep-balanced sampling. **Missing:** deliberate repeat/swapped pairs to measure judge self-consistency → E2.1. |
| A3 explicit ties | Built. `choice ∈ {A, B, tie}` end-to-end; `grading/aggregate.py` maps ties into Bradley-Terry. **Missing:** tie *rate* surfaced as an instrument signal → E2.3. |
| A4 rubric sub-scores | **Schema only — dead fields.** `Judgment.rubric_correctness/minimality/readability/overengineering` exist in `core/models.py` and the API accepts them (`ui/server.py:348`), but the grading UI never captures them and the report never reads them → E2.2. |
| B1 run manifest | Built. SQLite `results.db` (`core/db.py`): trial / run_result / gate_result / cost_record, deterministic trial ids, API-rate cost from `cost/pricing.toml`. |
| B2 one-command resumable runs | Built. `cli.py run` expands the 5-axis matrix, dedups by deterministic trial id (a crashed batch resumes without double-spend), `--dry-run`, inter-trial delay, live progress. |
| B3 environment pinning | Built where it counts: task bases deterministically resynthesized from `tasks/_repo_setup/repos.lock.yaml` (same SHAs on every machine), vendor packs pinned, pricing table data-driven. Residual: ambient toolchains (WSL venv, dotnet SDK, claude CLI version) are doctor-checked and README-recorded, not manifest-recorded — minor, fold into E1 only if it blocks something real. |
| C1 dashboard | Built. Web UI (dashboard/grading/launcher/browse/report) + self-contained HTML report with Pareto frontier and bootstrap CIs. |
| C2 methodology write-up | **Not done** → E5. |

What the old brief never saw, because only running the instrument could reveal
it, is the actual frontier:

- **Both .NET tasks shipped oracle-shape defects.** cosmos-A: 9 of 10
  hidden-tier trials failed on one un-guessable identifier
  (`DateCreatedUtc`); cosmos-B: 12 of 13 failed on a handler-ctor shape the
  instruction contradicted. The "33% discriminative" pass rate was
  substantially measuring an arbitrary style choice. Both were caught by
  $0 counterfactual re-gating and fixed under human OK (CP1, CP1.5). The
  three PyVRP tasks and moreiter-A **have never been audited for this defect
  family.** → E1
- **Post-fix, both swept cells saturate the hidden gate** (cosmos-B × haiku
  15/15, moreiter-A × sonnet 6/6). At current difficulties the gate is a
  floor-check; all discrimination now lives in one human's blind pairwise
  verdicts. → E2, E4
- **Nothing measures that human.** No self-consistency probe, no
  side-swap flip rate, no tie-rate signal. → E2
- **Human patience is the scaling bottleneck** — 42 pairs ≈ 1–2 hours, and
  pair count grows quadratically with corpus growth. CP2 is about to
  manufacture the one thing that can fix this: a pure human gold standard on
  blind-served content. → E3

---

## Part 1 — Non-negotiable constraints (every task, every session)

Grounded versions of the protected invariants; a change that improves
ergonomics but weakens one of these is a net loss.

1. **One blinding implementation.** Anything served during blind comparison
   goes through `redact_axis_ids` — never a parallel render path. Cost,
   tokens, and wall-clock are NEVER served during blind judging on any axis
   (human decision 2026-07-05). The Playwright blinding assertions
   (`pytest -m integration tests/test_ui_playwright.py`) must stay green
   after any UI-touching change.
2. **The model never sees the oracle.** Held-out tests live outside the
   worktree; leakage scanner and provenance-aware collision handling in
   `grading/gate.py` stay intact.
3. **Frozen golden tasks change only with an explicit human OK** at a named
   checkpoint — and the CP1/CP1.5 precedent is the template: back up
   `results.db` to `backups/`, then purge trials measured under the old
   instrument (deterministic trial ids would otherwise silently dedup-skip
   re-runs), stating plainly which judgments die with them.
4. **Never silently reinterpret recorded judgments.** A judgment binds a
   human verdict to the exact content served. If the content regenerates,
   the judgment is purged with a backup and a log entry (CP1.5 precedent) —
   never re-attached, never rescored. Schema changes are additive and
   nullable; old rows stay interpretable.
5. **Reveal is permanent** (`grading_session.revealed_at`): explicit
   confirmation, then the session closes forever.
6. **Budget discipline, free-first.** Every paid run gets a pre-estimate
   from DB history × `cost/pricing.toml` (the campaign's estimates landed
   within ±10% when done this way), spend is tracked as
   `sum(cost_record.usd_equiv)` against a recorded baseline — never hand
   arithmetic — and a human sets each campaign's hard cap. Prefer the free
   instruments first: `oracle`/`nop`/`manual` runners, the demo DB, and
   counterfactual re-gating of stored diffs.
7. **Minimalism is an acceptance criterion.** The project's thesis is that
   over-engineering is measurable and bad; every diff answers "is this the
   smallest change that fully solves the task?" before "does it work?"
8. **Full fast suite green** (`pytest`, 305 at last count) before any merge;
   README "Current state" stays truthful (repo convention: close-out commits
   update it).

---

## Part 2 — Sequencing gate: close the campaign before elevating

**Stage-0 verify ritual** (start of every session, ~2 minutes, no spend):
`python cli.py doctor` all green; fast suite green; `results.db` totals
reproduce the last logged numbers in `docs/measurement-log.md`. Drift found
here is a finding, not an obstacle — log it before proceeding.

Then, in order:

- **CP2 — the human grades.** 42 blind pairs per
  `docs/grading-brief-2026-07-06.md`. Claude neither grades nor reveals;
  this gold standard was deliberately purged to purity twice to get here.
- **Stage 4 — report + decision doc.** `cli.py report` per gradeable cell,
  plus the campaign decision doc. Must state the honest caveats already
  queued in the log: both cells gate-saturated (ceiling flags), the
  moreiter-A "67%" calibration number is a pooling artifact (0/3 haiku,
  6/6 sonnet), single judge, small corpus.
- **Merge `ui-ux-revamp` → `main`.** Elevation branches start from `main`.

E2.1 (consistency probes) is the one elevation task worth weighing *before*
CP2 grading: probes only measure a judge while they judge, and 42 fresh pairs
are about to be judged. It is small (Part 3). If the human would rather grade
now than wait for a feature, grade now — E2.1 then instruments the next
session instead. **Ask; don't decide this one unilaterally.**

---

## Part 3 — Workstreams

Ordered by leverage. Each task: one session, one diff. `Spend: $0` unless
marked.

### E1 — Spec-closure: turn the campaign's biggest discovery into a permanent instrument check

The oracle-defect family ("the held-out test demands a shape the instruction
never specified") invalidated more measurements than any other cause this
campaign — and was found by hand, twice, task by task. Make finding it
systematic.

- **E1.1 — Audit the unaudited suites.** Read the held-out tests of
  `pyvrp-A/B/C` and `moreiter-A` against the closure rule: *every public
  identifier, signature, and construction shape the oracle demands must be
  named in the instruction or derivable from the base repo's existing
  conventions.* (cosmos-A/-B are done — CP1/CP1.5.) Output:
  `docs/spec-closure-audit.md`, one verdict per task with the exact
  oracle lines at issue. Findings that need a frozen-task change stop at a
  checkpoint. Python's duck typing makes the pyvrp suites less prone to the
  compile-time variant but not immune — keyword-argument names and
  constructor signatures are the same trap. Spend: $0.
- **E1.2 — Lint what's lintable.** Extend `scripts/validate_tasks.py --lint`
  with the two known defect signatures: (a) public identifiers referenced by
  oracle tests that appear in neither the instruction text nor the base
  tree; (b) direct constructor calls of agent-authored types in oracle tests
  (the cosmos-B trap — prefer the `HandlerFactory` tolerant-construction
  pattern). Partial coverage is fine and expected; a lint that would have
  caught both known defects pays for itself. False positives are reviewable
  output, not build failures. Spend: $0.
- **E1.3 — Promote the counterfactual harness to a tool.** The campaign
  invented `scripts/simulate_cosmosA_namefix.py` ad hoc, then reinvented the
  pattern for cosmos-B. Generalize into
  `scripts/counterfactual_regate.py`: stored trial diff + candidate oracle
  edit → reconstructed worktree → real `grading.gate.apply` verdict, plus
  the GOLD (reference diff must pass) and BASE (must fail) checks. Zero
  spend by construction; already proven to correctly predict a $4.11 re-run
  direction-wise. Carry the two hard-won infra lessons (short worktree paths
  for Windows MAX_PATH; binary-mode patch writes). Spend: $0.
- **E1.4 — cosmos-A re-sweep** under the amended instruction (deferred from
  CP1 for budget). This validates the fix and restores cosmos-A as usable
  grading material. **Spend: paid — needs a fresh human budget OK**;
  estimate from stored per-methodology cost multipliers before asking.

*Avoid:* a general-purpose static-analysis framework. Two signatures, one
audit doc, one reusable script.

### E2 — Judge science: measure the judge, not just with the judge

With both gates saturated, one human's verdicts are now the entire ranking
signal. That instrument has an unmeasured noise floor.

- **E2.1 — Consistency probes.** Session construction gains k deliberate
  repeat pairs (same two trials, sides swapped, reinserted later at random
  positions — default k ≈ 10% of pairs, min 2). Probes are marked in the
  session data (additive field), **excluded from Bradley-Terry**, and yield
  two numbers: self-agreement rate and side-swap flip rate. Surface both at
  reveal time and in the report. The blind invariant is untouched — a probe
  looks exactly like any other pair to the judge. Spend: $0.
- **E2.2 — Resurrect the dead rubric fields.** The grading UI gains an
  *optional*, keyboard-driven sub-verdict step (correctness / minimality /
  readability / over-engineering) after A/B/T — skippable with a single
  key, never a gate in front of the verdict; the 42-pair marathon must not
  get slower for judges who decline. Report gains a sub-score decomposition
  where data exists. Existing NULL rows stay valid (constraint 4).
  Playwright coverage for the new surface. Spend: $0.
- **E2.3 — Tie rate as an instrument signal.** The analyzer already flags
  non-discriminating and flaky tasks; add tie rate per cell/task (a cell
  where everything ties is failing to discriminate at the *grading* tier —
  today only gate-tier saturation is flagged). Spend: $0.

*Avoid:* psychometrics theater. Three numbers — self-agreement, flip rate,
tie rate — reported honestly.

### E3 — The scaling unlock: a calibrated LLM judge (most ambitious)

Human grading caps the instrument at ~40 pairs per sitting; corpus growth
multiplies pairs quadratically. CP2 produces the calibration asset — a pure
human gold standard on blind-served content. Use it to find out, honestly,
whether an LLM judge agrees with the human often enough to earn scaled duty.

- **E3.1 — Grader identity in the schema.** Additive `grader` field on
  `grading_session` (`human` default, `llm:<model-id>` otherwise). Reports
  and Bradley-Terry consume human-only sessions **by default**; LLM sessions
  are opt-in per report invocation and never mix into the gold pool
  silently. Spend: $0.
- **E3.2 — The LLM judge is a client, not a fork.** It consumes the same
  server endpoints the browser does — the same `redact_axis_ids` payloads,
  no cost/tokens/time, instruction files stripped. It must be *impossible*
  for the judge path to see anything the human couldn't (constraint 1: one
  blinding implementation). Judge prompt versioned in-repo; temperature and
  model pinned in the session record. Spend: $0 to build (oracle/nop-style
  dry mode); paid to run.
- **E3.3 — Calibration report.** LLM judges every CP2 pair *both orders*
  (its position bias is measurable for free); report agreement rate and
  Cohen's kappa vs. the human, per cell, ties included, alongside the
  LLM's own flip rate. **Spend: paid but small** (est. from diff sizes —
  cosmos-B pairs run 13–55 KB; estimate before asking, human OK required).
- **E3.4 — The promotion gate, decided in advance.** Write the rule before
  seeing results: the LLM judge earns scaled duty only if its agreement
  with the human ≥ the human's own self-agreement (E2.1), and even then
  always with a declared human spot-check fraction. If it fails, the
  result still publishes in E5 — "we tested an LLM judge and it wasn't
  good enough" is a finding, not a failure.

*Avoid:* letting judge development contaminate the gold standard. The
Claude-made judgment was purged once already (CP1) to keep it pure; that
decision is load-bearing here.

### E4 — Recalibrate difficulty: make something discriminate again

- **E4.1 — Decide the doctrine first** (small doc + README/task-design-guide
  edit, no code): is the hidden gate *supposed* to discriminate between
  methodologies, or is it a floor-check with discrimination delegated to
  blind grading? The campaign log leans floor-check ("the instrument's
  discrimination now lives entirely in blind pairwise grading, which is
  what the tool was built around anyway") — but it's currently an emergent
  fact, not a stated design. The answer changes what `calibrate_tasks.py`'s
  30–70% band means and what E4.2 targets. Human decision, explicitly
  recorded. Spend: $0.
- **E4.2 — One harder task, authored under the new tooling.** If (and only
  if) E4.1 wants gate-tier discrimination: author one task targeting the
  30–70% band at sonnet-class models. Prefer a cross-cutting change in an
  already-onboarded repo (PyVRP or cosmos) — onboarding a new repo cost
  days of base-synthesis work per the git history, and the corpus needs
  difficulty spread more than repo count right now. Written against
  `docs/task-design-guide.md` **and the E1.2 lint from day one**; validated
  oracle-PASS/nop-FAIL; calibration probe (2 reps, cheapest plausible
  model) before any sweep. **Spend: paid probe — human budget OK.**
- **E4.3 — Complete cells only as reports need them** (moreiter-A ecc/custom
  slices, deferred Stage-2 leftovers). Not a standing goal; a cell earns
  spend when a specific report question needs it. **Spend: paid — per-cell
  human OK.**

### E5 — The public story

- **E5.1 — `docs/methodology.md`** for a domain-literate outsider: the five
  axes, three-tier gate, blinding machinery, Bradley-Terry with bootstrap
  CIs, the calibration doctrine from E4.1, and an honest-limitations
  section (single judge, small corpus, decision-support-not-proof — the
  README's register is the house voice). Include the E2 judge-reliability
  numbers once they exist. Spend: $0.
- **E5.2 — The campaign case study.** The oracle-defect discovery is the
  best evidence the instrument can catch its own measurement error: a
  benchmark that was quietly scoring a naming trap, caught and fixed for $0
  in API spend via counterfactual re-gating, under human sign-off, with the
  invalidated data purged rather than reinterpreted. Write it as a
  standalone piece; it is more persuasive than any ranking the tool will
  produce this year. Spend: $0.

*Avoid:* marketing tone, and any claim the CIs can't carry.

---

## Part 4 — Self-check (every task, before merge)

1. **Smallest diff:** does anything here exist because it might be useful
   rather than because this task needs it? Cut it.
2. **Constraint scan:** reread Part 1 against the diff — especially 1
   (blinding path), 3–4 (frozen tasks, judgment integrity), 6 (spend).
3. **Suites:** fast suite green; Playwright integration suite after any
   UI-touching diff; `validate_tasks.py --lint` after any task-file diff.
4. **Blind-judge your own diff** against the four rubric dimensions the
   schema names (correctness, minimality, readability, over-engineering) —
   the tool's own standard, applied to its author. Report the verdict.
5. **Truth maintenance:** does README "Current state" / the measurement log
   need a line? Write it in the same commit series.

---

## Part 5 — Suggested order

| # | Task | Spend | Checkpoint |
|---|------|-------|-----------|
| 0 | CP2 human grading + Stage 4 report/decision; merge to main | $0 | CP2 (human grades), Stage 4 review |
| 1 | E2.1 consistency probes (see Part 2 note on timing vs. CP2) | $0 | — |
| 2 | E1.1 spec-closure audit (pyvrp × 3, moreiter) | $0 | if findings → frozen-task OK |
| 3 | E1.3 counterfactual harness | $0 | — |
| 4 | E1.2 spec-closure lint | $0 | — |
| 5 | E2.2 rubric capture + E2.3 tie rate | $0 | — |
| 6 | E4.1 gate doctrine decision | $0 | human decides |
| 7 | E3.1 + E3.2 LLM-judge plumbing (dry mode) | $0 | — |
| 8 | E3.3 LLM-judge calibration run | paid | budget OK |
| 9 | E1.4 cosmos-A re-sweep | paid | budget OK |
| 10 | E4.2 harder task (only if E4.1 says so) | paid probe | frozen-corpus + budget OK |
| 11 | E5.1 + E5.2 write-ups | $0 | human review |

The table is a default, not a contract — reorder after CP2's results land,
the way the campaign reordered after CP1's did.
