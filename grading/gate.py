"""Held-out-test gate: copies tests into a worktree, runs them, cleans up."""

import shutil
import subprocess
from pathlib import Path

from core.models import GateResult, TaskSpec, Trial
from core.toolchain import needs_wsl, wsl_argv

# Worktree-local ref marking the post-prepare, pre-agent HEAD (the setup baseline
# captured in ClaudeCodeRunner.execute, per 5fb9787). Under refs/worktree/ it is
# scoped to the single worktree, so concurrent trials can't clobber one another.
# The runner writes it; the gate reads it to tell a setup-provenance held-out file
# (a genuine leak) from one the agent produced itself (not a leak).
BASELINE_REF = "refs/worktree/setup-bench-baseline"


def _iter_files(root: Path):
    for p in root.rglob("*"):
        if p.is_file():
            yield p, p.relative_to(root)


def _baseline_sha(worktree_path: Path) -> str | None:
    """The setup baseline SHA if the runner recorded one, else None."""
    result = subprocess.run(
        ["git", "rev-parse", "--verify", "-q", BASELINE_REF],
        cwd=str(worktree_path),
        capture_output=True,
        text=True,
    )
    sha = result.stdout.strip()
    return sha if result.returncode == 0 and sha else None


def _in_tree(worktree_path: Path, sha: str, rel_posix: str) -> bool:
    """True if `rel_posix` exists in the tree of `sha` (i.e. came in via setup)."""
    result = subprocess.run(
        ["git", "cat-file", "-e", f"{sha}:{rel_posix}"],
        cwd=str(worktree_path),
        capture_output=True,
    )
    return result.returncode == 0


def _run_command(cmd: str, cwd: Path, task: TaskSpec) -> tuple[bool, str]:
    if needs_wsl(task):
        result = subprocess.run(
            wsl_argv(cmd, cwd),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
            timeout=900,
        )
    else:
        result = subprocess.run(
            cmd,
            cwd=str(cwd),
            shell=True,
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="ignore",
        )
    return (result.returncode == 0, result.stdout + result.stderr)


def _run_hidden_tests(trial: Trial, worktree_path: Path, task: TaskSpec) -> tuple[bool, str]:
    src = Path(task.held_out_tests_path).resolve()
    dest_root = worktree_path / "tests"

    files = list(_iter_files(src))
    baseline = _baseline_sha(worktree_path)

    # Provenance-aware leakage guard. A held-out path already present in the
    # worktree is only a leak if it came in via the setup commits (it's in the
    # baseline tree, so the model saw it) OR provenance is unprovable (no baseline
    # ref) — both stay fatal. A path present only in the agent's own diff is not a
    # leak: the agent never saw the oracle, which lives outside the worktree until
    # now. The oracle always wins — it overwrites the colliding path below and runs
    # the true test; the agent's content already survives in the captured diff.
    for _, rel in files:
        dest = dest_root / rel
        if not dest.exists():
            continue
        rel_posix = (Path("tests") / rel).as_posix()
        provenance_agent = baseline is not None and not _in_tree(worktree_path, baseline, rel_posix)
        assert provenance_agent, (
            f"held-out test already present in worktree via setup (leak): {dest}"
        )

    created: list[Path] = []
    overwritten: list[tuple[Path, bytes]] = []
    try:
        for abs_src, rel in files:
            dest = dest_root / rel
            if dest.exists():
                overwritten.append((dest, dest.read_bytes()))
            else:
                created.append(dest)
            dest.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(abs_src, dest)  # oracle always wins

        passed, output = _run_command(task.run_cmd, worktree_path, task)
    finally:
        for f in created:
            f.unlink(missing_ok=True)
        for dest, content in overwritten:
            dest.write_bytes(content)  # restore the agent's version

    return (passed, output)


def apply(trial: Trial, worktree_path: Path, task: TaskSpec) -> GateResult:
    result = GateResult(trial_id=trial.id, passed=False)

    if task.build_cmd:
        ok, out = _run_command(task.build_cmd, worktree_path, task)
        result.compile_passed, result.compile_output = ok, out
        if not ok:
            return result

    if task.visible_test_cmd:
        ok, out = _run_command(task.visible_test_cmd, worktree_path, task)
        result.visible_passed, result.visible_output = ok, out

    hidden_ok, hidden_out = _run_hidden_tests(trial, worktree_path, task)
    result.hidden_passed, result.hidden_output = hidden_ok, hidden_out
    result.passed = hidden_ok

    return result
