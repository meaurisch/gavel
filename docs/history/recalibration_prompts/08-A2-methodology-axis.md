# A2 — Methodology axis (Claude Code)

**Service:** Claude Code runs; **you** watch and jot notes.
**Goal:** verify the methodology axis: each pack lays down its native files
correctly per harness, `baseline` lays down nothing (the ablation control).

---

Paste to Claude Code:

```
Shake out the Methodology axis. Use one golden task and the cheapest model so
this is about plumbing, not measurement.

1. Dry-run across all methodologies:
   .venv\Scripts\python.exe cli.py run --task cosmos-A --methodology all --repo-context none --model claude-haiku-4-5 --runner claude-code --reps 1 --dry-run
   Confirm one trial per methodology (baseline, custom, ecc, karpathy,
   superpowers) — and tell me if `custom` is not yet frozen/ready (it may not
   be; if it errors, exclude it and note that).

2. Run it for real (drop --dry-run). While it runs, for each methodology verify
   in the created worktree (before teardown) that:
   - repo-context files are laid down FIRST, methodology files SECOND, as two
     separate commits, never merged;
   - baseline lays down NOTHING;
   - each pack appears in its harness-native form (e.g. CLAUDE.md for the
     claude-code harness) per methodologies/<id>/manifest.yaml.
   If teardown is too fast to inspect, add a debug/--keep-worktree path or log
   the laid-down file list per trial (minimal change, TDD).

3. Confirm every trial produced a gate scorecard and a cost record.

Report a table: methodology -> files laid down -> gate -> cost. Flag any pack
that doesn't lay down what its manifest claims. Fix issues with TDD + commits.
```

**What YOU watch for (notepad):** wrong files placed, lay-down order wrong,
baseline not actually empty, manifest vs reality mismatches, ugly output.

---

After it's working, run the **CHECKPOINT** (`00-checkpoint-notepad-triage.md`),
then tick **A2**.
