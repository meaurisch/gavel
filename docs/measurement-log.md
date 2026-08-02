# Measurement campaign log — 2026-07-05

Running notes: one line per significant stage/spend/decision, what/why/how
verified. Branch: `ui-ux-revamp`. Mandate: `recalibration_prompts/29-M2`-style
campaign (Stage 0 preflight → Stage 1 calibration probe → CP1 → Stage 2 sweep
→ CP2 human grading → Stage 4 report/decision). Budget: **$20 hard cap** for
this campaign's new spend, tracked as `sum(cost_record.usd_equiv) − $11.7069`
(the pre-campaign DB total), never from hand arithmetic.

## Stage 0 — Preflight (2026-07-05, no spend)

- `python cli.py doctor` — all 15 checks OK (git, node, UI build, claude CLI
  2.1.201, dotnet 8.0.422, WSL venv, all 5 task bases, 3 vendor packs,
  pricing table 15 models).
- Fast suite: **305 passed, 19 deselected** (18 integration + 1 env-gated) —
  matches handoff exactly.
- `results.db` reproduces every inherited number:
  - 26 trials, all billed, **$11.7069 total** (handoff said $11.71 ✓).
  - cosmos-A: hidden **0/17** across baseline(×2 contexts)/custom/ecc/
    karpathy/superpowers at claude-haiku-4-5 ✓ (floor).
  - moreiter-A: hidden **0/3** (baseline × haiku) ✓ (floor).
  - cosmos-B: hidden **2/6** = 33% (1/3 baseline, 1/3 karpathy × haiku) ✓
    (in the 30–70% discrimination band). ~$0.109/trial ✓.
  - 2 judgments on the real cosmos-B methodology cell: `ff850172…`
    (choice=B, 2026-07-02, session `c38ed547…` — **made by Claude**, the
    purge candidate) and `fa275c44…` (choice=tie, 2026-07-03, session
    `28057019…`). A third session `b8c3f18f…` exists with 0 judgments
    (abandoned; harmless). No session revealed.
  - Trial exit statuses: 12 exit=0, 14 exit=1, 1 recorded error — consistent
    with the A2/A3 run report.
- Drift found: none.

## Stage 1 — Calibration probe (sonnet on the floored tasks)

- **Decision (probe size):** 2 reps per task (prompt allows 2–3) — chosen to
  protect Stage-2 budget. Grid: `cosmos-A,moreiter-A × baseline × none ×
  claude-sonnet-4-6 × 2 reps` = 4 trials.
- **Cost estimate before running** (from history × pricing.toml, not
  guesswork): sonnet-4-6 rates are exactly 3× haiku-4-5 on all three token
  components (3/15/0.3 vs 1/5/0.1 per Mtok), so at an identical token
  profile a sonnet trial ≈ 3× the haiku cost. cosmos-A baseline×none haiku
  averaged $0.545/trial → sonnet ≈ **$1.63/trial**; moreiter-A baseline
  averaged $0.382/trial → sonnet ≈ **$1.15/trial**. Probe estimate:
  2×1.63 + 2×1.15 ≈ **$5.6** (uncertainty: sonnet may spend more/fewer
  turns than haiku; treat ±50%). Remaining budget after probe ≈ $14.4.
- **Probe ran 2026-07-05/06, actual $5.8444** (DB-verified:
  `sum(usd_equiv) = 17.5513`, minus the $11.7069 pre-campaign baseline).
  Estimate error +4%. **Remaining budget: $14.16.**
- **Probe results (all four trials landed in DB with full gate records):**
  - `moreiter-A × baseline × sonnet`: **2/2 hidden PASS** ($1.04 + $1.18).
    → the moreiter-A floor was model strength. Scope to sonnet. (Ceiling
    risk: 2/2 could mean >70% at sonnet; the Stage-2 sweep will measure.)
  - `cosmos-A × baseline × sonnet`: **0/2 hidden** ($2.20 + $1.42) — but
    BOTH failed identically: compile+visible pass, then the **held-out
    oracle test itself fails to compile** against the agent's solution:
    `AuditMapperTest.cs` requires `AuditDocument.DateCreatedUtc` (the gold
    patch's private casing; reference.diff even maps it with
    `[JsonProperty("DateCreatedUTC")]`), while agents naturally mirror the
    domain entity's `DateCreatedUTC`. The instruction names `Etag`, `Type`
    and `id` for the documents but never the date property.
