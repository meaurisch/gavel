# 27 — fix cli.py run-summary cost under-reporting for ERROR trials

**Service:** single mechanical bug fix, one executor dispatch, no manual
action needed during the run.

**Context:** found during `24-A2-cheap-methodologies.md` (session 2026-07-02).
A `superpowers` batch of 3 real, billed trials (all ended with
`error: "agent produced an empty diff (no changes)"`, but each had real
non-zero cost/tokens in `cost_record`) printed:

```
Done. 0 passed, 0 failed, 3 errors. Total cost: $0.00
```

`results.db` is correct — `cost_record.usd_equiv` has the real per-trial cost
for all three. Only the terminal summary line under-counts. This is a
display-only bug; no data was lost or miscorrected.

**Root cause (already diagnosed, do not re-diagnose):** in `cli.py`, the
`run()` command body has, near the end:

```python
done = [r for r in results.values() if not r.get("skipped") and not r.get("error")]
passed = sum(1 for r in done if r.get("passed"))
failed = sum(1 for r in done if r.get("passed") is False)
errors = sum(1 for r in results.values() if r.get("error"))
total_usd = sum(r.get("usd", 0) for r in done)
```

`done` excludes any result with a truthy `error` — correct for `passed`/
`failed` (a trial that errored has no meaningful gate verdict), but wrong for
`total_usd`, which silently drops real billed cost on every errored trial.
Confirmed in `core/executor.py::execute_trial`: `summary["error"]` and
`summary["usd"]` are set independently — an errored trial can still carry a
non-zero `usd`. Only `skipped` trials should be excluded from the cost total;
`error` trials should not be.

---

You are the CONDUCTOR for this session and you run FULLY AUTONOMOUSLY. Make
every decision yourself and run to completion. Implement NOTHING on the main
thread — dispatch exactly ONE studio-executor subagent for the fix below, then
verify and stop. Do not read `cli.py` or `core/executor.py` yourself beyond
what's already quoted above — stay at plan level, let the executor do the
reading.

STEP 0 — CLEAN THE TREE:
- `git status --porcelain`. If any TRACKED files are modified/staged, commit
  them as ONE isolated "session: checkpoint wip" commit first. Leave
  untracked scratch alone. Confirm a clean tracked tree before dispatching.

STEP 1 — DISPATCH (single executor, model=sonnet):

Dispatch one `studio-executor` subagent with this self-contained brief:

```
GOAL: fix cli.py's run-summary line under-reporting total cost when trials
end in error. Root cause: the `done` list (built to exclude errored trials
from pass/fail counts) is also used to sum `total_usd`, so any trial that
errored but still billed real cost (e.g. "agent produced an empty diff")
gets its cost silently dropped from the printed total. results.db itself is
unaffected — this is a display-only bug in the printed summary line.

FILES:
- cli.py (fix)
- tests/test_cli.py (new test, follows the existing pattern of testing small
  pure helpers like `_progress_table` — see the existing tests in that file
  for style/conventions)

DO (TDD — write the failing test first):
1. In cli.py, extract the summary-aggregation block currently inline at the
   end of the `run()` command (the `done = [...]` / `passed = ...` /
   `failed = ...` / `errors = ...` / `total_usd = ...` lines, roughly lines
   142-146) into a standalone pure function, e.g.:

     def _summarize(results: dict[str, dict]) -> tuple[int, int, int, float]:
         """Returns (passed, failed, errors, total_usd)."""

   Keep `passed`/`failed` computed only over non-skipped, non-error results
   (unchanged behavior — a trial with an error has no meaningful gate
   verdict). Fix `total_usd` to sum `usd` over ALL non-skipped results
   (including errored ones), since `core/executor.py::execute_trial` sets
   `summary["usd"]` independently of `summary["error"]` — an errored trial
   can carry real billed cost that must not be dropped. Only `skipped`
   trials (never actually run, no cost incurred) should be excluded from the
   cost sum.
2. Update `run()` to call `_summarize(results)` instead of the inline block,
   using its returned tuple for the final `console.print(...)` line.
3. In tests/test_cli.py, add tests for `_summarize` covering at minimum:
   - an errored result with non-zero `usd` is included in total_usd but not
     in passed/failed counts (this is the regression case — must fail on the
     current code and pass after the fix)
   - a skipped result contributes 0 to everything and isn't counted as an
     error
   - a normal passed/failed result aggregates as before (no behavior change)
   Use plain dicts shaped like the `summary` dicts `core/executor.py`
   produces (keys: `passed`, `usd`, `tokens`, `wall_seconds`, `error`,
   `skipped` — not all keys present on every dict, mirror what `run()`
   already handles via `.get()`).

VERIFY: `.venv\Scripts\python.exe -m pytest tests/test_cli.py -v`
All tests in that file must pass, including the new ones.

COMMIT: "fix: include errored-but-billed trials in cli run-summary cost total"

Report back ONLY a <=4-line summary: files touched, commit SHA, test result.
Do NOT paste diffs or file bodies.

If tests won't go green, revert your own changes so the tree is clean and
report FAILED with a one-line reason.
```

STEP 2 — VERIFY:
- Confirm the executor's report shows the named test command passed and a
  commit SHA exists (`git log -1 --oneline`).
- Spot-check by eye that the commit touches only `cli.py` and
  `tests/test_cli.py` (`git show --stat <sha>`).

STEP 3 — FAILURE HANDLING:
- If the executor reports FAILED: confirm the tree is clean
  (`git status --porcelain` empty), do not retry a second time, report the
  one-line reason and stop.

STEP 4 — FINAL REPORT + STOP:
- Print PASS/FAILED, the commit SHA, and the test result line.
- Do not touch anything else in this session — this is a single isolated
  fix, not a jumping-off point for further cleanup.
