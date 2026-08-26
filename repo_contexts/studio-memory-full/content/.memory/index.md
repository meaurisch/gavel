# studio — memory index
The studio: ~17 personal repos (Python/FastAPI, Node/TS, a Raspberry Pi homelab), built solo with coding agents. Conventions live in `meaurisch/studio/conventions`. Entry points are the same everywhere: `python tasks.py test | run | check`.

## Subjects
- ai-newspaper — A personal daily newspaper — book quotes, chapter summaries, curated news, scientific papers — generated into one page per day. FastAPI + SQLite + Jinja2/Tailwind, LLM calls via OpenRouter.
- studio — The studio's own control plane: the project registry (`studio.yaml`), the `studio` CLI (lifecycle, doctor, conform), and the Pi worker (`studio_worker/` — ideation, implementation, answers, mergebot, ledger). Python 3.11+, no linter by choice; the whole gate is `python tasks.py test | run | check` (check = test = `pytest -q`).

## Preferences
- [pref-0001-claude-md-pointer-only] Every repo has both files: CLAUDE.md contains only @AGENTS.md, and AGENTS.md is the single source of agent conventions — #48, docs/superpowers/specs/2026-08-23-cross-project-memory-design.md
- [pref-0002-commit-subject-style] Every commit gets a clear, imperative subject line of at most 70 characters; session work is committed, never left dangling in the tree — conventions/session-wrap.md, #78

## Procedures
- [proc-0001-memory-conflict-protocol] Never act against an active memory fact: interactive agents ask, autonomous agents stop with a MEMORY CONFLICT comment — #48, docs/superpowers/specs/2026-08-23-cross-project-memory-design.md
- [proc-0003-readme-state-refresh] A session that changes what a project is or does updates the README's "Current state" and "Next up" sections before it ends — divergence dies at root — conventions/project-shape.md, conventions/session-wrap.md
- [proc-0004-pr-verification-evidence] A PR body says what broke, what the fix is, and exactly what was run to verify it; if nothing was verified, the body says so outright — conventions/pull-requests.md, #78

## Facts
- [fact-0001-locality-policy] Memory storage is always local git; embeddings local by default; LLM hosted per space (Azure for work, OpenRouter for personal) — #48, docs/superpowers/specs/2026-08-23-cross-project-memory-design.md
