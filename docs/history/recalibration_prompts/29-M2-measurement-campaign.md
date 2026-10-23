# 29-M2 — The first real measurement campaign (calibrate → sweep → grade → decide)

**Service:** Claude Code (Fable), autonomous with explicit human checkpoints.
**Branch:** create `measurement-campaign` off the current default working
branch. Commit incrementally, no merge/push — the human reviews.
**Goal:** gavel exists to answer one question and has never answered it:
*which methodology should I adopt, and at what cost?* Produce the first
defensible Bradley-Terry methodology ranking on real data, and a written
adoption decision per the stakes rule (IMPLEMENTATION_PLAN §6).

Read first: `README.md`, `CLAUDE.md`, `IMPLEMENTATION_PLAN.md`,
`docs/task-design-guide.md`, `docs/ui-revamp-report.md` (what the UI can do
now). The engine, gate, blinding, and UI are done and converged — do NOT
rebuild them. This prompt is about *using* the instrument.

======================================================================
STATE YOU INHERIT (verify, don't re-derive)
======================================================================

- Measured pass rates (claude-haiku-4-5): cosmos-B 33% hidden-gate (in the
  30–70% discrimination band — usable as-is), cosmos-A 0/17 and
  moreiter-A 0/3 (floor effect — zero signal at haiku). pyvrp-A/B/C are
  validated (oracle PASS / nop FAIL) but have never had a real sweep.
- One real gradeable cell exists (cosmos-B × none × haiku × claude-code,
  baseline vs karpathy passers) with 2 blind judgments — BT needs ≥ 3.
- One pre-existing judgment was made BY CLAUDE, not the human, in session
  `c38ed5475724451ab3bb8caedf5d2e2b` (see README "Next up").
- Historical cost: ~$0.11/trial for cosmos-B × haiku; $11.71 total for the
  entire 26-trial A2/A3 run. `cost/pricing.toml` has current rates; the
  run-launcher's estimator uses real history.

======================================================================
HARD CONSTRAINTS
======================================================================

1. **BUDGET: $20 hard cap for the whole campaign** (edit this number
   before pasting if you want a different cap). Track cumulative spend
   after every stage against the DB's cost records, not your own
   arithmetic. Stop and report if a stage would exceed the remaining
   budget. Prefer haiku wherever it discriminates; use sonnet-class only
   where haiku floors.
2. **Frozen golden tasks change only with an explicit human OK.** Prefer
   NON-INVASIVE calibration first: scoping a floored task to a stronger
   model changes nothing frozen. Only propose gate/task edits if the
   stronger model also floors (or saturates), and then STOP and present
   the proposal — options, evidence, expected effect — before touching
   anything.
3. **The human is the gold standard grader. You never grade.** You prepare
   the cells and stop; the human runs the blind sessions in the UI. Also:
   present the purge-or-keep decision for the Claude-made judgments in
   session `c38ed547…` at the first checkpoint (default recommendation:
   purge, for a pure human gold standard — it's cheap to re-grade).
4. Full `pytest` stays green (305 fast + 18 integration as of handoff).
   You're running the pipeline, not changing it — if a sweep exposes an
   engine bug, fix it with a test, but no feature work, no UI work.
5. Every trial run is resumable (`cli.py run` dedups by trial id); use
   `--delay` if you brush rate limits. Log every stage, spend, and
   decision in `docs/measurement-log.md` (create it; same style as
   `docs/ui-revamp-log.md`).

======================================================================
PLAN (checkpoint = STOP, report, wait for human)
======================================================================

**Stage 0 — Preflight (cheap, no spend).** `python cli.py doctor` green;
fast suite green; confirm the real DB's current trial/judgment counts and
reproduce the pass-rate numbers above from `results.db` itself. Report any
drift.

**Stage 1 — Calibration analysis → CHECKPOINT 1.** For cosmos-A and
moreiter-A, propose the cheapest path to discrimination: first a small
probe (2–3 reps, baseline methodology only) at claude-sonnet-4-6 to test
whether the floor is model-strength (estimate cost from history/pricing
before running; this probe IS allowed spend). Present at the checkpoint:
probe results, per-task recommendation (scope-to-model vs gate change vs
drop-from-campaign), the purge-or-keep call on the Claude judgments, and
the exact Stage-2 sweep grid with its cost estimate. Wait for OK.

**Stage 2 — The sweep (the approved grid only).** Core target: the
methodology axis — all five methodologies (baseline, karpathy,
superpowers, ecc, custom) × 3 reps on every task×model cell approved in
Checkpoint 1 (cosmos-B × haiku is the anchor: ~15 trials ≈ $1.65).
Secondary, budget permitting and pre-approved: one model-axis cell
(haiku vs sonnet on cosmos-B × baseline). Run in stages, verify gate
results and costs land in the DB after each, watch the analyzer flags.

**Stage 3 — Grading prep → CHECKPOINT 2 (the human grades).** List every
gradeable cell with its axis, pinned values, contender count, and pair
count (the picker shows this). Write the human a short grading brief:
which cells, expected session lengths, keyboard flow reminder, and the
warning that revealing closes a session. STOP. Do not grade, do not
reveal.

**Stage 4 — Report & decision (after the human confirms grading is
done).** `python cli.py report` per graded axis; verify the UI report
agrees. Write `docs/decision-<date>.md`: the ranking with CIs, tier pass
rates, cost rollup, Pareto frontier, analyzer flags, the two stakes-based
picks (quality / budget) with the §6 rule applied, honest caveats (n, CI
overlap, task coverage), and what evidence would change the decision.
Update README "Next up" to the new reality. Final human-facing summary.

======================================================================
OPERATING MODE
======================================================================

Same as the UI-revamp sessions: autonomous between checkpoints; nobody
answers mid-stage questions — make reversible calls yourself and log
them. Ground every claim in a tool result (a DB query, a gate log, a CLI
output — never "should have"). The checkpoints above are the ONLY
legitimate stops: spend approval, frozen-task changes, and human grading
are genuinely yours-to-decide moments, everything else is not.
