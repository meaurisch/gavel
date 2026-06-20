import time
from pathlib import Path

from core.models import RunResult, SetupSpec, TaskSpec, Trial
from runners.base import collect, lay_down_setup_files


class ManualRunner:
    def __init__(self, task: TaskSpec) -> None:
        self._task = task

    def prepare(self, trial: Trial, worktree_path: Path, setup: SetupSpec) -> None:
        lay_down_setup_files(worktree_path, setup)

    def execute(self, trial: Trial, worktree_path: Path) -> RunResult:
        start = time.monotonic()
        print("=" * 50)
        print(f"MANUAL TRIAL: {trial.id}")
        print(f"Open this directory in your IDE:")
        print(f"  {worktree_path}")
        print()
        print(f"Complete the following task:")
        print(f"  {self._task.instruction}")
        print()
        input("Press Enter when finished...")
        print("=" * 50)
        diff = collect(worktree_path)
        return RunResult(
            trial_id=trial.id,
            diff=diff,
            exit_status=0,
            wall_seconds=time.monotonic() - start,
        )
