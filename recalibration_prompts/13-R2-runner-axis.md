# R2 — Runner axis (Claude Code)

**Service:** Claude Code runs; **you** watch and jot notes.
**Goal:** verify the Runner axis — claude-code vs copilot-cli on one cell — with
cost for copilot joined via the usage calculator.
**If the spike FAILED:** substitute the `manual` runner for `copilot-cli`
everywhere below and skip the usage-calculator join.

---

Paste to Claude Code:

```
Shake out the Runner axis on one cell (one task, one methodology, one context,
one work model), comparing runners.

1. Dry-run:
   .venv\Scripts\python.exe cli.py run --task cosmos-A --methodology baseline --repo-context none --model <work_model> --runner copilot-cli --reps 1 --dry-run
   and the same with --runner claude-code --model claude-sonnet-4-6.

2. Run both for real (COPILOT_GITHUB_TOKEN exported for the copilot run).
   Verify each runner: produced a diff, the gate scored it, a Trial was recorded
   with the model actually used.

3. For the copilot trial, run the P2.2 usage calculator on the session and
   confirm the CostRecord gets filled and joined on trial_id (copilot attaches
   no cost at execute time). Sanity-check the USD/credits figures.

4. Confirm both runners' trials land in the same results.db and are comparable.

Report a table: runner -> diff captured? -> gate -> cost source -> USD. Flag any
asymmetry that would make a runner comparison unfair. Fix with TDD + commits.
```

**What YOU watch for (notepad):** copilot auth/flag friction, missing/garbled
diff capture, cost-join gaps, anything that makes the two runners not
apples-to-apples.

---

After it's working, run the **CHECKPOINT** (`00-checkpoint-notepad-triage.md`),
then tick **R2** → Phase J (prompt `14`).
