# J1 prerequisite audit — Autonomous conductor prompt (4 executor subsessions)

**Context:** J1 (`14-J1-grading-shakedown.md`) was pasted to Claude Code on
2026-07-01. Launching `cli.py grade --db results.db` and grading against
`ui/server.py` / `grading/pairwise.py` surfaced two real problems:

1. **A redaction gap.** `anonymize_diff` (`grading/pairwise.py`) sorts ids
   longest-first *within* one axis, but processes the four axes in a fixed
   order with no cross-axis ordering. A short id from an axis processed
   earlier (`AXIS_FIELDS` order: methodology, model, repo_context, runner)
   can be a substring of a longer id from an axis processed later. Confirmed
   with a script: methodology id `"v2"` + runner id
   `"agent-v2-experimental"` → output `"agent-[methodology]-experimental"`
   instead of `"[runner]"` — the runner id's own token never applies and
   `agent-`/`experimental` leak into the diff shown to the grader. Does not
   trigger on the current dataset (checked: `baseline`, `none`,
   `claude-haiku-4-5`/`claude-opus-4-8`/`claude-sonnet-4-6`,
   `claude-code`/`nop`/`oracle` — none is a substring of another) but is a
   live risk for any future id that happens to be a short substring of a
   different axis's id.

2. **Zero gradeable data, discovered too late.** `results.db` has 11 trials,
   4 hidden-gate passers, **0 gradeable cells on any axis** (a cell needs 2+
   distinct comparison-axis values that both pass hidden tests, in an
   otherwise-fixed cell). Root cause, confirmed against `results.db`:
   - `methodology` and `repo_context` each have exactly **one** value across
     all trials (`baseline`, `none`) — A2 (`08-A2-methodology-axis.md`) and
     A3 (`09-A3-repo-context-axis.md`) were never actually run with
     `--methodology all` / `--repo-context all` for real (dry-run only, or
     not run at all).
   - A4 (`10-A4-model-axis.md`) *was* run for real (cosmos-A / baseline /
     none / claude-haiku-4-5,claude-sonnet-4-6,claude-opus-4-8 /
     claude-code, matches the prompt exactly) and its follow-up bugs were
     fixed on `main` (commits `5c9fea7`, `df1bfd5`, `7a5121d`,
     `686cf00` — match `21-A4-shakedown-followups.md` issues 1–3). But every
     real (non-oracle) trial still failed the hidden gate — expected at
     reps=1 on uncalibrated tasks — so the model axis has only the `oracle`
     control passing per task, never 2 real values.
   - Meanwhile `docs/superpowers/recalibration-checklist.md` still shows
     A1–A4 all unticked, yet marks **J1 as "NEXT"**, and `README.md`'s "Next
     up" lists "J1 — grading UI shakedown (NEXT)" unconditionally. Nothing
     in the playbook checks "is there actually gradeable data" before
     pointing the human at J1 — that's the process gap that let this
     happen, and it will happen again at the next phase transition unless
     there's an explicit, automatable check.
   - The UI's own symptom was unhelpful: `ui/static/index.html` just shows
     "No grading-ready data. Run some trials first." with no indication of
     *why* (which axes are short, by how much).

**What this prompt fixes:** the redaction bug, the missing diagnostic (why
is there no data), and a real "Definition of Ready" check for Phase J so
this can't silently recur — plus reconciling the checklist/playbook/README
to the actual (partial) state of Phase A. **It does NOT run any real
trials** — producing actual gradeable data means spending real API money on
A2/A3 (and likely more reps of A4), and every cost-bearing step in this
project is human-initiated with a projected-cost check first (see
`19-M-calibration-sweep.md`, `10-A4-model-axis.md`). That stays a manual
step for you, spelled out at the end of this prompt.

---

Paste the block below into a **fresh** Claude Code session. It runs end to
end with **no manual actions** during the run: the conductor cleans the
tree itself, dispatches four `studio-executor` subagents, recovers from any
failed fix, and verifies. Launch it in an autonomous permission mode (e.g.
accept-edits / bypass-permissions) so subagent dispatches and commits don't
prompt.

---

