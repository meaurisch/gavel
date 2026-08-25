---
id: proc-0004-pr-verification-evidence
type: procedure
scope: studio
title: A PR body states what was actually run to verify the change
summary: 'A PR body says what broke, what the fix is, and exactly what was run to
  verify it; if nothing was verified, the body says so outright'
status: active
confidence: high
weight: 85
sources: [conventions/pull-requests.md, 'https://github.com/meaurisch/studio/issues/78']
created: '2026-08-25'
updated: '2026-08-25'
supersedes: []
superseded_by: null
author: seed
tags: [conventions, pull-requests]
---
`conventions/pull-requests.md`: a PR body has three jobs — what broke, what the fix
is, and what was actually run to verify it. "Verified" means naming the command
(`python tasks.py test`, a specific pytest invocation) and its result, not asserting
that things work. A change that was made but not verified is fine to open — the body
just has to say so.

Nothing enforces this, and as of 2026-08-25 the worker's own PR-body template could
not comply (studio#78): the default register everywhere is what-and-why with no
evidence. State the evidence or state its absence.
