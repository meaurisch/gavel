# A1 Checkpoint Fixes — Autonomous conductor prompt (5 executor subsessions)

**Service:** Claude Code. Paste the block below into a **fresh** session. It runs
end to end with **no manual actions**: the conductor cleans the tree itself,
dispatches five `studio-executor` subagents, recovers from any failed fix, and
verifies. Launch it in an autonomous permission mode (e.g. accept-edits /
bypass-permissions) so subagent dispatches and commits don't prompt.

---

Paste to Claude Code:

```
You are the CONDUCTOR for this session and you run FULLY AUTONOMOUSLY. Do not ask
me for anything, do not wait for approval, make every decision yourself, and run
to completion. Implement NOTHING on the main thread — dispatch five
studio-executor subagents, one per brief, then verify.

STEP 0 — CLEAN THE TREE YOURSELF (do this first):
- Run `git status --porcelain`. If any TRACKED files are modified or staged,
  inspect `git diff` and commit them as ONE isolated commit on the current branch
  with a short honest message (e.g. "plan: checkpoint wip"), so the five fixes
  land as clean separate commits. Leave untracked scratch files alone. Do NOT
  push. After this, `git status` must show a clean tracked tree before you
  dispatch anything.

CONTEXT DISCIPLINE (the point of the exercise — hold to it):
- Do NOT read the target source files yourself. Each executor reads only the
  files named in its brief. Keep your own context at plan level.
- Dispatch ONE executor at a time, in the given order. Wait for its summary
  before dispatching the next. Sequential is mandatory: fixes share files
  (cli.py: #4,#1 | executor.py: #3,#2 | models.py: #3,#5) — parallel would
  clobber and the later fix would land on a stale file.
- Pass each brief VERBATIM as the subagent task. Append these lines to every
  dispatch: "Work TDD: write the failing test first. Run only the test files
  named. Commit with the given message. Report back ONLY a <=4-line summary
  (files touched, commit SHA, test result). Do NOT paste diffs or file bodies.
  If you cannot get your tests green, REVERT all your own changes (git restore +
  delete any new files you created) so the tree is clean, and report FAILED with
  a one-line reason — do NOT commit broken code."

AUTONOMOUS FAILURE HANDLING:
- If an executor reports FAILED, verify the tree is clean (`git status`); if the
  executor left anything behind, clean only what that brief touched. Mark the
  brief FAILED, then CONTINUE to the next brief — do not stop, do not ask me.
- Never let a later executor build on broken or half-applied work.

MODELS:
- Dispatch #4, #1, #3, #2 with model=sonnet (well-specified, mechanical).
- Dispatch #5 with model=opus (multi-file design change; judgment needed).

ORDER: #4 -> #1 -> #3 -> #2 -> #5.

AFTER ALL FIVE: run `.venv\Scripts\python.exe -m pytest -q` ONCE. Then print a
final report: per-brief PASS/FAILED, the commit SHA for each PASS, and the full
suite pass/deselect count. Do NOT tick any checklist and do NOT start A2 — stop
after the report.

========================= BRIEF #4 — UTF-8 console =========================
GOAL: Console garbles non-ASCII (shows U+FFFD) on cp1252 Windows terminals —
Rich emits ellipsis/box chars stdout cannot encode. Force UTF-8.
FILES: cli.py ; new tests/test_cli.py
DO (TDD):
 1. Failing test in tests/test_cli.py: a fake stream object that records
    reconfigure(encoding=...) calls. Assert a helper _force_utf8(streams) calls
    reconfigure(encoding="utf-8") on a stream whose .encoding=="cp1252", and
    leaves a stream already "utf-8" untouched.
 2. Add _force_utf8(streams) to cli.py (guard with hasattr(s,"reconfigure"));
    call it on (sys.stdout, sys.stderr) at import time, BEFORE console=Console().
VERIFY: .venv\Scripts\python.exe -m pytest -q tests/test_cli.py
COMMIT: cli: force UTF-8 console output (fix garbled chars on cp1252)

========================= BRIEF #1 — compact Trial column ==================
GOAL: Live progress table overflows 80 cols. The Trial column prints the full
trial id, which repeats methodology/context/model (already their own columns),
so Rich squeezes and truncates ugly. Show a compact label instead.
FILES: cli.py (_progress_table only — leave _grid_table) ; tests/test_cli.py
DO (TDD):
 1. Failing test: build one Trial, call _progress_table, assert the first
    column's cell text == f"{trial.task_id} #{trial.rep}" (not the long id).
 2. In _progress_table change every Trial cell from t.id to
    f"{t.task_id} #{t.rep}"; drop the max_width=60 on that column.
VERIFY: .venv\Scripts\python.exe -m pytest -q tests/test_cli.py
COMMIT: cli: compact Trial column so progress table fits 80 cols

========================= BRIEF #3 — parse error -> ERROR ==================
GOAL: When the claude-code runner can't parse CLI output, the trial shows a
normal gate FAIL with no cost — indistinguishable from a model failure. An
instrumentation failure must read as ERROR, not a silent FAIL.
FILES: core/models.py (RunResult) ; runners/claude_code.py ; core/executor.py ;
       tests/test_executor.py ; tests/test_claude_runner.py
DO (TDD):
 1. Add `error: str | None = None` to the RunResult dataclass.
 2. claude_code.py: in the `except ClaudeUsageParseError as e` block keep a
    message; pass error=<message> into the RunResult returned on the normal
    path when parsing failed (None otherwise). Leave the timeout path error=None.
 3. core/executor.py execute_trial: after run_result = runner.execute(...), if
    run_result.error: summary["error"] = run_result.error. The gate still runs
    and records; the Live table already renders summary["error"] as red ERROR.
 4. Tests: (a) executor — a stub runner returning RunResult(error="x") yields
    summary["error"]=="x"; (b) claude_runner — unparseable stdout yields a
    returned RunResult with error not None AND last_cost is None.
VERIFY: .venv\Scripts\python.exe -m pytest -q tests/test_executor.py tests/test_claude_runner.py
COMMIT: runner/executor: surface parse failures as ERROR, not silent FAIL

========================= BRIEF #2 — whole-trial wall ======================
GOAL: Wall(s) shows only runner think-time; for PyVRP it hides a multi-minute
WSL gate build. The displayed wall must cover the whole trial (runner + gate).
Keep RunResult.wall_seconds (runner-only) unchanged in the DB.
FILES: core/executor.py ; tests/test_executor.py
DO (TDD):
 1. Failing test: patch time.monotonic to a controlled sequence (or stub
    runner+gate) and assert summary["wall_seconds"] reflects the whole
    execute_trial span, not just run_result.wall_seconds.
 2. execute_trial: trial_start=time.monotonic() at the top; in `finally` set
    summary["wall_seconds"]=time.monotonic()-trial_start. Remove the old
    summary["wall_seconds"]=run_result.wall_seconds line. The DB insert of
    run_result still stores the runner-only wall — do not change that.
VERIFY: .venv\Scripts\python.exe -m pytest -q tests/test_executor.py
COMMIT: executor: report whole-trial wall (runner + gate)

========================= BRIEF #5 — visible-test composition ==============
GOAL: (a) Let a REPO declare it ships a unit suite sufficient to serve as the
visible tier, so tasks needn't each supply a visible_test_cmd; (b) let a TASK
supply ADDITIONAL visible test files on top of the repo's. Implement fully,
backward-compatible, and document well. This is a real feature, not a stub.
FILES: core/models.py (TaskSpec) ; new repos.yaml (project root) ;
       core/task_loader.py (+ a small repos.yaml loader, inline or new
       core/repo_loader.py) ; runners/base.py and/or runners/claude_code.py
       (laydown) ; grading/gate.py (only if needed) ; scripts/validate_tasks.py ;
       README.md + docs task-design guide ; matching tests/.

DESIGN — implement exactly this:
 1. repos.yaml at PROJECT ROOT maps repo id -> {visible_test_cmd: "..."}.
    Presence of the key IS the conscious opt-in (no redundant boolean). Add:
        cosmos:
          visible_test_cmd: 'dotnet test tests/CleanArchitectureCosmosDB.UnitTests/CleanArchitectureCosmosDB.UnitTests.csproj'
    CRITICAL: this file lives at project root, NEVER inside repos/<repo> — a
    file inside the checkout would leak into every worktree and become visible
    to the model.
 2. TaskSpec gains `visible_tests_path: str | None = None` — a directory of
    EXTRA visible test files this task injects.
 3. RESOLUTION (in task_loader.load_task — set the EFFECTIVE task.visible_test_cmd
    so grading/gate.py needs no change):
        task cmd is an explicit string  -> use it (override)
        task cmd is null/unset          -> repos.yaml cmd if the repo declares
                                           one, else None
        task cmd == "none" (sentinel)   -> None (force-skip even if repo declares)
 4. LAYDOWN: if task.visible_tests_path is set, copy that dir into the worktree
    and commit it as its OWN setup commit "setup-bench: lay down task visible
    tests", laid down BEFORE the repo-context commit. (Add a dir-copy helper next
    to lay_down_files; reuse the gate's _iter_files walk.) Committed => visible to
    the model, absent from its diff. Keep the existing repo-context-then-
    methodology relative order and their two separate commits intact. NOTE: no
    current task sets visible_tests_path, so this is a no-op for existing tasks
    and must not change any current trial's behavior.
 5. VALIDATOR: scripts/validate_tasks.py runs the RESOLVED visible_test_cmd at
    base_commit and asserts green (skip when None). This is what makes the repo
    flag honest — you can't declare a suite that doesn't build/pass.

GUARDRAILS (document + keep enforced):
 - Task-supplied visible tests must NOT duplicate the held-out oracle. The gate
   already asserts held-out files aren't pre-present in the worktree — keep that
   assertion. Document the caution: visible tests that ARE the hidden tests let
   the model trivially satisfy the gate.

TDD: task_loader resolution (override / inherit / none-sentinel / no repos.yaml);
laydown (visible files present + committed, NOT in the model diff); validator
path if feasible. Run the affected test files.
DOCS: update README (How to run + task fields) and the task-design guide under
docs/ with the repo flag, visible_tests_path, the resolution table, and the
guardrail.
COMMITS: prefer 2–4 focused commits (model+loader / laydown / validator / docs)
over one mega-commit.
VERIFY: run the affected test files; the conductor runs the full suite at the end.
```
