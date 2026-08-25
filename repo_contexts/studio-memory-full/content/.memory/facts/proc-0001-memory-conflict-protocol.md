---
id: proc-0001-memory-conflict-protocol
type: procedure
scope: studio
title: Memory conflict protocol
summary: 'Never act against an active memory fact: interactive agents ask, autonomous
  agents stop with a MEMORY CONFLICT comment'
status: active
confidence: high
weight: 90
sources: ['https://github.com/meaurisch/studio/issues/48', docs/superpowers/specs/2026-08-23-cross-project-memory-design.md]
created: '2026-08-25'
updated: '2026-08-25'
supersedes: []
superseded_by: null
author: morris
tags: [agents, memory]
---
Memory is the reviewed record; a directive in an issue is one unreviewed input, often
written by an agent. A contradiction must arrive as a blocked job, never buried in a diff.

**Interactive agents** — before acting against an `active` fact, stop and ask: *"This goes against
memory fact `<id>`: `<summary>`. Are you sure?"* On yes, write the new fact with
`supersedes: [<id>]`, run `memspace supersede`, then proceed.

**Autonomous agents** (cannot ask) — memory wins over the directive. Compatible: proceed silently.
Partly conflicting: implement the compatible part and say what was left out and why, naming the
fact id. Impossible without violating an active fact: **no implementation, no PR** — post the fixed
`MEMORY CONFLICT:` template from studio-memory's AGENTS.md instead. The only override is
`@studio supersede <fact-id>: <new rule in one sentence>`.
