# G3b — Author the second Cosmos task (Claude Code)

**Service:** Claude Code.
**Goal:** author the second Cosmos golden task from the researched feature
(prompt `05`).
**You do first:** paste the chosen feature + which files/commit + testing caveat
in place of `<<<PASTE FEATURE CHOICE>>>`.

---

Paste to Claude Code:

```
Author our second Cosmos golden task, tasks/cosmos-B, mirroring the structure of
tasks/cosmos-A and the golden rubric in docs/task-design-guide.md.

Chosen feature (from research):
<<<PASTE FEATURE CHOICE>>>

Steps:
1. Confirm the exact `dotnet build` / `dotnet test` commands that work for this
   feature's test project (reuse what cosmos-A established). If the feature
   needs a Cosmos emulator, prefer testing against the repo's abstractions/mocks
   so held-out tests run with no live Azure; if that's impossible, tell me and
   stop — we'll repick.
2. Pin base_commit, write the instruction in real-ticket language (decide with
   me whether THIS one is the under-specified task or whether that's a PyVRP one
   — only one task total is under-specified).
3. Create tasks/cosmos-B/ : task.yaml, reference.diff, held_out_tests/
   (strengthened, leakage-safe), difficulty.
4. Ensure repo_contexts task_affinity covers cosmos-B.
5. Validate oracle=PASS / nop=FAIL via scripts/validate_tasks.py.
6. `.venv\Scripts\python.exe -m pytest -q` green. Commit in logical pieces.

Report the validation output and the final golden task set (PyVRP A/B/C +
cosmos-A + cosmos-B) with each task's difficulty and which is under-specified.
```

---

After this: finalize the **task-set + stakes tiers** in `IMPLEMENTATION_PLAN.md`
§7, tick **G3b**, then run the **CHECKPOINT** (`00-checkpoint-notepad-triage.md`)
before starting Phase A.
