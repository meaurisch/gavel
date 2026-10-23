# 24 — A2 completion: ecc, karpathy, superpowers real reps

**Service:** Claude Code runs fully autonomously — no manual action during the
run. Grant permission once by launching in an autonomous permission mode
(e.g. `--dangerously-skip-permissions` / accept-edits / bypass-permissions).

**Start this in a fresh Pro-plan usage window.** Don't paste this back-to-back
with another session in the same ~5-hour window — see the "why 3 more
sessions" note below.

**Context:** `23-A2-A3-real-run.md` (run 2026-07-01) ran A2 for real and found
two real bugs, both now fixed and committed:
- `9b76a05` — subprocess text-capture on Windows defaulted to the cp1252
  locale codepage instead of UTF-8, crashing on any Claude/git output
  containing bytes outside cp1252's range.
- `6fc8e52` + `980f0e8` — a trial where `claude` failed before doing any real
  work (unparseable stdout, OR a valid-but-zero-token JSON envelope) used to
  get persisted as a normal completed trial, permanently burning that trial
  ID so it could never be retried. Fixed: such attempts now raise instead of
  persisting, so `cli.py run`'s existing dedup (`trial_exists`) naturally
  retries them on the next invocation. **This is expected, working behavior
  now — do not re-diagnose it as a bug if you see it again.**

That same session also discovered the actual blocker wasn't rate-limiting —
it's an **account-level Claude usage-window cap**. Evidence: real trials ran
fine early in the session (baseline succeeded 5/6 times, one `custom` trial
even completed at $2.93 / 570K tokens), then every subsequent attempt died
in 2.5–5 seconds with exactly 0 tokens billed — a shape consistent with the
account's usage window being exhausted, not per-request throttling. `--delay`
between trials does not fix this; only time (a fresh usage window) does. This
is why the remaining work is split across separate sessions rather than one
long run.

**Current real-data state in `results.db`** (task=cosmos-A, repo_context=none,
model=claude-haiku-4-5, runner=claude-code) — verify with the queries in
STEP 1 rather than trusting this table blindly, but this is what it was as of
the end of session 23:

| methodology | real reps (non-dead) | rep indices used (0-5, dead ones included) |
|---|---|---|
| baseline | 5 of 6 | 0,1,3,4,5 real; 2 dead |
| custom | 1 of 6 | 3 real; 0,1,2,4,5 dead |
| ecc | 0 of 6 | all 6 dead |
| karpathy | 0 of 6 | all 6 dead |
| superpowers | 0 of 6 | all 6 dead |

`baseline` already has more than enough real reps — **do not touch baseline
in this session.** `custom` is handled in its own session (`25-A2-custom.md`)
because of its demonstrated cost/token unpredictability — **do not touch
custom in this session either.** This session is scoped to the three cheap
methodologies only: `ecc`, `karpathy`, `superpowers`.

Because reps 0-5 already exist (as dead rows) for these three, you must use
`--reps 9` to reach fresh rep indices 6, 7, 8 — lower rep counts will just
skip everything as "already exists."

**Lay-down correctness already spot-checked for karpathy** (session 23,
kept-worktree inspection): repo-context commit for `none` is empty, the
methodology commit adds exactly `CLAUDE.md` matching `methodologies/karpathy/
manifest.yaml`, and the graded diff (vs. baseline ref) contains only the
agent's own work. You do not need to re-verify karpathy. Spot-check `ecc` and
`superpowers` the same way (persisted diff inspection is enough, no need for
a fresh worktree unless something looks wrong).

---

Paste the block below into a **fresh** Claude Code session, launched in an
autonomous permission mode, in a fresh Pro-plan usage window.

---

