---
id: pref-0001-claude-md-pointer-only
type: preference
scope: studio
title: CLAUDE.md pointer only; conventions live in AGENTS.md
summary: 'Every repo has both files: CLAUDE.md contains only @AGENTS.md, and AGENTS.md
  is the single source of agent conventions'
status: active
confidence: high
weight: 95
sources: ['https://github.com/meaurisch/studio/issues/48', docs/superpowers/specs/2026-08-23-cross-project-memory-design.md,
  'https://github.com/meaurisch/ai-newspaper/issues/10']
created: '2026-08-25'
updated: '2026-08-26'
supersedes: []
superseded_by: null
author: morris
tags: [conventions, agents]
---
`CLAUDE.md` contains one line — `@AGENTS.md` — and nothing else. `AGENTS.md` holds the
actual conventions and is the only one of the two to edit.

This *is* the provider-agnostic route, not an exception to it. Claude Code auto-loads `CLAUDE.md`;
Codex and Gemini load `AGENTS.md`. A pointer makes every agent read the same text, and keeps that
text in a file with no vendor's name on it. "Provider agnostic" is a rule about the content of the
file, not about which filenames may exist.

ai-newspaper#10 proposed this pointer before the rule was settled and was closed with *"Rejected: No
Claude.md as we want to be provider agnostic"*. That decision is superseded by this one, and the repo
now follows the rule: ai-newspaper#18 replaced its generated `CLAUDE.md` with the pointer on
2026-08-25.

**The failure mode to watch for** is not a missing `CLAUDE.md` — it is a *generated* one. `new`
scaffolds a full copy of the studio base prompt into it, so any repo created that way starts in
violation, and the copy drifts from `AGENTS.md` silently because nothing compares them.
