# J3 — Pareto frontier visualization (Claude Design)

**Service:** Claude Design.
**Goal:** design the quality-vs-cost frontier chart that the `report` command
renders, so the tradeoffs the analyzer flags are visible at a glance.
**You do first:** if a draft chart exists from prompt `17`, screenshot it;
otherwise describe the data (below) to Design.

---

Paste to Claude Design (attach any draft chart):

```
I need a single chart that helps me make an adoption decision from a small
benchmark. Each point is one value of a comparison axis (e.g. a methodology:
baseline / karpathy / superpowers / ecc / custom). Axes:
- X = cost in USD (lower is better)
- Y = quality as a Bradley-Terry score, WITH 95% confidence-interval bars
  (overlapping CIs mean "statistically indistinguishable").
Mark the Pareto frontier (best quality for the cost). Highlight two picks: the
quality winner (for high-stakes work) and the cheapest value whose CI overlaps
the winner (for routine work).

Design a clean, readable static chart (this is a local tool; vanilla
JS/SVG/Canvas or a lightweight lib — no heavy framework). Show:
- how to render CI bars without clutter at small n (5–8 points),
- how to visually distinguish on-frontier vs dominated points,
- how to label the two recommended picks unobtrusively,
- a legend a non-statistician can read.

Give me concrete markup/CSS/JS (or a lib choice + config) I can hand to Claude
Code, plus rationale.
```

---

Hand Design's output to Claude Code to implement inside the `report` artifact.
Keep it simple and local. Then finish prompt `17`'s checklist.
