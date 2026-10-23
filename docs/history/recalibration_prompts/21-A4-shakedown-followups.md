# 21-A4 — Model-axis shakedown follow-ups

Context: setup-bench (C:\Users\norri\studio\setup-bench), a decision-support tool
for comparing agentic coding setups. The Model-axis shakedown (10-A4) ran
cosmos-A / baseline / repo-context none across haiku, sonnet, opus (claude-code,
1 rep) and surfaced runner bugs. Two were fixed on `main`; this prompt covers the
follow-ups that were deliberately deferred, plus their related sub-issues.

Fix ALL of the issues below with TDD (superpowers:test-driven-development) + short
commits, one logical fix per commit. Run the full suite after each fix
(`.venv\Scripts\python.exe -m pytest -q`, currently **195 pass / 1 deselected**).
Keep commit messages short and human, one logical change each.

## ALREADY FIXED (verify, don't redo)

- **996168d** — a gate crash no longer discards a trial's billed cost; `gate_apply`
  runs in its own `try:` in `core/executor.py` and records a FAIL on crash.
- **5fb9787** — `collect()` (runners/base.py) now diffs against a baseline ref
  captured *before* the agent runs, not live HEAD, so a committing agent's diff is
  no longer erased. `ClaudeCodeRunner.execute()` captures the post-`prepare()` HEAD
  and passes it. Default `baseline_ref="HEAD"` left in place for nop/oracle/manual.
- **27ff189** — `_DEFAULT_MAX_TURNS` reconciled 25 → 60 (settled §7 cap).
- **8841322** — held-out-path collision decision documented (fail-closed) in the
  README gate guardrail section.

## OPEN ISSUE 1 — `RunResult.error` is never persisted (HIGH)

- `core/models.py`: `RunResult` has an `error: str | None` field. But the
  `run_result` table in `core/db.py` (`_SCHEMA`) has only 4 columns
  (`trial_id, diff, exit_status, wall_seconds`) and `insert_run_result` writes only
  those 4. So every error the runner records — parse failures
  (`runners/claude_code.py` sets `error=parse_error`), and the gate-crash message
  the executor stashes in `summary["error"]` — is **silently dropped at insert**.
  It survives only in the in-memory `summary` shown in the live progress table; it
  is gone from `results.db`, so post-hoc analysis can't tell an errored trial from
  a clean one.
- Fix: add an `error TEXT` column to the `run_result` schema, backfill it via the
  existing `_ensure_column` helper (see how `task_spec` columns are backfilled in
  `init_schema`), persist it in `insert_run_result`, and read it back in
  `get_run_result`. Confirm the round-trip with a DB test (write a `RunResult`
  with `error="…"`, read it back, assert it survived) — mirror the style in
  `tests/test_db.py`.
- While here, decide whether a **genuinely empty diff** (agent produced no work —
  now a real signal, since 5fb9787 means an empty diff is no longer a false
  negative) should set `RunResult.error`. This is the "OR surface as explicit
  error" branch from the original diff-loss issue that was left unimplemented
  because the column didn't exist. Recommended: yes — set a clear error string
  when the diff is empty so an all-no-op trial is distinguishable in the DB. Do it
  as a second commit if you take it.

## OPEN ISSUE 2 — provenance-aware leakage assertion → overwrite-and-run (MEDIUM, design)

- Today a held-out-path collision (agent writes a test where the oracle lives) is
  a fail-closed hidden-gate FAIL — see the README gate guardrail note and
  `grading/gate.py:_run_hidden_tests` (`assert not dest.exists()`). The README
  documents overwrite-and-run (SWE-bench style) as the likely future direction.
- To enable it safely, the leakage assertion must become **provenance-aware**:
  distinguish a held-out file present via the *setup* (repo-context / methodology /
  task visible-tests commits — a genuine leak, must stay fatal) from one present
  only in the *agent's own diff* (not a leak — the agent never saw the oracle,
  which lives outside the worktree until gate time). Provenance is determinable:
  the setup commits form the baseline captured in 5fb9787; anything the agent
  added is in `git diff <baseline>`.
- If you implement: at gate time, for a colliding path that is provenance = agent,
  overwrite it with the oracle and run the true oracle (oracle always wins; agent's
  test content already survives in the captured diff for grading). For provenance =
  setup, keep the assertion fatal. **Do NOT weaken the setup-leakage guarantee** —
  the property "the model never sees the oracle and the gate runs the true oracle"
  must hold. The README says keep that guard; keep it, just make it precise.
- This is a design change to a protected invariant. Start with
  `superpowers:brainstorming` and get sign-off on the approach before writing code.
  If sign-off isn't available, leave it documented and stop after Issue 1.

## OPEN ISSUE 3 — `collect()` default baseline is a latent footgun (LOW)

- `collect(worktree_path, baseline_ref="HEAD")` defaults to HEAD so nop/oracle/
  manual (which never commit) stay unchanged. But when the Copilot runner
  (`runners/copilot.py`, stubbed — see 12-R1) is built, if it forgets to pass a
  captured baseline and the harness commits, the 5fb9787 bug silently returns for
  that runner. Decide: either make `baseline_ref` required (update the 4
  non-claude call sites to capture + pass a baseline) or leave the default and add
  a guard/regression test that fails loudly if a runner commits without a baseline.
  Low priority; fold into the Copilot runner work if not done now.

## Constraints

- Do NOT break the held-out leakage assertion / property in `grading/gate.py`
  (README says keep it). Issue 2 makes it *precise*, not *weaker*.
- Exit-1 from `claude` stays non-fatal — partial work must still be graded.
- `pyvrp-*` tasks build under WSL; Cosmos/.NET on the Windows shell (see README).

## When done

Run the full suite green, update README "Current state"/"Next up" to reflect what
landed, and report per-issue: what the root cause was, what changed, and the
before/after test count.
