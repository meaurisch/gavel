# J3 — Report command + Pareto frontier (Claude Code)

**Service:** Claude Code (visual design of the frontier via Claude Design,
prompt `18`).
**Goal:** build the `report` command (currently a stub that exits 1) and the
quality-vs-cost Pareto frontier visualization — the last unbuilt pieces.

---

Paste to Claude Code:

```
The `report` command in cli.py is a stub ("Not implemented yet"). Build it for
real, using grading/aggregate.py and the Bradley-Terry results.

Requirements:
1. `report` produces, for a chosen comparison axis + cell: the Bradley-Terry
   ranking with CIs, the three-tier gate pass-rates, the cost rollup, and the
   analyzer flags — as a clean terminal summary (Rich), and as a written
   artifact (HTML or markdown) under a reports/ dir.
2. Include the quality-vs-cost Pareto frontier: plot each comparison-axis value
   by quality (BT score) vs cost (USD), mark the frontier, and surface the
   stakes-based pick (high-stakes -> quality winner; routine -> cheapest value
   indistinguishable from the winner per overlapping CI). See IMPLEMENTATION_PLAN
   §6 for the decision rule.
3. Wire it to the matrix/db the same way `run` and `grade` are wired. Add tests
   (TDD) for the aggregation/frontier logic; the plotting can be smoke-tested.
4. Update README "Next up": the report command and Pareto viz are no longer
   stubs/open items.

Run `.venv\Scripts\python.exe -m pytest -q` (green) and commit in logical pieces.
For the FRONTIER VISUAL specifically, pause and let me get a design first
(prompt 18) before finalizing the chart styling.
```

---

After it works, run the **FINAL CHECKPOINT** (`00-checkpoint-notepad-triage.md`),
tick **J3**, then prompt `19` (first calibration sweep).
