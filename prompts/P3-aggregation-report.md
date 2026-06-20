# P3 — Aggregation, frontier, decision rollup

> **Studio adjustment.** Wire `cli.py report` into `tasks.ps1` if you want a
> `tasks.ps1 Report` shortcut. Charts → studio's `matplotlib` convention; the
> HTML report is a self-contained artifact. Multi-file analysis step —
> `studio-conductor` plans the rollup, `studio-executor` implements.

```
Implement grading/aggregate.py and cli.py `report`. From results.db:
1. Quality: per (task, model), build a win matrix over setups from the pairwise judgments; collapse reps — if a setup's pairwise result flips across reps, score that pair a TIE. Produce a per-setup "wins / ties / losses across tasks" summary and an overall preponderance ranking (no p-values; report direction and consistency).
2. Cost: per (setup, model, task), median USD-equivalent across reps, plus native units (usd_imputed for Claude, credits for Copilot). Roll up to per-setup cost.
3. Frontier: plot quality-rank vs cost; identify the Pareto-non-dominated setups.
4. Decision: apply the stakes rule — for tasks tagged high-stakes (auth/data/money), pick the quality winner regardless of cost; for routine tasks, pick the cheapest setup that is quality-indistinguishable (tie or better) from the winner. Output a single recommended setup per stakes tier, with the evidence behind it.
Render as an HTML report (tables + the frontier scatter). Show me the report for the data so far.
```
