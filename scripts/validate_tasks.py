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
import re
import shutil
import subprocess
import sys
from collections import namedtuple
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


# --- Static rubric lint (no build toolchain required) ---------------------
#
# These checks implement the machine-checkable subset of the golden-task rubric
# in docs/task-design-guide.md. They are pure (operate on already-loaded data)
# so they run cross-platform without worktrees, builds, or WSL. The remaining
# rubric criteria (spec unambiguity, mutation adequacy, contamination) are left
# to human audit per the guide.

Check = namedtuple("Check", "name status detail")  # status: PASS | WARN | FAIL

REQUIRED_FIELDS = (
    "id", "base_commit", "instruction", "run_cmd",
    "held_out_tests_path", "reference_diff_path", "build_cmd",
)
INSTRUCTION_MIN_CHARS = 40
INSTRUCTION_MAX_WORDS = 280


def check_required_fields(task: dict) -> Check:
    """Facet 1: every task.yaml field a runnable task needs is present + non-empty."""
    missing = [
        f for f in REQUIRED_FIELDS
        if not str(task.get(f, "")).strip()
    ]
    if missing:
        return Check("required_fields", "FAIL", f"missing/empty: {', '.join(missing)}")
    return Check("required_fields", "PASS", "")


def check_instruction_length(instruction: str) -> Check:
    """Facet 1/2: the ticket is non-empty and not bloated into a spec-dump."""
    text = (instruction or "").strip()
    if len(text) < INSTRUCTION_MIN_CHARS:
        return Check("instruction_length", "FAIL", f"too short (<{INSTRUCTION_MIN_CHARS} chars)")
    words = len(text.split())
    if words > INSTRUCTION_MAX_WORDS:
        return Check(
            "instruction_length", "WARN",
            f"long ({words} words) - over-specification smell",
        )
    return Check("instruction_length", "PASS", "")


def check_held_out_nontrivial(held_out_dir: Path) -> Check:
    """Facet 3: held-out tests exist and actually assert behaviour."""
    if not held_out_dir.exists():
        return Check("held_out_nontrivial", "FAIL", f"missing dir: {held_out_dir}")
    test_files = [
        p for p in held_out_dir.rglob("*.py")
        if p.is_file() and ("test" in p.name.lower())
    ]
    if not test_files:
        return Check("held_out_nontrivial", "FAIL", "no test_*.py files found")
    for p in test_files:
        text = p.read_text(encoding="utf-8", errors="ignore")
        if "assert" in text and re.search(r"def\s+test", text):
            return Check("held_out_nontrivial", "PASS", "")
    return Check(
        "held_out_nontrivial", "FAIL",
        "test files present but no `def test...`/`assert` - too weak",
    )


def check_reference_diff(diff_text: str) -> Check:
    """Facet 4: a real, cross-layer diff (multi-file is more discriminative)."""
    text = diff_text or ""
    files = re.findall(r"^\+\+\+ b/", text, flags=re.MULTILINE)
    if not files:
        return Check("reference_diff", "FAIL", "empty or not a unified diff")
    if len(files) < 2:
        return Check(
            "reference_diff", "WARN",
            "touches a single file - may be a toy/kata, not cross-layer",
        )
    return Check("reference_diff", "PASS", f"{len(files)} files")


def check_instruction_leakage(instruction: str) -> Check:
    """Facet 1: the ticket must not embed the solution as a patch or code block.

    Naming the *public* deliverable (e.g. ``ReplaceGroup``) is the spec, not
    leakage — so we flag diff/patch syntax and fenced code blocks, never bare
    identifier mentions.
    """
    text = instruction or ""
    markers = ("diff --git", "@@ ", "+++ b/", "--- a/")
    hit = next((m for m in markers if m in text), None)
    if hit:
        return Check("instruction_leakage", "FAIL", f"contains patch syntax: {hit!r}")
    if re.search(r"```", text):
        return Check("instruction_leakage", "FAIL", "contains a fenced code block")
    return Check("instruction_leakage", "PASS", "")


def check_difficulty_present(task: dict) -> Check:
    """Facet 5: difficulty should be logged as metadata (labelled post-calibration)."""
    if str(task.get("difficulty", "")).strip():
        return Check("difficulty", "PASS", "")
    return Check(
        "difficulty", "WARN",
        "no difficulty field - label by hand after a calibration sweep",
    )


