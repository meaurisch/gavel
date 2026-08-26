---
id: pref-0002-commit-subject-style
type: preference
scope: studio
title: Commit subjects are imperative and at most 70 characters
summary: 'Every commit gets a clear, imperative subject line of at most 70 characters;
  session work is committed, never left dangling in the tree'
status: active
confidence: high
weight: 85
sources: [conventions/session-wrap.md, 'https://github.com/meaurisch/studio/issues/78']
created: '2026-08-25'
updated: '2026-08-25'
supersedes: []
superseded_by: null
author: seed
tags: [conventions, git, session-wrap]
---
`conventions/session-wrap.md` fixes the shape of a commit: an imperative subject of at
most 70 characters, with the why-and-what in the body, referencing issue numbers where
they exist. Nothing enforces this — there is deliberately no commit-msg hook — so it
only holds when the committer applies it.

It is the studio's most-violated convention: on 2026-08-25, 62 of 132 subjects on the
working branch exceeded 70 characters, including the worker's own generated merge
subjects (studio#78). Ecosystem defaults pull toward long descriptive subjects; write
the description in the body instead.
