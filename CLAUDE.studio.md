<!-- Generated: 2026-06-20 -->
<!-- Sources: base.md, python-script.md, cli-tool.md, agent-mode.md -->

# Base — Always Included

- Always keep the README up to date, reflecting the exact current state of the project
- README must always have these sections: **What it is** | **How to run it** | **Current state** | **Next up**
- Every project must have a `tasks.ps1` with at minimum `Run` and `Watch` functions — the interface is always the same regardless of language
- Prefer clarity over cleverness — straightforward code beats clever abstractions
- This is a personal creative project — keep commit messages short and human
- `_scratch/` exists in the studio root for throwaway experiments — no git, no structure, no pressure
- All GitHub repos are private
- Use modular folder structure once a project grows past a few files
- Favor well-known frameworks: Flask/FastAPI for Python backends, Express for Node.js, Streamlit for data apps
- Always include a `.gitignore` appropriate to the stack
- Environment config goes in `.env` files — never commit secrets

# Python Script

- Always use a venv: `python -m venv .venv` — activate before installing anything
- Pin dependencies in `requirements.txt` — use `pip freeze > requirements.txt` after adding packages
- Entry point should be runnable as `python main.py`
- Use `argparse` for any script that takes arguments
- Use `logging` instead of bare `print()` for status messages — configure level via `--verbose`
- For API integrations: `anthropic`, `openai`, or `requests` — these are your go-to libraries
- Data work: `pandas` for tabular data, `matplotlib` for charts, `streamlit` for interactive dashboards
- Testing: `pytest` with a `tests/` folder — separate unit and integration tests
- Type hints on function signatures — Pydantic models for structured data

# CLI Tool

- Python CLIs: use `argparse` with clear help text for every argument
- Node.js CLIs: use `process.argv` or `commander` — keep dependencies minimal
- Always implement `--help` that explains what the tool does and shows examples
- Exit code 0 on success, 1 on expected errors, 2 on usage errors
- Print errors to stderr, output to stdout — so piping works correctly
- If a CLI wraps an API (Anthropic, OpenAI, etc.), support `--verbose` for raw responses
- Long-running operations should print progress — don't go silent for more than a few seconds

# Agent Mode — Conductor / Executor

This project opts into the two-model Studio agent pattern. Use these two subagents (defined globally at `~/.claude/agents/`) instead of doing everything on the main thread:

- **studio-conductor** (Opus 4.6) — planning, architecture, multi-file changes, unknown bugs, milestone breakdowns. Slow and expensive; use when judgment matters.
- **studio-executor** (Sonnet 4.6) — implementation loops, single-file edits, running the dev server, iterating on test output. Fast and cheap; use for everything the conductor has already planned.

## Routing rules

| Request shape | Route to |
|---|---|
| "Add a feature that touches more than one file" | conductor → then executor per step |
| "Fix this typo / rename this var / add this import" | executor (or main thread) |
| "Design the data model for X" | conductor |
| "Run the tests and fix whatever breaks" | executor |
| "Something is broken and I don't know why" | conductor (needs diagnosis) |
| "Ship this milestone fast" | conductor plans the milestone, executor ships each step |

## Default behavior on this project

- Always start non-trivial requests by delegating to **studio-conductor** for a plan, even if the user didn't ask for one. Show the plan, get a "yes", then hand off.
- For tight iteration loops (server running, testing, adjusting), stay on **studio-executor** and don't re-plan every change.
- If the user pushes back on the conductor's plan, iterate on the plan before executing — don't silently override it mid-execution.
- Cost awareness: if you can reasonably do a request on the main thread without invoking Opus, do that. Agent-mode is opt-in per project because it's not free.

## What agent-mode does NOT change

- Skills still apply globally. The conductor and executor both use `studio-debug`, `studio-ship`, `studio-pi-deploy`, etc. when triggered.
- `tasks.ps1`, README conventions, and `.env` handling are unchanged.
- `bye` still commits and pushes. The learn hook still runs if enabled.
