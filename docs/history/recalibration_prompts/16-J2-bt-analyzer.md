# J2 — Bradley-Terry + analyzer (Claude Code)

**Service:** Claude Code.
**Goal:** validate the ranking + analyzer math on the REAL judgments you produced
in J1 (not just unit fixtures): multi-rep sampling → Bradley-Terry scores +
bootstrap CIs → analyzer flags.

---

Paste to Claude Code:

```
We now have real pairwise judgments in results.db from grading. Validate the
aggregation end-to-end on real data:

1. Run the multi-rep pairwise sampling + Bradley-Terry fit (grading/pairwise.py,
   grading/bradley_terry.py, grading/aggregate.py) over the graded cell(s).
   Produce the Elo-style scores with 95% bootstrap CIs for the chosen comparison
   axis. Show the ranking.
2. Sanity-check: do overlapping CIs correctly mark indistinguishable values? Is
   multi-rep sampling drawing balanced cross-value pairs from ALL reps (not just
   one)? Verify against the data, not just the unit tests.
3. Run the analyzer (grading/analyzer.py) and confirm its flags fire correctly:
   non-discriminating axis values (all pass / all fail), flaky tasks (high
   variance across reps), and cost/quality tradeoffs. If our real data doesn't
   trigger a flag that should exist, say so.
4. Report the ranking + CIs + flags in a readable summary. If anything is wrong
   or brittle on real (small-n) data, fix it with TDD + commits.
```

**What YOU watch for (notepad):** rankings that don't match your gut from
grading, CI behavior that seems off, confusing analyzer output.

---

After validation, tick **J2**, then prompt `17`.