def lint_task(task_dir: Path) -> dict:
    """Run all static rubric checks for one task. Returns {task_id, checks}."""
    task = _load_task(task_dir)
    diff_path = PROJECT_ROOT / task.get("reference_diff_path", "")
    diff_text = diff_path.read_text(encoding="utf-8", errors="ignore") if diff_path.is_file() else ""
    held_out_dir = PROJECT_ROOT / task.get("held_out_tests_path", "")
    checks = [
        check_required_fields(task),
        check_instruction_length(task.get("instruction", "")),
        check_held_out_nontrivial(held_out_dir),
        check_reference_diff(diff_text),
        check_instruction_leakage(task.get("instruction", "")),
        check_difficulty_present(task),
    ]
    return {"task_id": task.get("id", task_dir.name), "checks": checks}


def render_lint_summary(all_results: list[dict]) -> tuple[str, bool]:
    """Render the static-lint summary. ok is False iff any check FAILs (WARNs allowed)."""
    lines = ["", "=" * 60, "STATIC RUBRIC LINT SUMMARY", "=" * 60]
    all_ok = True
    for r in all_results:
        checks = r["checks"]
        has_fail = any(c.status == "FAIL" for c in checks)
        has_warn = any(c.status == "WARN" for c in checks)
        if has_fail:
            all_ok = False
            status = "PROBLEM"
        elif has_warn:
            status = "WARN"
        else:
            status = "OK"
        lines.append(f"  {r['task_id']:12s}  [{status}]")
        for c in checks:
            if c.status != "PASS":
                lines.append(f"    {c.status}: {c.name} - {c.detail}")
    lines.append("=" * 60)
    lines.append(
        "All tasks pass the static rubric checks." if all_ok
        else "Some tasks FAIL static rubric checks. See above."
    )
    return "\n".join(lines), all_ok


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


def _run_build(wt_path: Path, build_cmd: str) -> tuple[bool, str]:
    """Run a build command in the worktree. Returns (succeeded, output)."""
    result = subprocess.run(
        build_cmd,
        cwd=str(wt_path),
        shell=True,
        capture_output=True,
        text=True,
        timeout=600,
        env=_build_env(),
    )
    return result.returncode == 0, result.stdout + result.stderr


def _validate_build_gate(task: dict) -> tuple[bool | None, str]:
    """build_cmd must succeed on the clean base commit. None if no build_cmd."""
    build_cmd = task.get("build_cmd")
    if not build_cmd or build_cmd == "null":
        return None, "no build_cmd"
    wt_path = None
    try:
        wt_path = _create_worktree(task["base_commit"])
        _patch_build_scripts_for_windows(wt_path)
        return _run_build(wt_path, build_cmd)
    finally:
        if wt_path and wt_path.exists():
            try:
                _destroy_worktree(wt_path)
            except Exception:
                log.warning("  Failed to destroy build-gate worktree %s", wt_path)


def _validate_fail_to_pass(task: dict) -> tuple[bool, str]:
    """Hidden tests must FAIL on the clean base commit (no changes).

    Returns (check_passed, output): check_passed is True when the tests FAIL,
    which proves they actually require the feature.
    """
    held_out_path = PROJECT_ROOT / task["held_out_tests_path"]
    wt_path = None
    try:
        wt_path = _create_worktree(task["base_commit"])
        if not _install_in_worktree(wt_path):
            return False, "install failed on clean base commit"
        created = _copy_held_out_tests(wt_path, held_out_path)
        try:
            tests_passed, output = _run_tests(wt_path, task["run_cmd"])
        finally:
            _cleanup_held_out_tests(created)
        return (not tests_passed), output
    finally:
        if wt_path and wt_path.exists():
            try:
                _destroy_worktree(wt_path)
            except Exception:
                log.warning("  Failed to destroy fail-to-pass worktree %s", wt_path)


def _validate_pass_to_pass_with_gold(task: dict) -> tuple[bool, str]:
    """Hidden tests must PASS after applying the reference (gold) diff.

    Returns (check_passed, output): check_passed is True when the tests PASS.
    """
    held_out_path = PROJECT_ROOT / task["held_out_tests_path"]
    diff_path = PROJECT_ROOT / task["reference_diff_path"]
    wt_path = None
    try:
        wt_path = _create_worktree(task["base_commit"])
        if not _apply_diff(wt_path, diff_path):
            return False, "failed to apply reference.diff"
        if not _install_in_worktree(wt_path):
            return False, "install failed with gold patch"
        created = _copy_held_out_tests(wt_path, held_out_path)
        try:
            tests_passed, output = _run_tests(wt_path, task["run_cmd"])
        finally:
            _cleanup_held_out_tests(created)
        return tests_passed, output
    finally:
        if wt_path and wt_path.exists():
            try:
                _destroy_worktree(wt_path)
            except Exception:
                log.warning("  Failed to destroy pass-to-pass worktree %s", wt_path)


