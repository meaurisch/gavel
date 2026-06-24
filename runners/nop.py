import time
from pathlib import Path

from core.models import MethodologySpec, RunResult, Trial
from runners.base import collect, lay_down_files


class NopRunner:
    def prepare(self, trial: Trial, worktree_path: Path, methodology: MethodologySpec) -> None:
        lay_down_files(worktree_path, methodology.files, "setup-bench: lay down methodology files")

    def execute(self, trial: Trial, worktree_path: Path) -> RunResult:
        start = time.monotonic()
        diff = collect(worktree_path)
        return RunResult(
            trial_id=trial.id,
            diff=diff,
            exit_status=0,
            wall_seconds=time.monotonic() - start,
        )
