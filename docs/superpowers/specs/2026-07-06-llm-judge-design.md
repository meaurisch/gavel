# LLM-as-Judge grading mode — design

Date: 2026-07-06 · Branch: `llm-judge` · Status: approved for implementation
(autonomous session; decisions recorded here in lieu of interactive review)

## Goal

Add a **second grading mode** to gavel: instead of the user judging blind A/B
pairs by hand, an LLM judge grades every pair of a session automatically. The
two modes are separate and clearly labeled everywhere; the human double-blind
flow is untouched. The judge must be cost-efficient, work with the user's
**Claude subscription** (no API key required), and be extensible to a
**GitHub (enterprise) subscription** (GitHub Models / Copilot). Everything is
testable at zero spend via a deterministic mock provider.

### Branch-point note

The goal said "branch of current main", but `main` is a strict ancestor of
`ui-ux-revamp` (no divergence, fast-forwardable) and the entire web UI this
feature integrates with exists only on `ui-ux-revamp`. Branching from `main`
would rebuild the feature against a UI that no longer exists. `llm-judge`
therefore branches from `ui-ux-revamp`'s tip, which *contains* current main.

## Research grounding (2026 best practices)

- **Position bias** is the dominant pairwise-judge failure: judges favor slot
  A or B regardless of content. Mitigation: judge each pair **twice with
  sides swapped**; agreement → verdict, disagreement → recorded as a **tie**
  with `position_consistent = false`. This doubles cost, so it's a session
  option (default ON; single-pass available for cheap sweeps).
- **Rubric-anchored prompting** beats bare "which is better": we reuse gavel's
  existing four rubric dimensions (correctness, minimality, readability,
  over-engineering) in one structured prompt, one call per ordering —
  not one call per dimension (4× cost for marginal gain).
- **Reasoning before verdict**, strict JSON output, and a **self-correction
  retry loop** (re-ask with the validation error appended, max 2 retries).
- **Verbosity / self-preference bias** can't be fully eliminated (candidates
  and judge may share a vendor); we mitigate by keeping the diff-shape proxy
  out of the prompt's framing, reporting **human↔LLM agreement** whenever both
  modes graded the same pairs, and surfacing the position-consistency rate as
  a per-session reliability signal.
- **Human and LLM judgments are never silently mixed**: every judgment row
  carries a `grader`, reports can filter by grader, and mixed reports say so.

## Architecture

```
GradePicker ──"Judge myself"──► existing human session flow (unchanged)
     │
     └──"LLM judge"──► config (provider, model, passes) ─► typed confirm
                                │
                                ▼
             POST /api/judge-sessions  (creates grading_session mode='llm')
                                │        background thread (ui/judge_runs.py)
                                ▼
       grading/judge.py: for each pair → build prompt from the SAME
       anonymized payload a human sees → provider call(s) → parse JSON
       verdict (retry loop) → upsert_judgment(grader='llm', rationale…)
       + judge_call usage rows                │ SSE progress
                                ▼
              done → Reveal (same endpoint/flow; rationale + judge cost
              shown only after reveal) → Bradley-Terry as today
```

### Components

1. **`grading/judge_providers.py`** — provider abstraction.
   - `JudgeProvider` protocol: `complete(prompt) -> ProviderResult(text,
     input_tokens, output_tokens, usd_equiv|None, wall_seconds)` plus
     `availability() -> (ok, reason)` and metadata (`id`, `label`,
     `billing` = `subscription | metered | free`).
   - **`claude-cli`** (default): `claude -p --output-format json --model <m>`
     with the prompt on **stdin** (same Windows-shim rationale as the
     runner), `--max-turns 1`, run in an **empty scratch dir** so the judge
     cannot read the repo. Usage parsed with the existing
     `cost/claude_usage.parse_claude_output`; works with whatever auth the
     user's CLI has — subscription login needs no API key.
   - **`gh-models`**: GitHub Models REST (OpenAI-compatible
     `POST https://models.github.ai/inference/chat/completions`), token from
     `GITHUB_TOKEN`/`GH_TOKEN` or `gh auth token`. Free tier works with any
     GitHub account; orgs/enterprises can enable paid tier — same code path.
     This is the "extensible to GitHub (enterprise) subscription" leg.
   - **`mock`**: deterministic verdict from a hash of the pair's diffs;
     zero network, zero spend. Powers unit tests, Playwright, and demo-DB
     exercises. Labeled clearly in the UI.
