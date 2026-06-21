"""
Oracle/nop validation for setup-bench tasks.

For each task in tasks/pyvrp-{A,B,C}/:
  - Oracle: create worktree, apply reference.diff, install, run held-out tests -> PASS
  - Nop:    create worktree, install (no diff), run held-out tests -> FAIL

Usage:
    python scripts/validate_tasks.py [--verbose]
"""

import argparse
import logging
import os
import platform
import shutil
import subprocess
import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
TASKS_DIR = PROJECT_ROOT / "tasks"
REPOS_DIR = PROJECT_ROOT / "repos" / "pyvrp"


def _build_env() -> dict[str, str]:
    """Return an env dict ensuring build tools (meson, ninja, etc) are on PATH."""
    env = os.environ.copy()
    venv_bin = Path(sys.executable).parent
    extra = [str(venv_bin)]
    if platform.system() == "Windows":
        git_usr_bin = Path(r"C:\Program Files\Git\usr\bin")
        if git_usr_bin.exists():
            extra.append(str(git_usr_bin))
    env["PATH"] = os.pathsep.join(extra) + os.pathsep + env.get("PATH", "")
    return env

log = logging.getLogger("validate_tasks")


def _load_task(task_dir: Path) -> dict:
    """Minimal key:value loader for task.yaml (avoids PyYAML dependency).

    Handles simple scalar fields and multi-line string values (indicated
    by a trailing '|' on the key line).  Good enough for our task.yaml
    files which only contain flat string fields.
    """
    result = {}
    current_key = None
    current_lines: list[str] = []

    for line in (task_dir / "task.yaml").read_text().splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue

        if not line[0].isspace() and ":" in stripped:
            # Flush previous multi-line key
            if current_key is not None:
                result[current_key] = "\n".join(current_lines).strip()
                current_key = None
                current_lines = []

            key, _, value = stripped.partition(":")
            key = key.strip()
            value = value.strip()

            if value == "|":
                current_key = key
                current_lines = []
            else:
                result[key] = value.strip('"').strip("'")
        elif current_key is not None:
            current_lines.append(stripped)

    if current_key is not None:
        result[current_key] = "\n".join(current_lines).strip()

    return result


def _iter_held_out_files(src: Path):
    for p in src.rglob("*"):
        if p.is_file():
            yield p, p.relative_to(src)


def _create_worktree(base_commit: str) -> Path:
    from core.worktree import create_worktree

    return create_worktree(REPOS_DIR, base_commit)


def _destroy_worktree(wt_path: Path) -> None:
    from core.worktree import destroy_worktree

    destroy_worktree(wt_path)


def _check_build_toolchain() -> bool:
    """Check that meson, a C++ compiler, and pybind11 are likely available."""
    checks = [
        (["meson", "--version"], "meson"),
        (["cmake", "--version"], "cmake (for pybind11)"),
    ]

    # Check for C++ compiler
    import platform

    if platform.system() == "Windows":
        checks.append(
            (["cl", "/?"], "MSVC C++ compiler (run from Developer Command Prompt)")
        )
    else:
        checks.append(
            (["g++", "--version"], "g++ (C++ compiler)")
        )

    missing = []
    for cmd, name in checks:
        try:
            subprocess.run(
                cmd,
                capture_output=True,
                timeout=10,
            )
        except (FileNotFoundError, subprocess.TimeoutExpired):
            missing.append(name)

    if missing:
        log.error(
            "Missing build tools: %s\n\n"
            "PyVRP requires C++ compilation. Install the following:\n"
            "  - meson + ninja: pip install meson-python meson ninja\n"
            "  - pybind11: pip install pybind11\n"
            "  - C++ compiler:\n"
            "    Windows: Install Visual Studio Build Tools (MSVC)\n"
            "    Linux:   sudo apt install g++ build-essential\n"
            "    macOS:   xcode-select --install\n"
            "  - cmake: pip install cmake\n\n"
            "Then re-run this script.",
            ", ".join(missing),
        )
        return False

    return True


