---
id: dec-0003-tasks-py-template-sync
type: decision
scope: studio/studio
title: tasks.py stays byte-identical to template/tasks.py
summary: 'studio''s own tasks.py is pinned byte-identical to template/tasks.py by a
  sync test; change both together or neither, and never add a fourth command'
status: active
confidence: high
weight: 60
sources: [tests/test_tasks_exit_code.py, conventions/project-shape.md]
created: '2026-08-25'
updated: '2026-08-25'
supersedes: []
superseded_by: null
author: seed
tags: [conventions, tasks-py]
---
`tests/test_tasks_exit_code.py` asserts `tasks.py` is byte-for-byte identical to
`template/tasks.py`, because the template is copied into every studio project and the
studio repo must eat its own cooking. Any edit — including adding a `lint`, `fmt` or
`serve` command, which `conventions/project-shape.md` forbids anyway — must land in
both files or the suite goes red. New tooling belongs inside `check()`, not behind a
new command name.
