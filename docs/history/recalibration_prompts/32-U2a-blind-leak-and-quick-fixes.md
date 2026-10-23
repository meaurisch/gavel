# 32-U2a — URGENT: `.agent-plans` blinding leak + three quick grading-UI fixes

**Context.** The human is mid-CP2 (manual blind grading, ~6 of 49 pairs
judged in an OPEN session on `results.db`). While grading they found that
one methodology's runs commit a `.agent-plans/` folder (planning/progress
files) whose presence in a served diff **immediately identifies the
methodology** — a live blinding leak. A 2026-08-01 aggregate check found
**3 of the 27 stored diffs contain `.agent-plans`**. They also filed three
trivial UI bugs (below).

Work on branch `llm-judge` (or a short-lived branch off it, merged back).
Zero spend. Full CLAUDE.md invariants apply.

## Blinding discipline for THIS session (read twice)

The human judge is mid-blind-session. You may read the DB freely, but you
must not deblind them:

- **Never name** which methodology writes `.agent-plans`, which axis
  values sit behind any pair, or which pair indices are affected — not in
  chat, not in commit messages, not in logs. Aggregate counts only.
- Do not reveal, close, or judge anything in their session.

## Part 1 — Close the leak (serve-side, the real fix)

1. `grading/pairwise.py`: the instruction-file stripper
   (`_is_instruction_file`, `METHODOLOGY_DIR_PREFIXES`) already removes
   methodology-identifying files from served diffs, and the same helper
   governs the reconstructed-originals endpoint. Add `.agent-plans/` (root
   folder, any depth) to the stripped set. The diff-shape proxy is
   computed on the anonymized diff, so it stays consistent automatically.
2. TDD: failing test first (a diff containing a `.agent-plans/...` hunk
   must serve without it; originals endpoint too), then the fix. Add a
   Playwright-level assertion if an existing fixture can carry a
   `.agent-plans` hunk cheaply.
3. Do NOT touch the vendored methodology packs or the runner's diff
   capture to gitignore the folder — packs are frozen at pinned commits
   (instrument change, human OK required). Serve-side stripping fixes
   recorded AND future data. Note the capture-side option in your report
   as a flagged follow-up, nothing more.

## Part 2 — Aggregate audit, then STOP for a human decision

A judgment binds the verdict to the exact content served (constraint:
never silently reinterpret). Stripping changes what those pairs render as,
and worse — for pairs already judged with the folder visible, the human
may have been deblinded at judgment time.

Compute and report ONLY these aggregates:

- How many pairs in the open session involve at least one of the 3
  leaky trials; how many of the ALREADY-JUDGED pairs do.
- Which of the three CP2 cells are affected **by count only** (e.g.
  "cell 1: N pairs affected") — no axis values.

Then present the options and **STOP — the human decides**:

- (a) Purge the affected judged rows (backup `results.db` to `backups/`
  first, CP1.5 precedent), fix serving, re-judge those pairs later —
  noting honestly that the human has already seen the folder on those
  pairs, so re-grading them carries memory contamination anyway.
- (b) Keep all judgments and log the caveat in `docs/measurement-log.md`
  (N judged pairs were served with a methodology-identifying folder
  visible).
- Either way: unjudged pairs are cleanly fixed by Part 1 before the
  human resumes grading.

## Part 3 — Three quick fixes (no design needed)

1. **Shared loading state**: `ui/frontend/src/pages/GradePicker.tsx:368`
   passes one `starting` flag to every `CellRow`, so clicking "Grade
   myself" puts sibling rows' buttons into the loading state too. Track
   WHICH cell is starting; only that button shows it.
2. **"(removed)" placeholder**: `ui/frontend/src/components/ThreeWayView.tsx:24`
   renders the literal text `(removed)` on deleted lines. Drop the text —
   the red deletion styling already says it.
3. **Three-way file header alignment**: the per-file header line built at
   `ui/frontend/src/lib/diff.ts:327` (e.g. `path/File.cs A: modified
   +31 −1 · B: modified +30 −0`) renders left-aligned; center it.

## Done means

- Fast suite green (`pytest`, 462 at last count) + Playwright integration
  suite green (`pytest -m integration tests/test_ui_playwright.py`) —
  the leak fix and UI fixes both touch served/rendered surfaces.
- Frontend rebuilt (`cd ui/frontend && npm run build`).
- `docs/measurement-log.md` gains a leak entry (aggregate numbers only);
  README "Current state" line if warranted; `RESUME-2026-08-01.md`
  progress log updated.
- Part-2 STOP honored: no purge, no caveat entry chosen, until the human
  answers.
- Elevation-brief Part 4 self-check run and reported.
