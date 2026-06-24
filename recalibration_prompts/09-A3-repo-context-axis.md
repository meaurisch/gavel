# A3 — Repo-Context axis (Claude Code)

**Service:** Claude Code runs; **you** watch and jot notes.
**Goal:** verify the repo-context axis and the `task_affinity` filtering plus the
`--full-matrix` override.

---

Paste to Claude Code:

```
Shake out the Repo-Context axis.

1. Dry-run across all repo-contexts on a Cosmos task:
   .venv\Scripts\python.exe cli.py run --task cosmos-A --methodology baseline --repo-context all --model claude-haiku-4-5 --runner claude-code --reps 1 --dry-run
   Confirm `none` (control) and the Cosmos repo-context both appear, and that a
   PyVRP-only repo-context is FILTERED OUT for a Cosmos task by task_affinity.

2. Prove the affinity override:
   ...same command with --full-matrix --dry-run
   Confirm the nonsensical pairings now appear (affinity ignored).

3. Run the sensible set for real (no --full-matrix). For each repo-context
   verify its files land FIRST in the worktree (before methodology), and that
   `none` lays down nothing.

4. Cross-check: run a PyVRP task with --repo-context all --dry-run and confirm
   the Cosmos repo-context is filtered out there too.

Report a table: task x repo-context -> included? (affinity) -> files laid down.
Flag any wrong filtering. Fix with TDD + commits.
```

**What YOU watch for (notepad):** affinity filtering wrong in either direction,
unclear messaging about what got skipped and why, ugly output.

---

After it's working, run the **CHECKPOINT** (`00-checkpoint-notepad-triage.md`),
then tick **A3**.