```
You are the CONDUCTOR for this session and you run FULLY AUTONOMOUSLY. Do not ask
me for anything, do not wait for approval, make every decision yourself, and run
to completion. Implement NOTHING on the main thread — dispatch four
studio-executor subagents, one per brief, then verify.

STEP 0 — CLEAN THE TREE YOURSELF (do this first):
- Run `git status --porcelain`. If any TRACKED files are modified or staged,
  inspect `git diff` and commit them as ONE isolated commit on the current branch
  with a short honest message (e.g. "session: checkpoint wip"), so the four fixes
  land as clean separate commits. Leave untracked scratch files alone. Do NOT
  push. After this, `git status` must show a clean tracked tree before you
  dispatch anything.

CONTEXT DISCIPLINE (the point of the exercise — hold to it):
- Do NOT read the target source files yourself. Each executor reads only the
  files named in its brief. Keep your own context at plan level.
- Dispatch ONE executor at a time, in the given order. Wait for its summary
  before dispatching the next. Sequential is mandatory: brief #3 imports the
  function brief #2 adds to core/db.py, and brief #4 documents the state left
  by #1–#3 — shared/dependent files (core/db.py: #2,#3 | docs+README: #4 only,
  but must run last to describe reality accurately).
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
- Never let a later executor build on broken or half-applied work. If brief #2
  FAILED, brief #3 cannot proceed (it depends on #2's new function) — mark #3
  SKIPPED (blocked by #2 FAILED) rather than dispatching it, and still dispatch
  #4 (it can document the blocked state).

MODELS:
- Dispatch #1, #2, #3 with model=sonnet (well-specified, mechanical).
- Dispatch #4 with model=opus (cross-file docs reconciliation; judgment needed
  about what's actually true).

ORDER: #1 -> #2 -> #3 -> #4.

========================= BRIEF #1 — cross-axis redaction fix =========================
GOAL: anonymize_diff() in grading/pairwise.py sorts substitution ids longest-first
WITHIN one axis, but has no ordering ACROSS the four axes (processed in
AXIS_FIELDS insertion order: methodology, model, repo_context, runner). A short id
from an earlier-processed axis can be a substring of a longer id from a
later-processed axis, partially consuming it before its own token is applied and
leaking a fragment. Fix: sort ALL ids from ALL axes together, longest first,
before substituting.
FILES: grading/pairwise.py ; tests/test_pairwise.py
DO (TDD):
 1. Failing test in tests/test_pairwise.py (alongside test_anonymize_longest_first_substring):
    a diff containing "runner = agent-v2-experimental", called with
    axis_ids_by_axis={"methodology": ["v2"], "model": [], "repo_context": [],
    "runner": ["agent-v2-experimental"]}. Assert "[runner]" is in the result,
    "agent-" and "experimental" are NOT in the result (no leaked fragment), and
    the full runner id is not in the result. This must FAIL against current code
    (it currently produces "agent-[methodology]-experimental").
 2. In anonymize_diff, replace the nested loop (`for axis, ids in
    axis_ids_by_axis.items(): ... for sid in sorted(ids, key=len, reverse=True)`)
    with a single flat pass: build one list of (sid, token) pairs across every
    axis, sort that list by len(sid) descending (globally, not per-axis), then
    substitute in that order. Keep everything else (instruction-file stripping,
    re.escape, IGNORECASE) unchanged.
 3. Confirm test_anonymize_redacts_every_axis_id and
    test_anonymize_longest_first_substring (the existing tests) still pass
    unchanged — the fix must not alter same-axis behavior.
VERIFY: .venv\Scripts\python.exe -m pytest -q tests/test_pairwise.py
COMMIT: grading: sort redaction ids globally across axes, not just within one (fixes cross-axis substring leak)

========================= BRIEF #2 — grading-readiness diagnostic (DB + API) =========================
GOAL: There is currently no way to see WHY the grading UI has no data short of
querying results.db by hand. Add a diagnostic that reports, per axis, how many
distinct values have hidden-gate passers and how many gradeable cells (>=2
distinct passing values in an otherwise-fixed cell) exist — plus the total
hidden-gate-passer count. Depends on nothing from brief #1 (different file).
FILES: core/db.py ; ui/server.py ; tests/test_db.py ; tests/test_server.py
DO (TDD):
 1. Failing test in tests/test_db.py: seed a handful of trials + gate_results
    (mirror the style of the list_grading_cells tests already in that file),
    call a new core/db.py function `grading_readiness(conn) -> dict`, and assert
    its shape:
      {"total_hidden_gate_passers": int,
       "axes": {"<axis>": {"distinct_passing_values": int, "gradeable_cells": int}, ...}}
    for all four AXIS_FIELDS keys (methodology, model, repo_context, runner).
 2. Implement `grading_readiness` in core/db.py: total_hidden_gate_passers is
    `SELECT COUNT(*) FROM gate_result WHERE passed = 1`; for each axis,
    distinct_passing_values is `SELECT COUNT(DISTINCT t.<col>) FROM trial t JOIN
    gate_result g ON t.id = g.trial_id WHERE g.passed = 1`, and gradeable_cells is
    `len(list_grading_cells(conn, axis))` (reuse the existing function, don't
    duplicate its query). Import AXIS_FIELDS from grading.pairwise (already done
    elsewhere in this file).
 3. Failing test in tests/test_server.py: hit a new `GET /api/grading-status`
    endpoint (follow the existing test client setup in that file) and assert the
    response matches grading_readiness()'s shape (wrap in a small Pydantic model
    the same way other endpoints in ui/server.py do, e.g. mirroring AxisInfo).
 4. Implement the endpoint in ui/server.py: call core.db.grading_readiness(_conn)
    and return it via the new Pydantic model. Place it near get_axes (it serves
    the same "what's available" purpose).
VERIFY: .venv\Scripts\python.exe -m pytest -q tests/test_db.py tests/test_server.py
COMMIT: db/api: add grading_readiness diagnostic (why is there no gradeable data)

========================= BRIEF #3 — surface it in the UI + a CLI check script =========================
GOAL: (a) the grading UI's empty state just says "No grading-ready data. Run
some trials first." with zero detail — replace it with the actual per-axis
counts from /api/grading-status (brief #2) so a human can see which axis is
short and by how much. (b) add a standalone script mirroring
scripts/validate_tasks.py / scripts/calibrate_tasks.py conventions so the same
check is runnable outside the UI, as an explicit pre-flight for Phase J.
DEPENDS ON BRIEF #2 (uses grading_readiness / /api/grading-status) — do not
dispatch this brief if #2 FAILED.
FILES: ui/static/index.html (loadAxes() only) ; new scripts/check_grading_ready.py ;
       new tests/test_check_grading_ready.py (or extend an existing scripts test
       file if one already covers validate_tasks.py/calibrate_tasks.py — check
       first)
DO:
 1. In ui/static/index.html's loadAxes(), when axesData.length === 0, fetch
    `/api/grading-status` and build the $emptyMessage text from it instead of
    the static string, e.g.: "No gradeable cells yet. N hidden-gate passers
    total. methodology: X distinct passing value(s) (need 2+ in one cell); model:
    Y; repo_context: Z; runner: W." Fall back to the current generic string if
    the fetch fails. This is a small DOM/JS change — smoke-test by hand if no JS
    test harness exists in this repo (check first), otherwise add one.
 2. New scripts/check_grading_ready.py (argparse, follow validate_tasks.py's
    style — PROJECT_ROOT sys.path insert, logging): connects to results.db
    (--db option, default results.db), calls core.db.grading_readiness, prints a
    table (axis, distinct passing values, gradeable cells) plus the total
    passer count, and exits 1 if every axis has 0 gradeable_cells, else exits 0.
    Add a `--help` with a one-line example per this project's CLI conventions
    (CLAUDE.md: exit 0 success / 1 expected-failure / 2 usage error; stderr for
    errors, stdout for output).
 3. TDD the script's exit-code logic at minimum (a small pytest hitting its main
    function/argument parsing against a seeded in-memory or temp DB) — mirror
    however scripts/ testing is currently done in this repo (check for an
    existing tests/test_validate_tasks.py-style file first; if none exists,
    keep the test focused on the exit-code branch, not full CLI plumbing).
VERIFY: .venv\Scripts\python.exe -m pytest -q (run the new test file specifically,
    plus confirm `.venv\Scripts\python.exe scripts\check_grading_ready.py --db results.db`
    runs and exits 1 against the current results.db, which has 0 gradeable cells)
COMMIT: ui/scripts: surface why grading has no data, add check_grading_ready pre-flight

========================= BRIEF #4 — reconcile checklist/playbook/README to reality =========================
GOAL: docs/superpowers/recalibration-checklist.md shows A1-A4 all unticked but
marks J1 "NEXT"; README.md "Next up" does the same. Neither reflects that A1 and
A4 actually ran (against results.db + git log) while A2 and A3 never did, and
neither the playbook nor 14-J1-grading-shakedown.md has any check gating J1 on
gradeable data actually existing. Fix the docs to match reality and add the
gate so this can't silently recur.
DEPENDS ON BRIEF #3 (references scripts/check_grading_ready.py by name) — if #3
FAILED, still do this brief but describe the diagnostic as "planned, not yet
built" instead of naming the script.
FILES: docs/superpowers/recalibration-checklist.md ; RECALIBRATION_PLAYBOOK.md ;
       README.md (only the "Next up" bullet list) ;
       recalibration_prompts/14-J1-grading-shakedown.md
DO:
 1. Verify (read-only, do not re-run anything expensive): query results.db (or
    ask a quick script) to confirm A1's spine trials exist (cosmos-A and
    pyvrp-A/B/C oracle/nop trials, one real claude-code trial on cosmos-A) and
    A4's three-model sweep exists (cosmos-A / baseline / none / claude-haiku-4-5,
    claude-sonnet-4-6,claude-opus-4-8 / claude-code). Check git log for the A4
    follow-up fix commits (5c9fea7, df1bfd5, 7a5121d, 686cf00 — match
    21-A4-shakedown-followups.md's three OPEN ISSUEs). Confirm no trial has
    methodology != "baseline" or repo_context != "none" anywhere in results.db
    (i.e. A2/A3 genuinely never ran for real).
 2. In docs/superpowers/recalibration-checklist.md: tick A1 and A4 (with a
    one-line evidence note each, e.g. "- [x] A1 execution spine — verified via
    results.db (cosmos-A/pyvrp oracle+nop+claude-code trials)"). Leave A2 and A3
    unticked. Change the J1 line from "NEXT" to something that reflects it's
    blocked: e.g. "- [ ] J1 grading UI shakedown — **BLOCKED: run A2 + A3 for
    real first, then `scripts/check_grading_ready.py` must report >=1 gradeable
    cell** — CHECKPOINT".
 3. In RECALIBRATION_PLAYBOOK.md's Phase J section, add a one-line prerequisite
    note above the J1 row: real A2 (`08-A2-methodology-axis.md`, drop
    --dry-run) and A3 (`09-A3-repo-context-axis.md`, drop --dry-run) must have
    actually run — not just the shakedown dry-runs — and
    `scripts/check_grading_ready.py --db results.db` must exit 0 (>=1 gradeable
    cell on some axis) before pasting J1. Reference recalibration_prompts/22 as
    where this was diagnosed, so a future reader has the "why."
 4. In README.md's "Next up" list, replace the unconditional "J1 — grading UI
    shakedown (NEXT)" bullet with one that names the actual blocker (A2/A3 not
    yet run for real; 0 gradeable cells in results.db as of 2026-07-01).
 5. In recalibration_prompts/14-J1-grading-shakedown.md, add a "Step 0" before
    the existing "Step 1 — Launch": run `scripts/check_grading_ready.py --db
    results.db` first; if it exits 1, stop and go run A2/A3 for real instead of
    launching the UI.
COMMIT: docs: reconcile checklist/playbook/README to actual Phase A state, gate J1 on real gradeable data

AFTER ALL FOUR: run `.venv\Scripts\python.exe -m pytest -q` ONCE. Then print a
final report: per-brief PASS/FAILED/SKIPPED, the commit SHA for each PASS, and
the full suite pass/deselect count. Then print, verbatim, this reminder (do not
act on it yourself):

  "Redaction bug fixed and a readiness diagnostic now exists, but results.db
  still has 0 gradeable cells — that requires actually spending API budget on
  real trials, which is a human-initiated step in this project (see
  10-A4-model-axis.md / 19-M-calibration-sweep.md for the cost-check
  convention). Next manual step: run 08-A2-methodology-axis.md and
  09-A3-repo-context-axis.md for real (drop --dry-run), watch cost, then
  `scripts/check_grading_ready.py --db results.db` before returning to J1."

Do NOT tick any checklist item beyond what brief #4 already did, and do NOT
start A2/A3 yourself. Stop after the report.
```
