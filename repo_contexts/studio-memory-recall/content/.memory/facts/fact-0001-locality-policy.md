---
id: fact-0001-locality-policy
type: fact
scope: studio
title: Locality policy
summary: Memory storage is always local git; embeddings local by default; LLM hosted
  per space (Azure for work, OpenRouter for personal)
status: active
confidence: high
weight: 70
sources: ['https://github.com/meaurisch/studio/issues/48', docs/superpowers/specs/2026-08-23-cross-project-memory-design.md]
created: '2026-08-25'
updated: '2026-08-25'
supersedes: []
superseded_by: null
author: morris
tags: [memory, privacy]
---
Locality is a property of a *space*, declared in `memory.yaml`, with three legs:
storage (always local git), embeddings (local by default) and LLM (hosted per space —
`hosted:azure` for work data, `hosted:openrouter` for personal). A tool must refuse to run a step
whose provider is stricter than the space policy allows; it never silently falls back.

The `studio` space is coding memory, so its remote is GitHub — that is what lets `context_repos`
mount it read-only into Pi jobs. A personal space would be a local-only repo (PC↔Pi over Tailscale,
or inside the vault) and never on GitHub.
