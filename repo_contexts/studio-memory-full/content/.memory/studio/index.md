# studio/studio — memory index
The studio's own control plane: the project registry (`studio.yaml`), the `studio` CLI (lifecycle, doctor, conform), and the Pi worker (`studio_worker/` — ideation, implementation, answers, mergebot, ledger). Python 3.11+, no linter by choice; the whole gate is `python tasks.py test | run | check` (check = test = `pytest -q`).

## Decisions
- [dec-0003-tasks-py-template-sync] studio's own tasks.py is pinned byte-identical to template/tasks.py by a sync test; change both together or neither, and never add a fourth command — tests/test_tasks_exit_code.py, conventions/project-shape.md
