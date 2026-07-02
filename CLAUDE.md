# setup-bench — project facts

- Local-first decision-support tool comparing agentic coding setups across five
  axes (task × methodology × repo-context × model × runner), with a three-tier
  gate (compile → visible → hidden), blind pairwise grading, and Bradley-Terry
  ranking. `README.md` and `IMPLEMENTATION_PLAN.md` are the spec.
- Windows + PowerShell primary. `tasks.ps1` is the interface
  (Setup/Run/Test/Watch/Grade/Report/Demo/Doctor); it wraps `cli.py`.
- Python venv at `.venv`; tests via `pytest` (full suite must stay green).
  A fresh clone needs `python cli.py setup` once — it clones the task repos and
  deterministically rebuilds the synthesized task-base commits (see
  `tasks/_repo_setup/repos.lock.yaml`). `python cli.py doctor` checks readiness.
- PyVRP tasks build/test under WSL (Ubuntu); .NET/cosmos tasks need the dotnet
  SDK 8. The gate auto-dispatches PyVRP into WSL. `python cli.py demo` seeds a
  synthetic DB so the grading UI and report can be exercised with zero spend.
- Protected invariants: the model never sees the held-out oracle (leakage
  scanner + provenance-aware collision handling in `grading/gate.py`); blinded
  diffs must not reveal any axis id (`grading/pairwise.anonymize_diff`); frozen
  golden tasks only change with an explicit human OK.
- Running real trials with the `claude-code` runner spends real API budget —
  prefer the free `oracle`/`nop`/`manual` runners and the demo DB for pipeline
  work; keep paid sweeps minimal and deliberate.
