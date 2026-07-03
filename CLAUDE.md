# gavel (formerly setup-bench) — project facts

- Local-first decision-support tool comparing agentic coding setups across five
  axes (task × methodology × repo-context × model × runner), with a three-tier
  gate (compile → visible → hidden), blind pairwise grading, and Bradley-Terry
  ranking. `README.md` and `IMPLEMENTATION_PLAN.md` are the spec.
- Windows + PowerShell primary. `tasks.ps1` is the interface
  (Setup/Ui/Run/Test/Watch/Grade/Report/Demo/Doctor); it wraps `cli.py`.
- The web UI (`python cli.py ui`, port 8247) is the single entry point:
  dashboard, blind grading, run launcher, trial browser, report. It's a
  Vite/React/TS SPA in `ui/frontend/` (built by `cli.py setup`, needs Node 18+)
  served by FastAPI (`ui/server.py`). Styling comes exclusively from the Gavel
  design tokens (`ui/frontend/src/tokens.css`, light + dark) — don't hardcode
  colors/fonts in components.
- Python venv at `.venv`; tests via `pytest` (full suite must stay green).
  Browser regression tests live behind the `integration` marker
  (`pytest -m integration tests/test_ui_playwright.py`, needs
  `python -m playwright install chromium`) — run them after ANY change to the
  UI, they assert the diff-layout and blinding invariants.
  A fresh clone needs `python cli.py setup` once — it clones the task repos,
  deterministically rebuilds the synthesized task-base commits (see
  `tasks/_repo_setup/repos.lock.yaml`), and builds the frontend.
  `python cli.py doctor` checks readiness.
- PyVRP tasks build/test under WSL (Ubuntu); .NET/cosmos tasks need the dotnet
  SDK 8. The gate auto-dispatches PyVRP into WSL. `python cli.py demo` seeds a
  synthetic DB so the grading UI and report can be exercised with zero spend.
- Protected invariants: the model never sees the held-out oracle (leakage
  scanner + provenance-aware collision handling in `grading/gate.py`); nothing
  served during blind comparison may reveal the varying axis — one redaction
  implementation (`grading/pairwise.redact_axis_ids`) covers diffs, gate logs,
  and reconstructed originals, comparison metrics are coarsened and withheld on
  the model/runner axes, and revealing a session closes it permanently
  (`grading_session.revealed_at`); frozen golden tasks only change with an
  explicit human OK.
- Running real trials with the `claude-code` runner spends real API budget —
  prefer the free `oracle`/`nop`/`manual` runners and the demo DB for pipeline
  work; keep paid sweeps minimal and deliberate. The browser run-launcher
  enforces this (typed SPEND confirmation).
