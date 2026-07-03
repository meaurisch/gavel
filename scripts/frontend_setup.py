"""Frontend toolchain helpers — npm install + build for ui/frontend, shared by
`cli.py setup` (does the work) and `cli.py doctor` (checks readiness)."""

from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
FRONTEND_DIR = ROOT / "ui" / "frontend"
DIST_INDEX = FRONTEND_DIR / "dist" / "index.html"


def npm_path() -> str | None:
    # Resolve the full path: on Windows `npm` is npm.cmd, which CreateProcess
    # can't spawn from a bare name.
    return shutil.which("npm")


def node_version() -> str | None:
    node = shutil.which("node")
    if node is None:
        return None
    try:
        proc = subprocess.run([node, "--version"], capture_output=True, text=True, timeout=30)
    except subprocess.TimeoutExpired:
        return None
    return proc.stdout.strip() if proc.returncode == 0 else None


def frontend_built() -> bool:
    return DIST_INDEX.is_file()


def build_frontend() -> tuple[bool, str]:
    """npm install (ci when lockfile is present) + npm run build.
    Returns (ok, detail)."""
    npm = npm_path()
    if npm is None:
        return False, "npm not found on PATH — install Node.js 18+ (https://nodejs.org)"
    if not FRONTEND_DIR.is_dir():
        return False, f"frontend directory missing at {FRONTEND_DIR}"

    install_cmd = [npm, "ci"] if (FRONTEND_DIR / "package-lock.json").exists() else [npm, "install"]
    for cmd in (install_cmd, [npm, "run", "build"]):
        proc = subprocess.run(
            cmd,
            cwd=str(FRONTEND_DIR),
            capture_output=True,
            text=True,
            encoding="utf-8",
            errors="replace",
            timeout=600,
        )
        if proc.returncode != 0:
            tail = (proc.stderr or proc.stdout or "").strip().splitlines()[-8:]
            return False, f"`{' '.join(cmd[1:] or cmd)}` failed: " + " | ".join(tail)

    if not frontend_built():
        return False, "build reported success but dist/index.html is missing"
    return True, "frontend built (ui/frontend/dist)"
