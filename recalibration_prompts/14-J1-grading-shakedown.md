# J1 — Grading UI shakedown (HUMAN grades + Claude Code launch)

**Service:** Claude Code launches the UI; **YOU** grade; Claude Design polishes
(prompt `15`).
**Goal:** exercise the blind pairwise grading UI on real hidden-gate passers from
the sweeps so far — axis picker + cascading cell pickers — and confirm blinding
(no axis id leaks into the diffs).

---

### Step 1 — Launch. Paste to Claude Code (or run it yourself):

```
Launch the grading UI against our real results so far:
   .venv\Scripts\python.exe cli.py grade --db results.db
It serves at http://localhost:8247. Before I start grading, confirm in the code
(ui/server.py, grading/pairwise.py) that EVERY axis id is redacted from the
diffs shown to the grader, for whichever comparison axis is selected. Tell me how
many hidden-gate passers exist per cell so I know if there's enough to grade.
```

### Step 2 — YOU grade in the browser

Open http://localhost:8247. For a chosen comparison axis (e.g. methodology) and
a pinned cell, grade blind pairwise (A / B / Tie), advancing with the keyboard.
Do several. Then switch the comparison axis (e.g. to model) and grade a few more.

**What YOU watch for (notepad):** any axis id or other tell leaking into a diff;
confusing/ugly UI; awkward keyboard flow; unclear which cell you're in; missing
"why" affordances; anything slow or broken. Write it ALL down — this is the most
UX-heavy surface.

### Step 3 — Capture issues. Paste your notes to Claude Code via the CHECKPOINT
prompt (`00-checkpoint-notepad-triage.md`). For purely visual/layout problems,
also use prompt `15` (Claude Design).

---

After fixes, tick **J1**, then prompt `16`.
