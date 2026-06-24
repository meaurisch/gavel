# A4 — Model axis (Claude Code)

**Service:** Claude Code runs; **you** watch and jot notes.
**Goal:** verify the model axis end-to-end and that cost differences across
models show up correctly (this is the first place real cost deltas appear).

---

Paste to Claude Code:

```
Shake out the Model axis on one cell (one task, one methodology, one context),
sweeping the three Claude models.

1. Confirm all three models are in the pricing table:
   .venv\Scripts\python.exe cli.py pricing list
   (expect claude-haiku-4-5, claude-sonnet-4-6, claude-opus-4-8). If any is
   missing, add it with `cli.py pricing add` or `pricing fetch`.

2. Run the sweep (reps=1 for the shakedown to keep it cheap):
   .venv\Scripts\python.exe cli.py run --task cosmos-A --methodology baseline --repo-context none --model claude-haiku-4-5,claude-sonnet-4-6,claude-opus-4-8 --runner claude-code --reps 1

3. Verify per model: a trial ran, a diff was captured, the gate scored it, and
   the USD cost is priced from pricing.toml at that model's rate (Haiku cheapest,
   Opus dearest — sanity-check the ordering). Confirm tokens and wall time are
   recorded.

Report a table: model -> gate -> tokens -> USD -> wall(s). Flag any mispriced or
missing cost. Fix with TDD + commits.
```

**What YOU watch for (notepad):** cost numbers that look wrong relative to the
pricing table, model id mismatches, missing self-reported figure, ugly output,
rate-limit handling.

---

After it's working, run the **CHECKPOINT** (`00-checkpoint-notepad-triage.md`),
then tick **A4**. Phase A done → move to the Copilot spike (prompt `11`).
