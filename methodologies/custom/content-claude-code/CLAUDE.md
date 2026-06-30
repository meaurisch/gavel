# Custom Agentic Setup — Conductor / Executor Discipline

This project uses a structured multi-agent workflow. Do **not** implement
non-trivial changes ad hoc on the main thread — route them through the subagents
defined in `.claude/agents/`.

## Workflow

1. **Plan** — for any non-trivial change, dispatch the **planner** subagent. It
   interviews for scope, explores the codebase, and writes a structured plan to
   `.agent-plans/<timestamp>/plan.md` plus a `PROGRESS.md`. It never edits code.
2. **Implement** — dispatch the **conductor** subagent with the active plan
   directory. The conductor orchestrates the whole implementation:
   - delegates each atomic task to the **executor** subagent (the only agent that
     edits application code),
   - runs the **task-validator** (scoped build + tests) after each task, and the
     **task-reviewer** for risky tasks,
   - after all tasks pass, runs the **overall-validator** (full build + suite) and
     the **overall-reviewer** (cross-task coherence) as the final gate.

   The conductor never edits code itself and retries a failed task at most twice
   before escalating to you.

## Routing

| Change shape | Start with |
|---|---|
| Multi-file feature, refactor, or architecture change | planner → conductor |
| A single, already-specified edit | executor |
| "Is this implementation correct / complete?" | task-reviewer / overall-reviewer |
| "Does it build and pass tests?" | task-validator / overall-validator |

## Discipline

- The executor makes only the change it was asked to make — no unrequested
  refactors or "improvements".
- Validators and reviewers never edit code; they run checks and report.
- Authoritative state lives on disk under `.agent-plans/<timestamp>/`
  (`plan.md`, `PROGRESS.md`, per-task artifacts), not in chat memory — re-read it
  before each decision.
