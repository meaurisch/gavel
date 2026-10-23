# J1 — Grading UI visual critique (Claude Design)

**Service:** Claude Design.
**Goal:** polish the *visual/interaction* design of the grading UI — distinct
from functional bugs (those go through the CHECKPOINT prompt to Claude Code).
**You do first:** screenshot the grading UI (the pairwise A/B view, the axis
picker, the cascading cell pickers). Have `ui/server.py` and `ui/static/` handy.

---

Paste to Claude Design (attach the screenshots):

```
This is the blind pairwise grading screen of a local benchmarking tool. A human
compares two anonymized code diffs (A vs B) and picks the one they'd merge, or
Tie, advancing with the keyboard. There's an axis picker (what we're comparing:
methodology / model / repo-context / runner) and cascading pickers to pin the
other axes to one "cell". Every axis id is hidden so judging stays blind.

Critique and redesign for fast, fatigue-free, repeated judging:
- Layout of the two diffs for quick side-by-side scanning (long diffs included).
- Clear, unobtrusive display of which comparison axis + cell I'm in, without
  revealing the blinded ids.
- Keyboard-first flow (A / B / Tie / back / skip) with obvious affordances.
- Visual hierarchy, spacing, color for diffs (add/remove), and progress through
  the queue.
- Keep it a simple local static UI (vanilla HTML/CSS/JS served by FastAPI) — no
  heavy framework.

Give me concrete proposed markup/CSS changes I can hand to Claude Code to
implement, plus a short rationale for each change.
```

---

Take Design's proposed changes to Claude Code to implement (TDD where there's
logic; visual-only changes just applied + eyeballed). Keep `tests/test_server.py`
green.
