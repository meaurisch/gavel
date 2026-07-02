"""Environment doctor — readiness checks for setup-bench.

Each check returns a DoctorRow. `required` distinguishes hard requirements
(git, python deps) from per-task-family toolchains (dotnet is only needed for
cosmos-* tasks, WSL only for pyvrp-*): those report as warnings, not failures.
"""

from __future__ import annotations

import os
import shutil
import subprocess
import sys
from dataclasses import dataclass
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent

WSL_DISTRO = os.environ.get("SB_WSL_DISTRO", "Ubuntu")
WSL_VENV = os.environ.get("SB_WSL_VENV", "~/pyvrp-venv/bin/activate")


@dataclass
class DoctorRow:
    name: str
    ok: bool
    required: bool
    detail: str
    hint: str = ""


def _probe(cmd: list[str], timeout: int = 30) -> tuple[bool, str]:
    exe = shutil.which(cmd[0])
    if exe is None:
        return False, f"{cmd[0]} not found on PATH"
    try:
        # Use the resolved path: on Windows a bare name that resolves to a
        # .CMD shim (claude, npm, ...) can't be spawned by CreateProcess.
        proc = subprocess.run([exe, *cmd[1:]], capture_output=True, text=True, encoding="utf-8",
                              errors="replace", timeout=timeout)
    except subprocess.TimeoutExpired:
        return False, f"{' '.join(cmd)} timed out"
    out = (proc.stdout or proc.stderr).strip().splitlines()
    return proc.returncode == 0, out[0] if out else f"exit {proc.returncode}"


def check_git() -> DoctorRow:
    ok, detail = _probe(["git", "--version"])
    return DoctorRow("git", ok, True, detail, "Install git and put it on PATH")


def check_claude_cli() -> DoctorRow:
    ok, detail = _probe(["claude", "--version"])
    return DoctorRow("claude CLI", ok, False, detail,
                     "npm install -g @anthropic-ai/claude-code (needed for the claude-code runner)")


def check_dotnet() -> DoctorRow:
    ok, detail = _probe(["dotnet", "--version"])
    return DoctorRow("dotnet SDK", ok, False, detail if ok else detail,
                     "Install .NET 8 SDK (needed for cosmos-* tasks)")


def check_wsl() -> DoctorRow:
    ok, detail = _probe(
        ["wsl", "-d", WSL_DISTRO, "--", "bash", "-lc",
         f"test -f {WSL_VENV} && echo venv-ok || echo venv-missing"],
        timeout=60,
    )
    ok = ok and "venv-ok" in detail
    return DoctorRow(f"WSL ({WSL_DISTRO} + pyvrp venv)", ok, False, detail,
                     "Install WSL Ubuntu and create the pyvrp venv (needed for pyvrp-* tasks); "
                     "override via SB_WSL_DISTRO / SB_WSL_VENV")


def check_task_bases() -> list[DoctorRow]:
    sys.path.insert(0, str(ROOT / "scripts"))
    from bootstrap_repos import bootstrap

    rows = []
    for base_id, status, detail in bootstrap(check_only=True):
        rows.append(DoctorRow(
            f"task base {base_id}", status == "ok", True,
            detail if status != "ok" else f"{detail[:12]} present",
            "Run `python cli.py setup`",
        ))
    return rows


def check_vendor_packs() -> list[DoctorRow]:
    import yaml

    rows = []
    for manifest in sorted((ROOT / "methodologies").glob("*/manifest.yaml")):
        raw = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        if not raw.get("source"):
            continue
        mid = manifest.parent.name
        vendor = manifest.parent / "vendor"
        ok = vendor.exists() and any(vendor.iterdir())
        rows.append(DoctorRow(
            f"vendor pack {mid}", ok, True,
            "present" if ok else "missing",
            "Run `python cli.py setup` (or scripts/vendor_setup.py --all)",
        ))
    return rows


def check_pricing() -> DoctorRow:
    try:
        from cost.pricing import load_pricing
        models, _ = load_pricing()
        return DoctorRow("pricing table", bool(models), True, f"{len(models)} models priced",
                         "cost/pricing.toml missing or empty — `python cli.py pricing fetch`")
    except Exception as e:
        return DoctorRow("pricing table", False, True, str(e)[:120],
                         "cost/pricing.toml unreadable")


def run_all_checks() -> list[DoctorRow]:
    rows = [check_git(), check_claude_cli(), check_dotnet(), check_wsl()]
    rows.extend(check_task_bases())
    rows.extend(check_vendor_packs())
    rows.append(check_pricing())
    return rows
