"""Shared helpers for deciding how to dispatch build/test commands by toolchain."""
from __future__ import annotations

import os
import platform
from pathlib import Path

from core.models import TaskSpec


def is_editable_pip_install(build_cmd: str | None) -> bool:
    """True for a ``pip install -e .`` build command (PyVRP-style)."""
    text = build_cmd or ""
    return "pip install" in text and "-e" in text


def needs_wsl(task: TaskSpec) -> bool:
    # PyVRP's C++ only builds under WSL on this Windows host. The validator runs
    # *inside* WSL (Linux), where this must stay False so it installs natively.
    return is_editable_pip_install(task.build_cmd) and platform.system() == "Windows"


def _canonical_inner_cmd(cmd: str) -> str:
    if is_editable_pip_install(cmd):
        return "pip install -e . --no-build-isolation"
    if "pytest" in cmd:
        return cmd + ' -o "addopts="'
    return cmd


def wsl_argv(cmd: str, cwd: Path) -> list[str]:
    distro = os.environ.get("SB_WSL_DISTRO", "Ubuntu")
    venv = os.environ.get("SB_WSL_VENV", "~/pyvrp-venv/bin/activate")
    inner = _canonical_inner_cmd(cmd)
    script = f"source {venv} && cd \"$(wslpath -a '{cwd}')\" && {inner}"
    return ["wsl", "-d", distro, "--", "bash", "-lc", script]
