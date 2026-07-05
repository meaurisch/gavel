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
