# setup-bench — project facts

- Local-first decision-support tool comparing agentic coding setups across five
  axes (task × methodology × repo-context × model × runner), with a three-tier
  gate, blind pairwise grading, and Bradley-Terry ranking. See `README.md` and
  `IMPLEMENTATION_PLAN.md` for the full design — they are the MINIMUM spec.
- Windows + PowerShell primary. `tasks.ps1` is the interface (Run, Watch, ...).
- Python venv at `.venv` (create it yourself — the clone starts clean); tests via
  `pytest`.
- PyVRP tasks build/test under WSL (Ubuntu); .NET/cosmos tasks need the dotnet
  SDK. The gate auto-dispatches PyVRP into WSL.
- You are in an isolated clone on branch `fable-run`. There is no git remote;
  do not add one and do not push. Commit locally, early and often.
