import subprocess
import time
from pathlib import Path

from core.models import MethodologySpec, RepoContextSpec, RunResult, TaskSpec, Trial
from runners.base import collect, lay_down_files


class OracleRunner:
    def __init__(self, task: TaskSpec) -> None:
        self._task = task

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
        ref_path = Path(self._task.reference_diff_path)
        subprocess.run(
            ["git", "apply", str(ref_path.resolve())],
            cwd=str(worktree_path),
            check=True,
            capture_output=True,
            text=True,
        )
        diff = collect(worktree_path)
        return RunResult(
            trial_id=trial.id,
            diff=diff,
            exit_status=0,
            wall_seconds=time.monotonic() - start,
        )
