# M — First calibration sweep (Claude Code) — close-out

**Service:** Claude Code runs; **you** review the result.
**Goal:** the measurement the shakedowns flowed toward — a small real sweep that
lands each task's pass-rate in the discriminative 30–70% band and produces the
first genuine ranking. Uses the settled knobs (reps=3).

---

Paste to Claude Code:

```
Run our first real calibration sweep now that every component is shaken out.

1. Calibrate first: run scripts/calibrate_tasks.py over the golden task set to
   measure each task's pass-rate and report which fall inside the 30–70%
   discrimination band vs too-easy/too-hard. Use a modest sweep (e.g. a couple
   of methodologies x the model set x reps=3) — keep cost sane and tell me the
   projected cost BEFORE running the full thing.
2. Show me the per-task pass-rate bands. For any task outside 30–70%, recommend a
   concrete adjustment (strengthen/loosen tests, sharpen/relax the instruction)
   — but DON'T change a frozen golden task without my OK.
3. Once tasks are in-band, run the measurement sweep with the settled knobs
   (reps=3, max-turns=60), then `report` for the comparison axis we care about.
   Produce the first ranking + CIs + cost frontier + stakes pick.

Report: projected vs actual cost, per-task bands, and the final ranking. Save the
report artifact under reports/.
```

**What YOU review:** is the ranking believable? Are CIs wide (expected at small
n)? Does the stakes pick make sense? Capture anything off in the notepad.

---

After this: run a final **CHECKPOINT**, tick **M**, and the recalibration is
complete. Consider a `bye` to commit/push and update the README "Current state".