def validate_transitions(task_dir: Path) -> dict:
    """Run build-gate, FAIL_TO_PASS, and PASS_TO_PASS(gold) checks for one task."""
    task = _load_task(task_dir)
    task_id = task["id"]
    result = {
        "task_id": task_id, "build_gate": None,
        "fail_to_pass": None, "pass_to_pass": None, "errors": [],
    }

    log.info("[%s] Build gate: build_cmd succeeds on clean base", task_id)
    try:
        bg, out = _validate_build_gate(task)
        result["build_gate"] = bg
        if bg is False:
            result["errors"].append(f"build gate: FAILED on clean base\n{out[-2000:]}")
            log.error("  Build gate FAILED:\n%s", out[-2000:])
    except Exception as exc:
        result["errors"].append(f"build gate: {exc}")
        log.exception("  Build gate error")

    log.info("[%s] FAIL_TO_PASS: hidden tests fail on clean base", task_id)
    try:
        ftp, out = _validate_fail_to_pass(task)
        result["fail_to_pass"] = ftp
        if not ftp:
            result["errors"].append(
                f"FAIL_TO_PASS: tests PASSED on clean base (tests too weak)\n{out[-2000:]}"
            )
            log.error("  FAIL_TO_PASS problem (tests passed on base):\n%s", out[-2000:])
    except Exception as exc:
        result["errors"].append(f"FAIL_TO_PASS: {exc}")
        log.exception("  FAIL_TO_PASS error")

    log.info("[%s] PASS_TO_PASS: hidden tests pass with gold patch", task_id)
    try:
        ptp, out = _validate_pass_to_pass_with_gold(task)
        result["pass_to_pass"] = ptp
        if not ptp:
            result["errors"].append(
                f"PASS_TO_PASS: tests FAILED with gold patch (tests or diff broken)\n{out[-2000:]}"
            )
            log.error("  PASS_TO_PASS problem (tests failed with gold):\n%s", out[-2000:])
    except Exception as exc:
        result["errors"].append(f"PASS_TO_PASS: {exc}")
        log.exception("  PASS_TO_PASS error")

    return result


def render_transitions_summary(all_results: list[dict]) -> tuple[str, bool]:
    """Render the transition-validation summary. Returns (text, all_ok)."""
    lines = ["", "=" * 60, "TRANSITION VALIDATION SUMMARY", "=" * 60]
    all_ok = True
    for r in all_results:
        bg = r["build_gate"]
        build = "PASS" if bg else ("SKIP" if bg is None else "FAIL")
        ftp = (
            "FAIL (correct)" if r["fail_to_pass"]
            else "PASS (too weak!)" if r["fail_to_pass"] is False
            else "SKIP"
        )
        ptp = (
            "PASS" if r["pass_to_pass"]
            else "FAIL (broken!)" if r["pass_to_pass"] is False
            else "SKIP"
        )
        ok = (bg is not False) and bool(r["fail_to_pass"]) and bool(r["pass_to_pass"])
        if not ok:
            all_ok = False
        status = "OK" if ok else "PROBLEM"
        lines.append(
            f"  {r['task_id']:12s}  build={build:5s}  F2P={ftp:16s}  P2P={ptp:14s}  [{status}]"
        )
        for err in r["errors"]:
            lines.append(f"    ERROR: {err.split(chr(10))[0]}")
    lines.append("=" * 60)
    lines.append(
        "All transitions validated successfully." if all_ok
        else "Some tasks have transition problems. See above for details."
    )
    return "\n".join(lines), all_ok


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
    parser.add_argument(
        "--validate-transitions", action="store_true",
        help="Run FAIL_TO_PASS / PASS_TO_PASS / build-gate checks instead of oracle/nop.",
    )
    parser.add_argument(
        "--lint", action="store_true",
        help="Run static rubric checks (no build needed) instead of oracle/nop.",
    )
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s %(message)s",
    )

    sys.path.insert(0, str(PROJECT_ROOT))

    # The static lint needs no build toolchain — check it before the gate.
    if not args.lint and not args.skip_toolchain_check and not _check_build_toolchain():
        sys.exit(2)

    task_dirs = sorted(TASKS_DIR.glob("pyvrp-*"))
    if args.task:
        task_dirs = [d for d in task_dirs if d.name == args.task]
        if not task_dirs:
            log.error("Task %s not found", args.task)
            sys.exit(2)

    if args.lint:
        results = [lint_task(d) for d in task_dirs]
        text, ok = render_lint_summary(results)
        print(text)
        sys.exit(0 if ok else 1)

    if args.validate_transitions:
        results = [validate_transitions(d) for d in task_dirs]
        text, ok = render_transitions_summary(results)
        print(text)
        sys.exit(0 if ok else 1)

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