def _patch_build_scripts_for_windows(wt_path: Path) -> None:
    """Patch PyVRP's build scripts to work on Windows.

    The upstream build_extensions.py calls `rm -rf` which only works on
    Unix.  Replace the clean() function with a cross-platform equivalent.
    """
    build_ext = wt_path / "buildtools" / "build_extensions.py"
    if not build_ext.exists():
        return

    text = build_ext.read_text()
    old = 'check_call(["rm", "-rf", str(build_dir)])'
    new = (
        "import shutil as _shutil\n"
        "    if build_dir.exists():\n"
        "        _shutil.rmtree(build_dir)"
    )
    if old in text:
        text = text.replace(old, new)
        build_ext.write_text(text)
        log.debug("  Patched build_extensions.py for Windows")


def _install_in_worktree(wt_path: Path) -> bool:
    """Run pip install -e . in the worktree. Returns True on success."""
    log.info("  Installing PyVRP in %s ...", wt_path)
    _patch_build_scripts_for_windows(wt_path)
    result = subprocess.run(
        [sys.executable, "-m", "pip", "install", "-e", ".", "--no-build-isolation"],
        cwd=str(wt_path),
        capture_output=True,
        text=True,
        timeout=600,
        env=_build_env(),
    )
    if result.returncode != 0:
        log.error("  pip install failed:\n%s\n%s", result.stdout[-2000:], result.stderr[-2000:])
        return False
    log.info("  Install succeeded.")
    return True


def _apply_diff(wt_path: Path, diff_path: Path) -> bool:
    """Apply a diff to the worktree. Returns True on success."""
    result = subprocess.run(
        ["git", "apply", str(diff_path.resolve())],
        cwd=str(wt_path),
        capture_output=True,
        text=True,
    )
    if result.returncode != 0:
        log.error("  git apply failed:\n%s", result.stderr)
        return False
    return True


def _copy_held_out_tests(wt_path: Path, held_out_path: Path) -> list[Path]:
    """Copy held-out tests into the worktree's tests/ directory."""
    dest_root = wt_path / "tests"
    created = []
    for abs_src, rel in _iter_held_out_files(held_out_path):
        dest = dest_root / rel
        dest.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(abs_src, dest)
        created.append(dest)
    return created


def _cleanup_held_out_tests(created: list[Path]) -> None:
    for f in created:
        f.unlink(missing_ok=True)


def _run_tests(wt_path: Path, run_cmd: str) -> tuple[bool, str]:
    """Run the test command in the worktree. Returns (passed, output)."""
    if "pytest" in run_cmd:
        run_cmd += ' -o "addopts="'
    result = subprocess.run(
        run_cmd,
        cwd=str(wt_path),
        shell=True,
        capture_output=True,
        text=True,
        timeout=300,
        env=_build_env(),
    )
    output = result.stdout + result.stderr
    return result.returncode == 0, output