- **Root-cause sweep over ALL cosmos-A trials that reached the hidden tier**
  (10 of 19: 8 haiku + 2 sonnet): **9 of 10** show the exact
  `DateCreatedUtc` CS0117/CS1061 signature (the 10th, `custom` at haiku,
  fails on a genuine namespace miss, CS0234). This is the task-design
  guide's "un-guessable identifier" anti-pattern, not a capability floor.
  Two of the nine additionally show CS0200 (agent mirrored `IsCompleted`'s
  private setter onto the document — a defensible test demand, counted as a
  genuine failure).
- **Free local counterfactual experiment** (`scripts/simulate_cosmosA_namefix.py`,
  zero spend, no frozen file touched): for each of the 10 hidden-tier
  trials — scratch worktree at base, agent diff applied, oracle copied in,
  the single `DateCreatedUtc` token renamed to the agent's actual document
  property name, hidden run_cmd executed. (Two infra lessons en route:
  worktree paths must be short — Windows MAX_PATH — and patches must be
  written in binary mode or Python CRLF-ifies them.)
- **Counterfactual results** (= what the hidden gate would say if the agent
  had known the required property name):
  - sonnet baseline: **2/2 PASS** — cosmos-A has NO capability floor at
    sonnet; the 0/2 probe result was entirely the naming trap.
  - haiku hidden-tier reachers: **4/8 PASS** (baseline×cosmos rep0,
    baseline×none rep0, ecc rep2, superpowers rep0). Overall haiku
    counterfactual pass rate: **4/17 ≈ 24%** — just below the 30–70% band,
    with per-methodology spread (baseline/ecc/superpowers ≈ 33%,
    karpathy 0% — never compiled, custom 0%).
  - The 4 remaining hidden-tier failures are genuine: one agent diff was
    empty (custom), one never defined a date property at all, and two made
    `Type` get-only (`public string Type => "audit"`) which the oracle's
    object-initializer rejects (CS0200) — a defensible-but-rejected design;
    noted honestly, no change proposed (the `Type` field IS named in the
    instruction, unlike the date).
- **CHECKPOINT 1 presented 2026-07-06. STOPPED — awaiting human OK.**
  Summary of what was asked (full detail in the session):
  1. cosmos-A: amend instruction (one line naming `DateCreatedUtc` on
     `AuditDocument`, style-consistent with the already-named `Etag`/
     `Type`/`id`) — frozen-task change, needs explicit OK; plus backup
     results.db and delete the 19 stale cosmos-A trial rows (dedup would
     otherwise silently skip re-runs under the amended instruction);
     re-sweep deferred to a future campaign (budget).
  2. moreiter-A: scope to claude-sonnet-4-6 (non-invasive, no frozen
     change). Ceiling risk (2/2 at baseline) acknowledged; sweep measures.
  3. cosmos-B: unchanged, anchor cell as-is at haiku.
  4. Claude-made judgment `ff850172…` (session `c38ed547…`): recommend
     PURGE (delete judgment row + its now-empty session; optionally the
     abandoned empty session `b8c3f18f…` too) for a pure human gold
     standard.
  5. Proposed Stage-2 grid (remaining budget $14.16):
     a. cosmos-B × all-5 × none × haiku × 3 reps → 9 new ≈ $1.4
     b. moreiter-A × all-5 × none × sonnet × 2 reps → 8 new ≈ $10.7
        (range $9–12; per-methodology cost multipliers from cosmos-A
        history: custom ≈ 1.9× baseline, ecc 1.1×, superpowers 1.05×,
        karpathy 0.7×)
     c. budget permitting after a+b (≥$1.5 headroom): cosmos-B × baseline
        × sonnet × 3 reps → 3 new ≈ $1.0 (model-axis cell)
     Projected campaign total ≈ $18.9 of $20; spend re-checked against the
     DB between sub-stages, c dropped if tight.

## Checkpoint 1 decisions (human, 2026-07-06)

**1a approved, purge approved, Stage-2 a+b+c approved** (via structured
checkpoint questions; recommendations accepted unchanged).

Applied immediately after approval:

- **Backup**: `backups/results-2026-07-06-pre-cp1.db` (1,380,352 bytes) —
  full pre-purge DB, kept out of the project root so the UI's DB switcher
  doesn't list it.
- **Stale-row purge**: all 19 cosmos-A trials + their gate/run/cost rows
  deleted (they measured the pre-amendment instruction; trial-id dedup
  would otherwise silently skip re-runs). Claude-made judgment
  `ff850172…` deleted; its session `c38ed547…` and the abandoned empty
  session `b8c3f18f…` deleted. Post-state: 11 trials, 1 judgment
  (the human tie), 1 session.
