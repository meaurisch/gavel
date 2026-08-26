---
paths:
- tasks.py
- template/tasks.py
---
# [dec-0003-tasks-py-template-sync] tasks.py stays byte-identical to template/tasks.py

studio's own tasks.py is pinned byte-identical to template/tasks.py by a sync test; change both together or neither, and never add a fourth command

Mirror any change to tasks.py into template/tasks.py, and vice versa, in the same commit.
