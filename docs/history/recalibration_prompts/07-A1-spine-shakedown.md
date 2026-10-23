# A1 — Execution spine: Task + gate + cost (Claude Code)

**Service:** Claude Code runs the trials; **you** watch and jot notes.
**Goal:** prove the per-trial pipeline end-to-end on the golden tasks: worktree
isolation, file lay-down order, three-tier gate scorecard, cost from
pricing.toml, leakage scanner.
**Env reality:** PyVRP gates build under **WSL**; Cosmos gates build under
**Windows/.NET**. Start with a Cosmos task (simplest local toolchain).

---

Paste to Claude Code:

```
Shake out the execution spine of setup-bench on our golden tasks. Go in this
order and STOP at the first thing that's broken so we can fix it before going on.

1. Dry-run the matrix (no execution):
   .venv\Scripts\python.exe cli.py run --task cosmos-A --methodology baseline --repo-context none --model claude-haiku-4-5 --runner oracle --reps 1 --dry-run
   Confirm the trial grid looks right (1 trial, correct ids).

2. Oracle trial (must PASS the gate — it applies reference.diff):
   .venv\Scripts\python.exe cli.py run --task cosmos-A --methodology baseline --repo-context none --model claude-haiku-4-5 --runner oracle --reps 1
   Then the nop trial (must FAIL the gate — it does nothing):
   ...same but --runner nop
   Verify the three-tier scorecard (compile -> visible -> hidden) is recorded
   in results.db for both, and that the worktree was created fresh and torn down.

3. One REAL claude-code trial on Haiku (small, cheap):
   .venv\Scripts\python.exe cli.py run --task cosmos-A --methodology baseline --repo-context none --model claude-haiku-4-5 --runner claude-code --reps 1
   Verify: a diff was captured; the gate ran; a CostRecord was written with USD
   priced from cost/pricing.toml AND the self-reported figure as secondary;
   token counts present.

4. Repeat step 3 for one PyVRP task (e.g. pyvrp-A). PyVRP builds only under WSL.
   Check whether cli.py's executor handles the WSL toolchain the way
   scripts/validate_tasks.py does. If it does NOT, that is finding #1 — make
   `cli.py run` succeed for a PyVRP task on this machine by reusing the toolchain
   handling in scripts/validate_tasks.py (TDD; minimal change).

5. Confirm the leakage scanner runs and is green for each task.

Report a short table: task x runner -> gate result, cost, wall time, and any
anomaly. Fix anything broken with TDD + a focused commit, then re-run that step.
```

**What YOU watch for (notepad):** confusing log output, ugly/garbled progress
table, wrong or missing cost numbers, slow steps with no progress, anything that
"feels off." Write it all down.

---

After it's working, run the **CHECKPOINT** (`00-checkpoint-notepad-triage.md`),
then tick **A1**.