def validate_task(task_dir: Path) -> dict:
    """
    Run oracle and nop validation for a single task.
    Returns dict with keys: task_id, oracle_pass, nop_fail, errors.
    """
    task = _load_task(task_dir)
    task_id = task["id"]
    base_commit = task["base_commit"]
    run_cmd = task["run_cmd"]
    diff_path = PROJECT_ROOT / task["reference_diff_path"]
    held_out_path = PROJECT_ROOT / task["held_out_tests_path"]

    results = {"task_id": task_id, "oracle_pass": None, "nop_fail": None, "errors": []}

    # --- Oracle trial ---
    log.info("[%s] Oracle trial: apply reference.diff, run held-out tests", task_id)
    wt_path = None
    try:
        wt_path = _create_worktree(base_commit)

        if not _apply_diff(wt_path, diff_path):
            results["errors"].append("oracle: failed to apply reference.diff")
            return results

        if not _install_in_worktree(wt_path):
            results["errors"].append("oracle: pip install failed (build toolchain?)")
            return results

        created = _copy_held_out_tests(wt_path, held_out_path)
        try:
            passed, output = _run_tests(wt_path, run_cmd)
            results["oracle_pass"] = passed
            if not passed:
                results["errors"].append(f"oracle: tests FAILED (expected PASS)\n{output[-2000:]}")
                log.error("  Oracle FAILED:\n%s", output[-2000:])
            else:
                log.info("  Oracle PASSED")
        finally:
            _cleanup_held_out_tests(created)
    except Exception as exc:
        results["errors"].append(f"oracle: {exc}")
        log.exception("  Oracle error")
    finally:
        if wt_path and wt_path.exists():
            try:
                _destroy_worktree(wt_path)
            except Exception:
                log.warning("  Failed to destroy oracle worktree %s", wt_path)

    # --- Nop trial ---
    log.info("[%s] Nop trial: no diff, run held-out tests", task_id)
    wt_path = None
    try:
        wt_path = _create_worktree(base_commit)

        if not _install_in_worktree(wt_path):
            results["errors"].append("nop: pip install failed (build toolchain?)")
            return results

        created = _copy_held_out_tests(wt_path, held_out_path)
        try:
            passed, output = _run_tests(wt_path, run_cmd)
            results["nop_fail"] = not passed
            if passed:
                results["errors"].append(f"nop: tests PASSED (expected FAIL)\n{output[-2000:]}")
                log.error("  Nop PASSED (should have FAILED)")
            else:
                log.info("  Nop correctly FAILED")
        finally:
            _cleanup_held_out_tests(created)
    except Exception as exc:
        results["errors"].append(f"nop: {exc}")
        log.exception("  Nop error")
    finally:
        if wt_path and wt_path.exists():
            try:
                _destroy_worktree(wt_path)
            except Exception:
                log.warning("  Failed to destroy nop worktree %s", wt_path)

    return results


def main():
    parser = argparse.ArgumentParser(
        description="Validate setup-bench tasks with oracle/nop trials."
    )
    parser.add_argument(
        "--verbose", "-v", action="store_true", help="Enable debug logging."
    )
    parser.add_argument(
        "--task", "-t", type=str, default=None,
        help="Run only a specific task (e.g., pyvrp-A).",
    )
    parser.add_argument(
        "--skip-toolchain-check", action="store_true",
        help="Skip the build toolchain check.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    sys.path.insert(0, str(PROJECT_ROOT))

    if not args.skip_toolchain_check and not _check_build_toolchain():
        sys.exit(2)

    task_dirs = sorted(TASKS_DIR.glob("pyvrp-*"))
    if args.task:
        task_dirs = [d for d in task_dirs if d.name == args.task]
        if not task_dirs:
            log.error("Task %s not found", args.task)
            sys.exit(2)

    all_results = []
    for task_dir in task_dirs:
        result = validate_task(task_dir)
        all_results.append(result)

    # Summary
    print("\n" + "=" * 60)
    print("VALIDATION SUMMARY")
    print("=" * 60)

    all_ok = True
    for r in all_results:
        oracle = "PASS" if r["oracle_pass"] else "FAIL" if r["oracle_pass"] is False else "SKIP"
        nop = "FAIL (correct)" if r["nop_fail"] else "PASS (wrong!)" if r["nop_fail"] is False else "SKIP"
        status = "OK" if r["oracle_pass"] and r["nop_fail"] else "PROBLEM"
        if status != "OK":
            all_ok = False

        print(f"  {r['task_id']:12s}  oracle={oracle:6s}  nop={nop:16s}  [{status}]")
        for err in r["errors"]:
            print(f"    ERROR: {err.split(chr(10))[0]}")

    print("=" * 60)
    if all_ok:
        print("All tasks validated successfully.")
    else:
        print("Some tasks have issues. See above for details.")

    sys.exit(0 if all_ok else 1)


if __name__ == "__main__":
    main()
