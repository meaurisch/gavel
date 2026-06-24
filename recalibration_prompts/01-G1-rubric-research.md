# G1 — Golden-standard rubric (research)

**Service:** Claude Chat + Research (enable the Research feature).
**Goal:** produce an authoritative, checkable rubric defining what makes a
benchmark *task* "golden" for setup-bench. Output feeds prompt `02`.
**Why Research, not Code:** you want external grounding from eval-design
practice (SWE-bench & friends), not just opinion.

---

Paste to Claude Chat (with Research on):

```
I'm building a small local benchmark that compares agentic coding setups
(methodology packs, models, runners) by having them implement a reverted
feature in a real repo, then gating on held-out tests and grading diffs
blind/pairwise. I need a rigorous, checkable rubric for what makes a single
benchmark TASK "golden" — the gold standard every future task is measured
against.

Research how serious code-evaluation benchmarks design tasks (e.g. SWE-bench
and SWE-bench Verified, Aider's benchmark, LiveCodeBench, and academic work on
discriminative test-set design), and synthesize a rubric covering at least
these facets, each as a CONCRETE pass/fail check I can apply to a task:

1. Task description quality — unambiguous scope, names the entry points,
   states done-criteria, and does NOT leak the intended solution.
2. Instruction language — reads like a real senior-written ticket; plus the
   role of a deliberately UNDER-specified task to probe how setups handle
   ambiguity.
3. Tests — visible vs held-out split; how to strengthen held-out tests beyond
   what the original PR shipped; FAIL_TO_PASS / PASS_TO_PASS / build-gate
   transition validation; guarding against test leakage.
4. Representativeness — the change resembles real cross-layer work, not a toy.
5. Difficulty & calibration — landing a task's pass-rate in a discriminative
   band (~30–70%) so it separates good setups from bad.

Deliver:
- The rubric as a markdown checklist (one checkable line per criterion).
- A short "anti-patterns" list (task smells that make a benchmark task weak).
- 3–5 cited sources I can read further.

Keep it practical and specific to code-implementation tasks. I will paste your
rubric into my repo's task-design guide.
```

---

**After Research answers:** save the rubric text to a scratch file (e.g.
`_scratch/golden-rubric.md`) or just copy it — prompt `02` ingests it into the
repo. Tick "G1 rubric" only after prompt `02` lands it.
