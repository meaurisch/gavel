# Research-Driven Evolution of setup-bench

**Date:** 2026-06-24
**Status:** Approved for execution

## Context

setup-bench is a local-first benchmarking framework for comparing agentic coding
setups across harnesses, models, and tasks. After a meeting with a colleague,
several architectural improvements were identified. Rather than implementing them
directly from assumptions, the approach is research-first: investigate how the
evaluation community (Claude Code evals, SWE-bench, academic literature) handles
these problems, then derive implementation decisions from findings.

## Key Intentions (to be validated against research)

These are the directions agreed during brainstorming. The research may confirm,
refine, or redirect any of them.

### 1. Split "setup" axis into Methodology + Repo-Context

Currently the trial matrix has 4 axes: Harness × Setup × Model × Task. "Setup"
conflates methodology packs (superpowers, karpathy, ecc) with repo-specific
instructions. The intention is to split into 5 axes so these can vary
independently.

**Open questions for research:**
- How do other benchmarks handle the distinction between "system-level
  instructions" and "repo-specific context"?
- Is there prior art on managing combinatorial explosion in multi-axis eval
  frameworks?

### 2. Three soft gates with scorecard

Currently there's one hard gate (held-out tests). The intention is three soft
gates: compile, visible tests, hidden tests. All trials enter grading regardless;
gate results shown as a scorecard alongside each diff.

**Open questions for research:**
- How does SWE-bench gate trials? Hard or soft?
- What gate structure produces the most discriminative evaluations?
- Is a compile gate worth the implementation cost, or do test failures already
  capture compilation issues?

### 3. Multi-rep pairwise grading with balanced sampling

Currently pairwise grading only uses rep 0. The intention is random L-from-K×K
sampling with balanced rep usage, showing win/loss/tie tallies per matchup. No
statistical significance numbers — the tool is framed as "decision support, not
clinical trial."

**Open questions for research:**
- How does SWE-bench handle non-determinism? Do they use pass@k?
- What does the literature say about the minimum number of repetitions needed for
  reliable signal in code generation tasks?
- Are there better aggregation strategies than pairwise comparison for this use
  case?

### 4. API-rate USD as primary cost metric

Currently Claude self-reports USD. The intention is to compute cost from token
counts × published API rates, making cost comparable across models.

**Open questions for research:**
- How do other benchmarks report cost? Tokens, USD, or both?
- Is there a standard approach for cost-quality frontier analysis?

### 5. Test set quality and task design

Currently there are 3 PyVRP tasks. The intention is to research best practices
and potentially build tooling to help create good evaluation tasks.

**Open questions for research:**
- What makes an evaluation task discriminative (separates good setups from bad)?
- How does SWE-bench select and validate tasks?
- What is Claude Code's eval task format and what can we learn from it?
- What pitfalls should we avoid in task design?

### 6. README framing

The project should be framed as a "decision support tool, not a clinical trial."
Reps catch variance, blind comparisons give qualitative signal, scorecards
provide objective signals, cost adds another dimension.

## Deliverables

### Prompt 1: Research (Claude Chat, Research Mode)

See `prompts/P3.0-research-eval-frameworks.md`

### Prompt 2: Derive Implementation Prompts (Claude Code)

See `prompts/P3.1-derive-implementation-prompts.md`

## Execution Flow

```
Prompt 1 (Claude Chat, Research Mode)
  → produces: docs/research-eval-frameworks.md
  → user reviews the report

Prompt 2 (Claude Code)
  → reads: docs/research-eval-frameworks.md + codebase + this spec
  → produces: prompts/P3.2-*.md (one per action point)
  → user critically reviews each generated prompt before executing
```
