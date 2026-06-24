# G1 — Integrate the rubric (Claude Code)

**Service:** Claude Code.
**Goal:** fold the Research rubric (from prompt `01`) into the repo's task-design
guide and encode the checkable parts into the validators.
**You do first:** paste the rubric text from prompt `01` in place of
`<<<PASTE RUBRIC>>>`.

---

Paste to Claude Code:

```
Here is a researched "golden task" rubric for our benchmark:

<<<PASTE RUBRIC>>>

Integrate it into setup-bench:

1. Read docs/task-design-guide.md and merge this rubric into it as a clearly
   marked "Golden-standard rubric" section — a checkable list. Keep the
   existing guidance; don't duplicate. Preserve the doc's voice.
2. Read scripts/validate_tasks.py and scripts/calibrate_tasks.py. For any rubric
   criterion that can be checked mechanically (e.g. held-out tests present and
   non-trivial, FAIL_TO_PASS / PASS_TO_PASS / build transitions, leakage scan,
   difficulty field present, instruction non-empty/over-length heuristics),
   add or extend a check. Follow the existing code patterns and add tests under
   tests/ for any new check (TDD: failing test first).
3. Add a short "How to audit a task against the rubric" checklist to
   docs/task-design-guide.md that a human can run by eye for the non-mechanical
   criteria (description quality, language, representativeness).
4. Run `.venv\Scripts\python.exe -m pytest -q` and confirm green. Commit:
   guide changes and validator changes as separate commits, short messages.

Report which criteria are now machine-checked vs left to human audit, so I know
what to eyeball during G2/G3.
```

---

After this lands, tick **G1** in `docs/superpowers/recalibration-checklist.md`.