```
You are the CONDUCTOR for this session and you run FULLY AUTONOMOUSLY. Make
every decision yourself and run to completion — there is no cost-ceiling
checkpoint in this session (see why below). You MAY run cli.py directly on
the main thread, but implement NO code fixes on the main thread — dispatch a
studio-executor subagent for any bug fix, TDD, one at a time.

BACKGROUND (verified 2026-07-01 in session 23, do not re-derive — read
recalibration_prompts/24-A2-cheap-methodologies.md's context section first
for the full picture):
- Two real bugs already fixed and committed (9b76a05, 6fc8e52, 980f0e8): a
  Windows subprocess encoding crash, and a bug where a claude-CLI-failed
  trial (zero tokens billed) used to get persisted permanently instead of
  staying retryable. Both are done — do not re-diagnose either pattern.
- The actual blocker in session 23 was an account-level Claude usage-window
  cap, not rate-limiting. A trial that dies in 2-5 seconds with 0 tokens
  billed is now cleanly retryable (no wasted trial ID, no cost) — if this
  happens repeatedly and consistently across every new attempt, it likely
  means the usage window is already exhausted for this session too. If you
  see 3+ consecutive zero-token instant failures across different
  methodologies, STOP attempting new trials (don't keep bumping --reps
  looking for a gap), and report the honest partial state instead of
  looping. Do not treat this as a code bug to fix.
- scripts/check_grading_ready.py --db results.db defines "gradeable": a
  methodology-axis cell needs >=2 DISTINCT methodology values that EACH have
  at least one HIDDEN-GATE-PASSING trial, with repo_context/model/runner
  held fixed. As of session 23, 0 of 6 real claude-code haiku trials on
  cosmos-A have passed the hidden gate (all FAIL) — only the reference
  oracle runner passes. More reps increase the number of independent shots
  at a gate pass, but there's a real chance this task's gate is simply
  miscalibrated for haiku regardless of methodology. That's fine — axis
  coverage (this session's job) is still the correct, valuable thing to do;
  whether it also produces a pass is not something you control or should try
  to force.

STEP 0 — CLEAN THE TREE:
- `git status --porcelain`. If any TRACKED files are modified/staged, commit
  them as ONE isolated "session: checkpoint wip" commit first. Leave
  untracked scratch alone. Confirm a clean tracked tree before proceeding.

STEP 1 — CONFIRM CURRENT STATE (don't trust the table in the prompt doc
blindly):
`.venv\Scripts\python.exe -c "import sqlite3; conn=sqlite3.connect('results.db'); conn.row_factory=sqlite3.Row; [print(dict(r)) for r in conn.execute('''SELECT t.methodology_id, t.rep, r.exit_status, c.input_tokens, c.output_tokens FROM trial t LEFT JOIN run_result r ON r.trial_id=t.id LEFT JOIN cost_record c ON c.trial_id=t.id WHERE t.task_id=\"cosmos-A\" AND t.repo_context_id=\"none\" AND t.model=\"claude-haiku-4-5\" AND t.runner=\"claude-code\" AND t.methodology_id IN (\"ecc\",\"karpathy\",\"superpowers\") ORDER BY t.methodology_id, t.rep''')]"`
Adjust the --reps target in STEP 2 if the real/dead split differs from what's
documented (e.g. if a prior partial session already added real reps 6-8 for
one of these).

STEP 2 — REAL RUNS (cheap methodologies, one at a time, cheapest evidence
first — ecc, then karpathy, then superpowers):
1. `.venv\Scripts\python.exe cli.py run --task cosmos-A --methodology ecc
   --repo-context none --model claude-haiku-4-5 --runner claude-code --reps 9`
2. `.venv\Scripts\python.exe cli.py run --task cosmos-A --methodology
   karpathy --repo-context none --model claude-haiku-4-5 --runner claude-code
   --reps 9`
3. `.venv\Scripts\python.exe cli.py run --task cosmos-A --methodology
   superpowers --repo-context none --model claude-haiku-4-5 --runner
   claude-code --reps 9`
- After each, if you see 3 consecutive zero-token instant fails, stop running
  further methodologies in this session (the usage window is exhausted) —
  report exactly what got real data and what didn't, don't force it.

STEP 3 — LAY-DOWN SPOT-CHECK:
- For one new real trial each of ecc and superpowers (karpathy already
  verified in session 23), inspect `run_result.diff` in results.db and
  confirm nothing looks wrong (methodology's manifest.yaml files are what
  would've been laid down — you don't need a fresh worktree to sanity-check
  this, the diff itself + a `git show`-equivalent read of the manifest is
  enough unless something looks actually broken).
- If you find a REAL bug (wrong files, wrong lay-down order, crash) — not an
  expected hidden-gate FAIL or the already-known zero-token usage-window
  pattern — dispatch ONE studio-executor (model=sonnet) with a self-contained
  TDD brief. Cap at ONE fix attempt per distinct bug; if still broken after
  that, mark it a known issue in your final report and move on — do not loop.

STEP 4 — FINAL REPORT:
- For each of ecc/karpathy/superpowers: real rep count achieved (out of 3
  target), any bug found/fixed (commit SHA), actual $ spent (query
  cost_record for trial ids created this session).
- Total $ spent this session.
- Whether you stopped early due to the usage-window pattern, and at which
  methodology.
- Do NOT touch custom or A3 in this session — those are 25-A2-custom.md and
  26-A3-and-wrapup.md. Do NOT run check_grading_ready.py's docs
  reconciliation step yet — that's the last thing 26 does, once all axis
  data is in. Stop after the report.
```
