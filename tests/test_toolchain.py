"""Unit tests for core.toolchain — must fail before core/toolchain.py exists."""
from __future__ import annotations

from pathlib import Path

import pytest

from core.models import TaskSpec


def _make_task(build_cmd: str | None = None, run_cmd: str = "echo ok") -> TaskSpec:
    return TaskSpec(
        id="t",
        repo_url="x",
        base_commit="x",
        instruction="do something",
        run_cmd=run_cmd,
        held_out_tests_path="x",
        reference_diff_path="x",
        build_cmd=build_cmd,
    )


# --- needs_wsl ---

def test_needs_wsl_true_for_pyvrp_on_windows(monkeypatch):
    monkeypatch.setattr("core.toolchain.platform.system", lambda: "Windows")
    from core.toolchain import needs_wsl
    task = _make_task(build_cmd="pip install -e . 2>&1")
    assert needs_wsl(task) is True


def test_needs_wsl_false_for_dotnet_on_windows(monkeypatch):
    monkeypatch.setattr("core.toolchain.platform.system", lambda: "Windows")
    from core.toolchain import needs_wsl
    task = _make_task(build_cmd="dotnet build CleanArchitectureCosmosDB.sln")
    assert needs_wsl(task) is False


def test_needs_wsl_false_on_linux(monkeypatch):
    monkeypatch.setattr("core.toolchain.platform.system", lambda: "Linux")
    from core.toolchain import needs_wsl
    task = _make_task(build_cmd="pip install -e . 2>&1")
    assert needs_wsl(task) is False


# --- wsl_argv structure ---

_CWD = Path(r"C:\tmp\wt")


def test_wsl_argv_structure_default_env(monkeypatch):
    monkeypatch.delenv("SB_WSL_DISTRO", raising=False)
    monkeypatch.delenv("SB_WSL_VENV", raising=False)
    from core.toolchain import wsl_argv
    argv = wsl_argv("pip install -e . 2>&1", _CWD)
    assert argv[:6] == ["wsl", "-d", "Ubuntu", "--", "bash", "-lc"]
    script = argv[6]
    assert "source ~/pyvrp-venv/bin/activate" in script
    assert r"wslpath -a 'C:\tmp\wt'" in script


def test_wsl_argv_pip_install_canonicalized(monkeypatch):
    monkeypatch.delenv("SB_WSL_DISTRO", raising=False)
    monkeypatch.delenv("SB_WSL_VENV", raising=False)
    from core.toolchain import wsl_argv
    argv = wsl_argv("pip install -e . 2>&1", _CWD)
    script = argv[-1]
    assert "pip install -e . --no-build-isolation" in script
    assert "2>&1" not in script


def test_wsl_argv_pytest_gets_addopts(monkeypatch):
    monkeypatch.delenv("SB_WSL_DISTRO", raising=False)
    monkeypatch.delenv("SB_WSL_VENV", raising=False)
    from core.toolchain import wsl_argv
    argv = wsl_argv("pytest tests/x.py -v", _CWD)
    script = argv[-1]
    assert '-o "addopts="' in script


def test_wsl_argv_env_override(monkeypatch):
    monkeypatch.setenv("SB_WSL_DISTRO", "Debian")
    monkeypatch.setenv("SB_WSL_VENV", "~/foo/bin/activate")
    from core.toolchain import wsl_argv
    argv = wsl_argv("pip install -e . 2>&1", _CWD)
    assert argv[2] == "Debian"
    script = argv[-1]
    assert "~/foo/bin/activate" in script
