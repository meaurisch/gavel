The studio's own control plane: the project registry (`studio.yaml`), the `studio` CLI
(lifecycle, doctor, conform), and the Pi worker (`studio_worker/` — ideation,
implementation, answers, mergebot, ledger). Python 3.11+, no linter by choice; the
whole gate is `python tasks.py test | run | check` (check = test = `pytest -q`).

Conventions for every studio repo live here under `conventions/` — this repo is both
the rulebook and a project subject to it.