- **Budget bookkeeping correction**: the purge removed $11.51 of *recorded*
  cost, so `sum(usd_equiv) − 11.7069` no longer works. Real campaign spend
  so far is unchanged at **$5.8444**; from here, campaign spend =
  5.8444 + (`sum(cost_record.usd_equiv)` − **4.0247**), the post-purge DB
  baseline.
- **Frozen-task amendment (human-OK'd)**: `tasks/cosmos-A/task.yaml`
  instruction gains one sentence — "`AuditDocument` exposes the audit
  timestamp as `DateCreatedUtc`." — style-consistent with the already-named
  `Etag`/`Type`/`id`. `validate_tasks.py --lint`: all tasks OK (moreiter-A
  length WARN pre-existing). cosmos-A re-sweep deferred to a future
  campaign.

## Stage 2 — The approved sweep

- **2a launched** (cosmos-B × all 5 × none × haiku × 3 reps; 6 of 15 ids
  exist → 9 new; est ≈ $1.4). Fast pytest re-run in parallel as a sanity
  check after the task.yaml edit (305 passed).
- **2a result: 0/9 hidden passes, actual $3.66** (vs $1.4 estimate — the
  `custom` pack cost $2.55 for its 3 trials, ~8× baseline per trial, one of
  them a compile failure). Campaign spend **$9.50**, remaining **$10.50**.
  Per the budget constraint this alone forces a stop before 2b
  (est $10.7 ≥ remaining).
- **Root cause of the 2a wipe-out — cosmos-B has its own oracle-shape
  defect, same family as cosmos-A:** `CompleteHandlerTest`/
  `ReopenHandlerTest` construct `new …CommandHandler(repo)` — one argument —
  while the instruction says "built like the existing Create / Delete
  slices" and BOTH base slices inject `(IToDoItemRepository, IMapper)`
  (even Delete, which maps nothing, with an ArgumentNullException guard).
  Agents that follow the stated convention fail oracle compilation with
  CS7036. **12 of 13 hidden-tier failures on cosmos-B (old + new trials)
  carry exactly this signature**; the 13th is a genuine compile failure
  (custom rep2). The two historical "passers" (baseline rep1,
  karpathy rep0) are the agents that *deviated* from the stated
  convention — the 33% "discriminative" pass rate was substantially
  measuring an arbitrary constructor-style choice. The task's OWN
  spec-comment promises "the public contract is well specified" — the
  handler ctor shape is not part of that contract.
- **Proposed fix (frozen-task change — requires human OK, nothing touched
  yet):** tolerant construction in the two handler tests via a small
  `TestDoubles/HandlerFactory.cs` (reflection over the handler's public
  ctor: repository → the test double, `IMapper` → a real
  `MapperConfiguration` exactly as the existing `SearchHandlerTest.
  BuildMapper()` does, `ILogger<T>` → `NullLogger<T>`). All behavioural
  assertions unchanged (repo state, `EntityNotFoundException`); FAIL_TO_PASS
  on base preserved (the `Complete`/`Reopen` types don't exist → compile
  fail). Proposal drafted in scratchpad, counterfactual running: every
  compile-passing cosmos-B trial re-gated under the tolerant tests, plus
  GOLD (reference.diff must PASS) and BASE (must FAIL).
- No cosmos-B agent diff touches a held-out `CosmosB/` path (SQL-checked),
  so the 15 stored trials can be **re-gated in place for free** via the
  real `grading.gate.apply` against reconstructed worktrees if the fix is
  approved — no API re-spend needed to restore the anchor cell.
- **Counterfactual verdict (tolerant handler tests): ALL 14 compile-passing
  trials PASS, each 20/20 xunit; GOLD passes; BASE fails compile
  (FAIL_TO_PASS preserved).** Post-fix cosmos-B × haiku hidden pass rate:
  **14/15 ≈ 93%** (only custom rep2's genuine compile failure remains).
  Honest consequences: (a) the pre-fix "33%, in the discrimination band"
  was an artifact of the ctor trap — post-fix the gate SATURATES at haiku
  (ceiling, >70%), so cosmos-B's gate carries little methodology signal;
  (b) the cell becomes excellent *grading* material — 5 methodologies with
  14 hidden-gate passers → many cross-value blind pairs, and would-I-merge
  judgment is the tool's primary metric anyway. The analyzer's
  non-discriminating flag will (correctly) fire; goes in the report
  caveats.
- **CHECKPOINT 1.5 (unscheduled) presented — STOPPED for human OK:**
  cosmos-B test fix, in-place re-gate of the 15 stored trials, and a
  revised budget plan for the remainder of Stage 2 ($10.50 left).

## Checkpoint 1.5 decisions (human, 2026-07-06)

- **Test fix APPROVED** — applied to the frozen held-out suite:
  `TestDoubles/HandlerFactory.cs` added; `CompleteHandlerTest`/
  `ReopenHandlerTest` construct via the factory. `validate_tasks.py
  --lint`: all OK.
- **Re-gate REJECTED — human chose fresh re-runs** (~$4.3 est): stored
  diffs are NOT re-gated; the 15 cosmos-B trials re-execute with live
  agents under the fixed oracle.
- Consequence (logged, follows necessarily from re-run): trial ids are
  deterministic, so the old 15 cosmos-B rows had to be deleted first
  (backup `backups/results-2026-07-06-pre-cosmosB-rerun.db`), **including
  the human's tie judgment + session `28057019…`** — it referenced trial
  ids whose diffs are being regenerated; keeping it would attach the
  verdict to content the human never saw. DB now: 5 trials (probe +
  moreiter baselines), 0 judgments, 0 sessions. Every judged pair will be
  freshly human-graded (a pure gold standard, per the CP1 purge decision).
- Spend-tracking re-base #2: campaign spend so far **$9.5037** (real,
  unchanged by deletions); from here = 9.5037 + (`sum(usd_equiv)` −
  **3.3679**).
- **Remainder plan APPROVED (trimmed 2b + model cell):** after the
  cosmos-B re-run — moreiter-A × sonnet × karpathy+ecc+superpowers ×
  2 reps, run cheapest-first per methodology with a spend check between
  each; then cosmos-B × baseline × sonnet × 3 reps if headroom; `custom`
  deferred to a future campaign alongside the cosmos-A re-sweep.
- cosmos-B re-run launched (15 trials, haiku, fixed oracle).
- **cosmos-B re-run done: 15/15 hidden PASS, $4.11** (per-methodology
  $/trial: karpathy 0.105, baseline 0.117, superpowers 0.144, ecc 0.156,
  custom 0.849). The counterfactual's 14/15 prediction held direction-wise;
  fresh runs even cleared custom's old compile failure. The anchor cell is
  now **5 methodologies × 3 passers = 15 contenders** — maximal grading
  material; the hidden gate itself saturates at haiku (100% — ceiling flag
  expected from the analyzer, honest caveat for the report; discrimination
  on cosmos-B now comes from human grading, not the gate).
- Campaign spend **$13.6165**, remaining **$6.3835**.
- 2b slices (sonnet estimates = moreiter baseline $1.11/trial × cosmos-B
  methodology multipliers): karpathy ≈ $1.00/trial, superpowers ≈ $1.37,
  ecc ≈ $1.48. Reserving ~$1.4 for the model cell → run karpathy ×2
  (~$2.0), check; superpowers ×2 (~$2.7), check; ecc only if it still
  fits (unlikely). karpathy slice launched.
- **2b slice results:** karpathy 2/2 hidden PASS ($2.00, on estimate);
  superpowers 2/2 hidden PASS ($2.30). moreiter-A × sonnet cell now
  6/6 across baseline/karpathy/superpowers — **saturated too**. ecc slice
  dropped (est ~$3.0 > $2.08 remaining). Campaign spend **$17.9161**.
- Emerging pattern worth naming for the report: with the two oracle-shape
  defects fixed, BOTH swept cells saturate their hidden gates (cosmos-B ×
  haiku 15/15, moreiter-A × sonnet 6/6). At these task difficulties the
  gate is a floor-check, not a discriminator — the instrument's
  discrimination now lives entirely in blind pairwise grading, which is
  what the tool was built around anyway. The analyzer's ceiling flags
  should fire on both cells; report must say so plainly.
- **2c launched:** cosmos-B × baseline × sonnet × 3 reps (model-axis cell,
  est ~$1.05).
- **2c done: 3/3 hidden PASS, $1.15.** Stage 2 closed. Campaign spend
  **$19.0655 of $20** ($0.93 headroom; every estimate checked against the
  DB, cap never crossed).

## Stage 3 — Grading prep (2026-07-06, no spend)

- Gradeable cells enumerated with the server's own `list_grading_cells`
  (not hand-derived): methodology × (cosmos-B·none·haiku·claude-code,
  n_values=5) and × (moreiter-A·none·sonnet·claude-code, n_values=3);
  model × (cosmos-B·baseline·none·claude-code, n_values=2). No
  repo-context or runner cells (expected — neither axis was varied).
- Pair counts from `generate_pairs`' default (C(M,2)×3): **30 + 9 + 3 =
  42 blind pairs**.
- `calibrate_tasks.py`: cosmos-B 100% (18/18) ceiling-flagged;
  moreiter-A 67% overall (an aggregation across models — per cell it is
  0/3 at haiku and 6/6 at sonnet, i.e. floor and ceiling respectively;
  the 67% "medium" band is an artifact of pooling, noted for the report).
- Grading brief written: `docs/grading-brief-2026-07-06.md` (cells, pair
  counts, session-length estimates, keyboard flow, the
  reveal-closes-permanently warning, BT ≥3 note).
- **CHECKPOINT 2: STOPPED. The human grades blind in the UI. No grading,
  no reveal by Claude.**

## E2.1 — consistency probes, built before CP2 (2026-08-01, no spend)

- **Human decision:** the elevation brief's Part-2 timing question ("build
  E2.1 before grading?") was answered **yes** on 2026-08-01 — the CP2
  session is the only human gold standard being produced, and the LLM
  judge's promotion rule (E3.4) needs the human's self-agreement as its
  yardstick.
- Implementation (branch `e21-consistency-probes`, merged into
  `llm-judge`): human sessions insert ~10% (min 2) side-swapped repeat
  pairs at random later positions; blind surfaces never mark them
  (Playwright-asserted); probe verdicts are excluded from Bradley-Terry
  and yield self-agreement + side-swap flip rate at reveal and in every
  report surface. Additive schema (`grading_session.probe_of`,
  `judgment.is_probe`); LLM-judge sessions unchanged.
- **Consequence for CP2:** the three sessions will serve
  33 + 11 + 5 = **49 pairs (42 real + 7 probes)**. The grading brief
  gained an addendum; expect ~15% more grading time.
- Suites: 462 fast + 24 Playwright green. Spend: $0.

## Blinding leak — committed planning folder (2026-08-02, no spend)

- **Found by the human mid-CP2.** One methodology's runs commit a
  root-level planning/progress folder. The instruction-file stripper never
  covered it (it is not laid down by a pack, so the leakage scanner never
  saw it either), so its mere presence in a served diff identified the
  varying axis value on sight — a live blinding leak on the manual
  double-blind surface.
- **Aggregate exposure (no axis values recorded here, CP2 is still open):**
  **3 of 27** stored diffs carry the folder. All three sit in **cell 1**;
  cells 2 and 3 have **0** affected trials and **0** affected pairs.
- **Cell 1 sessions.** Two open (unrevealed) human sessions exist on cell 1,
  both 33 pairs — the first carries **5 judgments**, of which **2** were
  served a diff containing the folder; the second (created after the last
  judgment) has **0 judgments**. Cell-1 pair exposure: 13 of 33 pairs in the
  first session, 15 of 33 in the second, involve at least one affected trial.
- **Fix (serve-side, this branch).** `.agent-plans/` joins
  `grading.pairwise.METHODOLOGY_DIR_PREFIXES`, so the one stripper that
  governs served diffs, the diff-shape proxy (computed on the anonymized
  diff) and the reconstructed-originals endpoint drops it at any depth.
  Recorded and future runs are both covered; the vendored packs and the
  runner's diff capture are untouched (packs are frozen at pinned commits —
  changing them is an instrument change needing an explicit human OK).
  TDD: unit test on `anonymize_diff`, an API test across diff + proxy +
  originals, and the Playwright fixture now commits such a folder in every
  seeded diff while the file navigator must still show exactly 2 files.
- **Flagged follow-up (not done):** a capture-side option — have the runner
  gitignore the folder so it never enters a stored diff. That changes the
  instrument for future runs and would make stored diffs differ from what
  the agent actually produced; serve-side stripping is strictly safer and
  already sufficient.
- **OPEN — human decision pending** on the 2 already-judged affected pairs:
  (a) back up `results.db` and purge, or (b) keep and log the caveat. Not
  taken by Claude. Unjudged pairs are clean as of this fix.
- Suites: 464 fast + 24 Playwright green. Spend: $0.
