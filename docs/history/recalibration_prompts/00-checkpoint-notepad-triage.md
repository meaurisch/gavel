# CHECKPOINT — Notepad triage & fix  (reusable)

**Service:** Claude Code (use **Claude Cowork** first only if the notepad dump is very long — see bottom).
**When:** at every checkpoint marked in `RECALIBRATION_PLAYBOOK.md` and `docs/superpowers/recalibration-checklist.md`.
**You do first:** paste your raw notepad notes into Claude Code in place of `<<<PASTE NOTES>>>`.

---

Paste to Claude Code:

```
We just finished a testing block in the setup-bench project. Here are the raw
notes I took while using it — everything I found broken, ugly, confusing, or
slow:

<<<PASTE NOTES>>>

Do this:
1. Triage every note into exactly one bucket: BUG (wrong/broken behavior),
   UGLY (works but poor UX/output/wording/formatting), or ENHANCEMENT (new
   capability, not a defect). Show the triage as a table.
2. For BUG and UGLY items, propose the smallest correct fix for each, with the
   exact file(s) and a one-line approach. Do NOT fix yet.
3. Flag any item that is actually a symptom of a deeper design issue rather
   than a local fix — call those out separately.
4. Wait for my go-ahead, then fix all BUG + UGLY items using TDD where code is
   involved (write/adjust a failing test first), run the relevant tests, and
   commit each logical fix separately with a short message.
5. Append every ENHANCEMENT to a running backlog at
   `docs/superpowers/recalibration-backlog.md` (create it if missing) — do not
   implement enhancements now; we stay focused on the current phase.

After fixing, run the full suite (`.venv\Scripts\python.exe -m pytest -q`) and
report the result before we move to the next block. Then tick the relevant
checkpoint in `docs/superpowers/recalibration-checklist.md`.
```

---

**Large dump? Pre-structure with Claude Cowork.** If the notepad is long/messy,
paste it into Claude Cowork first with: *"Group these raw testing notes into
BUG / UGLY / ENHANCEMENT, deduplicate, and order each group by severity. Return
a clean markdown table I can hand to an engineer."* Then paste Cowork's table
into the Claude Code prompt above instead of the raw notes.
