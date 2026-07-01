# 25 — A2 completion: custom methodology remaining reps

**Service:** Claude Code runs fully autonomously — no manual action during
the run. Grant permission once by launching in an autonomous permission mode.

**Start this in a fresh Pro-plan usage window**, separate from
`24-A2-cheap-methodologies.md`. This session is isolated on purpose — see
below.

**Context:** `23-A2-A3-real-run.md` (2026-07-01) got exactly one real
`custom` methodology trial: rep 3, which cost **$2.93** (456,846 input /
114,402 output tokens, 882 wall-seconds) — roughly **36x** the reference
baseline cost. `custom`'s manifest.yaml lays down a conductor + executor +
validator + reviewer sub-agent stack (`methodologies/custom/content-claude-code/
agents/`), so it plausibly spawns many Task-tool subagent turns per attempt,
each billing separately. Every other `custom` attempt that session (5 of 6)
died instantly at 0 tokens (account usage-window exhaustion, not a bug —
see `24-A2-cheap-methodologies.md`'s context section for the full
diagnosis and the two bug-fix commits, `6fc8e52`/`980f0e8`, that make these
failures cleanly retryable rather than permanently stuck).

**Why `custom` gets its own session:** one successful `custom` trial can
plausibly consume as much of a usage window as the rest of A2 combined. If it
ran alongside the cheap methodologies (session 24) or A3 (session 26), a
lucky/unlucky `custom` success could starve everything scheduled after it in
the same session — exactly what happened in session 23 (custom rep 3
succeeded first, then every subsequent trial that session died at 0 tokens).
Isolating it means a big `custom` success (or a run of instant failures)
only affects this one session's outcome, not the rest of A2/A3.

**Current state:** `custom` has 1 real rep (index 3) out of the target 3.
Rep indices 0,1,2,4,5 already exist as dead (zero-token) rows — use
`--reps 8` to reach fresh indices 6, 7 (2 more attempts, enough to reach 3
real reps if both succeed).

**There is no dollar cost-ceiling checkpoint in this session.** A failed
attempt costs $0 and the account usage-window is the real limiter — it
self-throttles. The only discipline needed is: don't keep bumping `--reps`
past 8 hunting for a gap if both attempts fail. Two attempts is the budget
for this session; report whatever you get.

---

Paste the block below into a **fresh** Claude Code session, launched in an
autonomous permission mode, in a fresh Pro-plan usage window.

---

```
You are the CONDUCTOR for this session and you run FULLY AUTONOMOUSLY. Make
every decision yourself and run to completion. You MAY run cli.py directly on
the main thread, but implement NO code fixes on the main thread — dispatch a
studio-executor subagent for any bug fix, TDD, one at a time.

BACKGROUND (verified 2026-07-01 in session 23, do not re-derive — read
recalibration_prompts/25-A2-custom.md's context section first):
- `custom` methodology already has 1 real rep (trial id
  cosmos-A_custom_none_claude-haiku-4-5_claude-code_3), which cost $2.93 for
  456,846 input / 114,402 output tokens — expect similar or higher cost per
  successful attempt in this session, it's not a fluke, `custom`'s manifest
  spawns a conductor/executor/validator/reviewer subagent stack.
- Two bugs already fixed and committed this repo (9b76a05, 6fc8e52,
  980f0e8): a Windows subprocess encoding crash, and a bug where a
  claude-CLI-failed trial (zero tokens billed) used to get persisted
  permanently instead of staying retryable. Both are done. A trial that dies
  in 2-5 seconds with 0 tokens billed is now cleanly retryable and free — do
  NOT treat it as a bug, it's the account usage-window being exhausted.

STEP 0 — CLEAN THE TREE:
- `git status --porcelain`. If any TRACKED files are modified/staged, commit
  them as ONE isolated "session: checkpoint wip" commit first. Confirm a
  clean tracked tree before proceeding.

STEP 1 — CONFIRM CURRENT STATE:
`.venv\Scripts\python.exe -c "import sqlite3; conn=sqlite3.connect('results.db'); conn.row_factory=sqlite3.Row; [print(dict(r)) for r in conn.execute('''SELECT t.rep, r.exit_status, c.input_tokens, c.output_tokens, c.usd_equiv FROM trial t LEFT JOIN run_result r ON r.trial_id=t.id LEFT JOIN cost_record c ON c.trial_id=t.id WHERE t.task_id=\"cosmos-A\" AND t.repo_context_id=\"none\" AND t.model=\"claude-haiku-4-5\" AND t.runner=\"claude-code\" AND t.methodology_id=\"custom\" ORDER BY t.rep''')]"`
Adjust the --reps target below if the real-rep count already differs from
"1 real (index 3), reps 0-5 all exist."

STEP 2 — REAL RUN:
`.venv\Scripts\python.exe cli.py run --task cosmos-A --methodology custom
--repo-context none --model claude-haiku-4-5 --runner claude-code --reps 8`
- This attempts fresh indices 6 and 7 (2 new attempts). If both die at 0
  tokens instantly, the usage window is exhausted for this session — do NOT
  bump --reps further, just report it.
- If one or both succeed, `custom` now has 2-3 real reps total across this
  and session 23 — good enough, don't chase a 3rd if 2 is what you get.

STEP 3 — BUG CHECK:
- If a real trial (nonzero tokens, real wall time) shows wrong lay-down
  (files not matching methodologies/custom/manifest.yaml's claude-code
  entries) or a genuine crash — not the known zero-token usage-window
  pattern, not a hidden-gate FAIL — dispatch ONE studio-executor
  (model=sonnet) with a self-contained TDD brief. Cap at ONE fix attempt; if
  still broken, mark it a known issue and move on.

STEP 4 — FINAL REPORT:
- `custom` real rep count now (out of 3), which rep indices, cost of each
  successful attempt, any bug found/fixed (commit SHA).
- Total $ spent this session.
- Do NOT touch ecc/karpathy/superpowers or A3 in this session. Do NOT run
  the docs-reconciliation step — that's 26-A3-and-wrapup.md, once all axis
  data is in. Stop after the report.
```
