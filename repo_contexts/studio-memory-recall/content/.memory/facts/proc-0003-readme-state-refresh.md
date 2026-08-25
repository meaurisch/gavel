---
id: proc-0003-readme-state-refresh
type: procedure
scope: studio
title: README "Current state" and "Next up" are refreshed in the session that changes them
summary: 'A session that changes what a project is or does updates the README''s
  "Current state" and "Next up" sections before it ends — divergence dies at root'
status: active
confidence: high
weight: 85
sources: [conventions/project-shape.md, conventions/session-wrap.md,
  'https://github.com/meaurisch/studio/issues/78']
created: '2026-08-25'
updated: '2026-08-25'
supersedes: []
superseded_by: null
author: seed
tags: [conventions, readme, session-wrap]
---
Every studio README carries four sections; "Current state" and "Next up" are the two
that describe the project *now*, and the rule (`conventions/project-shape.md`,
`conventions/session-wrap.md`) is that whoever changes the state updates them in the
same session — human or agent, feature or fix.

`studio doctor` measures staleness (>15 commits or >300 changed lines since the README
was last touched) but only advises; no gate blocks a stale README. In practice only 7
of 133 commits on the working branch touched README.md (studio#78) — no ecosystem
convention expects a README edit per change, so an agent must be told, or remember.
