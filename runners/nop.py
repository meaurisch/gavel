import time
from pathlib import Path

from core.models import MethodologySpec, RepoContextSpec, RunResult, Trial
from runners.base import capture_baseline, collect, lay_down_files


class NopRunner:
    def prepare(
        self,
        trial: Trial,
        worktree_path: Path,
        methodology: MethodologySpec,
        repo_context: RepoContextSpec,
    ) -> None:
        lay_down_files(worktree_path, repo_context.files, "setup-bench: lay down repo context files")
        lay_down_files(worktree_path, methodology.files, "setup-bench: lay down methodology files")

    def execute(self, trial: Trial, worktree_path: Path) -> RunResult:
        start = time.monotonic()
        baseline = capture_baseline(worktree_path)
        diff = collect(worktree_path, baseline)
        return RunResult(
            trial_id=trial.id,
            diff=diff,
            exit_status=0,
            wall_seconds=time.monotonic() - start,
        )
