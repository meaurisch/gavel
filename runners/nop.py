import time
from pathlib import Path

from core.models import RunResult, SetupSpec, Trial
from runners.base import collect, lay_down_setup_files


class NopRunner:
    def prepare(self, trial: Trial, worktree_path: Path, setup: SetupSpec) -> None:
        lay_down_setup_files(worktree_path, setup)

    def execute(self, trial: Trial, worktree_path: Path) -> RunResult:
        start = time.monotonic()
        diff = collect(worktree_path)
        return RunResult(
            trial_id=trial.id,
            diff=diff,
            exit_status=0,
            wall_seconds=time.monotonic() - start,
        )