2. **`grading/judge.py`** — orchestration: prompt construction, the
   swap-pass protocol, JSON parsing + retry, verdict merging, diff budget
   (per-side char cap, default 60 000; oversized files truncated tail-first
   with an explicit `[truncated]` marker recorded in the judgment), and
   pure functions for the agreement analysis (per-pair agreement rate +
   Cohen's kappa between graders).
3. **`ui/judge_runs.py`** — background job manager modeled on `ui/runs.py`
   (handle + events list + SSE, one active judge run at a time, cancel
   after current pair, resumable: pairs that already have a judgment are
   skipped, so a crashed/cancelled session can be re-launched).
4. **Schema** (all via the existing `_ensure_column` backfill pattern —
   old DBs keep working; their rows read as human-mode):
   - `grading_session` += `mode TEXT DEFAULT 'human'`, `judge_provider`,
     `judge_model`, `judge_passes INTEGER`.
   - `judgment` += `grader TEXT DEFAULT 'human'` (`human` or
     `llm:<provider>:<model>`), `rationale TEXT`, `confidence REAL`,
     `position_consistent INTEGER`.
   - new `judge_call` table: per-call usage audit (session, pair, ordering,
     tokens, usd_equiv, wall time, status/error).
5. **Server endpoints**
   - `GET  /api/judge/providers` — availability + models + billing class.
   - `POST /api/judge/plan` — call count (pairs × passes), token/cost
     estimate, confirm requirements. Never executes.
   - `POST /api/judge-sessions` — create + start (typed `JUDGE` confirm for
     any non-mock provider — subscription quota and metered tokens are both
     real spend; mirrors the run launcher's SPEND philosophy).
   - `GET /api/judge-sessions/{id}` snapshot, `…/events` SSE,
     `…/cancel`.
   - Reveal reuses `GET|POST /api/reveal`; the payload gains
     `rationales`/`judge_stats` **only for revealed llm sessions**.
   - `/api/report` gains `grader=all|human|llm` (default `all`, backward
     compatible) and an `agreement` block when both modes covered the
     same cell.
6. **Frontend**
   - `GradePicker`: each gradeable cell row offers **Grade myself** and
     **LLM judge**; the latter opens an inline config panel (provider +
     availability, judge model, single/double pass, plan preview, typed
     confirm). Mode explanation copy up top.
   - New page `/grade/judge/:sessionId`: live progress (per-pair ticker,
     verdict letters only — axis values stay hidden), consistency counter,
     cancel, and a "Reveal results" call-to-action when done.
   - `Reveal`: for llm sessions adds per-pair judge rationale, the
     position-consistency rate, and the judge usage/cost card (post-reveal
     only — cost is never served during blind judging on any axis).
   - Dashboard/session lists: mode badge (Human / LLM·model).
   - `Report`: grader filter chips + human↔LLM agreement card.

### Blinding invariants (unchanged and extended)

- The judge consumes **exactly the payload a blind human sees**: anonymized
  diffs via `anonymize_diff` + `_axis_ids_for_blinding`, gate scorecard
  booleans, the task instruction. **Never** cost/tokens/wall-time, never
  raw axis ids, never gate logs (cheap + logs are noisy token sinks; the
  scorecard carries the tier verdicts).
- Verdicts/rationales are stored immediately but rationales and judge cost
  are **served only after reveal**; during a session the UI shows A/B/tie
  letters and progress only.
- Reveal still closes a session permanently; llm sessions obey the same
  rule (post-reveal judging attempts are refused server-side).

## Cost efficiency

- Default judge model: cheapest current Claude (haiku class) — judging a
  diff pair is a bounded, rubric-guided task well within a small model.
- Double-pass default = 2 calls/pair. A 9-pair session ≈ 18 calls, each
  roughly (2 × diff size + preamble) input + ~400 output tokens; the plan
  endpoint shows the arithmetic before anything runs.
- Static preamble (rubric + instruction) leads the prompt for provider-side
  prompt-cache reuse across pairs.
- One call carries all four rubric dimensions.
- Subscription (`claude-cli`) has zero marginal dollar cost; usage is still
  metered against the plan's quota, hence the typed confirm + estimate.
- `mock` provider gives the community a zero-spend way to see the whole flow
  (demo DB + Playwright use it).

## Alternatives considered

- **Anthropic API / Agent SDK instead of the CLI** — rejected as the
  default: requires an API key; the CLI inherits the user's existing
  subscription login and is already a hard dependency of the runner. The
  provider seam keeps an API provider addable later.
- **Pointwise scoring then ranking** — rejected: the whole pipeline is
  pairwise/Bradley-Terry-native; pointwise scores calibrate poorly across
  sessions and models.
- **Per-dimension judge calls** — rejected: 4× the cost for marginal gain.
- **Extending `ui/runs.py`** — rejected: trial runs and judge runs share a
  pattern but not state or spend semantics; a small parallel manager is
  clearer than one manager with two behaviors.

## Testing

- Unit (pytest, no network): prompt building (blinding asserted — axis ids
  must not appear), verdict parsing incl. malformed-JSON retry, swap-merge
  logic, diff budget, provider selection/availability, schema backfill,
  judge_call rollup, agreement/kappa math, report grader filter.
- Server (TestClient): judge-session lifecycle against the mock provider on
  a seeded DB; reveal enrichment; confirm-phrase enforcement; SSE events;
  resume-after-cancel.
- Playwright (`integration` marker): picker shows both modes; config +
  typed confirm; mock judge session runs to completion in-browser; progress
  page leaks no axis values (DOM scan, same technique as existing blinding
  tests); reveal shows rationales; report agreement card renders; existing
  18-test suite stays green.
- E2E on `results-demo.db` with the mock judge — zero spend.

## Out of scope

- Judging with the judge seeing full repo context (tool-using judge).
- Multi-judge ensembles (the provider seam + session config leave room).
- Copilot CLI as a judge provider (`copilot -p` exists but is stub-tier in
  this repo; gh-models covers the GitHub leg first).
- Auto-launching real paid sweeps from the judge flow.
