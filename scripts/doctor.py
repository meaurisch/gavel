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
    return DoctorRow("dotnet SDK", ok, False, detail,
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
    sys.path.insert(0, str(ROOT / "scripts"))
    from vendor_setup import list_vendor_packs

    return [
        DoctorRow(
            f"vendor pack {mid}", present, True,
            "present" if present else "missing",
            "Run `python cli.py setup` (or scripts/vendor_setup.py --all)",
        )
        for mid, present in list_vendor_packs()
    ]


def check_node() -> DoctorRow:
    from frontend_setup import node_version, npm_path

    version = node_version()
    npm = npm_path()
    ok = version is not None and npm is not None
    detail = f"node {version}, npm present" if ok else "node/npm not found on PATH"
    return DoctorRow("node + npm", ok, True, detail,
                     "Install Node.js 18+ (https://nodejs.org) — needed to build the web UI")


def check_frontend_built() -> DoctorRow:
    from frontend_setup import frontend_built

    built = frontend_built()
    return DoctorRow("web UI build", built, True,
                     "ui/frontend/dist present" if built else "ui/frontend/dist missing",
                     "Run `python cli.py setup` (or: cd ui/frontend && npm install && npm run build)")


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
    rows = [check_git(), check_node(), check_frontend_built(),
            check_claude_cli(), check_dotnet(), check_wsl()]
    rows.extend(check_task_bases())
    rows.extend(check_vendor_packs())
    rows.append(check_pricing())
    return rows
