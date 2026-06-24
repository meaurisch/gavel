# G2 — Raise PyVRP A/B/C to golden (Claude Code)

**Service:** Claude Code.
**Goal:** audit the three existing PyVRP tasks against the golden rubric and fix
gaps, then re-validate. PyVRP builds only under WSL — the validator already
handles that.

---

Paste to Claude Code:

```
We now have a golden-task rubric in docs/task-design-guide.md. Audit and upgrade
the three existing PyVRP tasks (tasks/pyvrp-A, tasks/pyvrp-B, tasks/pyvrp-C) to
meet it. Work one task at a time, A then B then C.

For each task:
1. Read its task.yaml, reference.diff, and held_out_tests/. Score it against
   every rubric criterion in docs/task-design-guide.md. Produce a short
   scorecard (criterion -> pass/fail/concern).
2. Fix the gaps you can fix in-repo:
   - Strengthen held-out tests beyond the original PR where they're thin
     (more assertions, edge cases) WITHOUT leaking the solution into anything
     the agent can see.
   - Tighten the instruction language so it reads like a real ticket; if one of
     the three should be our deliberately UNDER-specified task, tell me which
     and why before changing it.
   - Ensure a `difficulty` field is set with a justification.
3. Re-validate in WSL (this is the canonical check for PyVRP):
   wsl -d Ubuntu -- bash -c 'source ~/pyvrp-venv/bin/activate && cd /mnt/c/Users/norri/studio/setup-bench && python scripts/validate_tasks.py --verbose --skip-toolchain-check'
   Expected: oracle=PASS, nop=FAIL for all three.
4. Run `.venv\Scripts\python.exe -m pytest -q` (green).
5. Commit each task's upgrade separately with a short message.

Do NOT touch repos/pyvrp working state or held_out_tests placement rules
(leakage-safety). Report the three scorecards and which task you recommend as
the under-specified one.
```

---

**Human note:** the choice of the under-specified task and final stakes tiers
is yours — Claude Code proposes, you decide. Record the decision in
`IMPLEMENTATION_PLAN.md` §7 (task-set row). Then tick **G2**.
