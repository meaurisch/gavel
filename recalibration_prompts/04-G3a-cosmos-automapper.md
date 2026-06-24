# G3a — Cosmos AutoMapper task (Claude Code)

**Service:** Claude Code.
**Goal:** author the first Cosmos (C#/.NET 5) golden task — the AutoMapper →
hand-written-mappers slice — proving the cross-repo template and the .NET gate.
**Prereq:** .NET SDK present. If `dotnet --version` fails, install the .NET 5
(or compatible) SDK first; flag it to me if you can't.

---

Paste to Claude Code:

```
Author our first Cosmos golden task. The repo is at repos/cosmos
(CleanArchitectureCosmosDB.sln, .NET 5, Clean Architecture + Cosmos DB). Follow
the same task structure as tasks/pyvrp-A (task.yaml + reference.diff +
held_out_tests/) and the golden rubric in docs/task-design-guide.md.

Feature to revert/recreate: replace AutoMapper-based mapping with hand-written
mappers for 1–2 aggregates (cap it at 2). The task asks the agent to implement
the hand-written mapper(s) and wiring that AutoMapper was doing.

Steps:
1. Confirm the toolchain: `dotnet --version`, then a baseline build/test of the
   solution so we know green looks like (use `dotnet build` and `dotnet test`).
   Report the exact commands that work for THIS solution.
2. Pick the concrete aggregate(s) and the exact code slice to revert. Show me
   the plan before writing held-out tests.
3. Create tasks/cosmos-A/ with:
   - task.yaml: id, repo_url, base_commit (pin it), instruction (real-ticket
     language), build_cmd (`dotnet build ...`), run_cmd (`dotnet test ...`
     scoped to the new mapping tests), held_out_tests_path, reference_diff_path,
     difficulty.
   - reference.diff: the feature implementation (what oracle applies).
   - held_out_tests/: per-pair mapping tests, strengthened, leakage-safe.
4. Add a Cosmos repo-context under repo_contexts/ (manifest with task_affinity
   pointing at cosmos tasks); keep `none` as the control.
5. Validate: oracle (apply reference.diff -> tests pass) and nop (no diff ->
   tests fail). Wire this into scripts/validate_tasks.py if it doesn't already
   pick up non-PyVRP tasks; if the validator is PyVRP-specific, generalize it
   minimally (TDD) so it runs the task's own build_cmd/run_cmd.
6. `.venv\Scripts\python.exe -m pytest -q` green. Commit in logical pieces.

Report the working dotnet commands and the oracle/nop validation output.
```

---

After validation passes, tick **G3a**.
