from pathlib import Path

import pytest

from core.models import RepoContextSpec
from core.repo_context_loader import (
    get_task_affinity,
    list_repo_contexts,
    load_repo_context,
)


# --- shipped repo contexts ---

def test_list_repo_contexts():
    assert list_repo_contexts() == ["cosmos", "none", "pyvrp-instructions"]


def test_load_repo_context_noop():
    spec = load_repo_context("none", "claude-code")
    assert isinstance(spec, RepoContextSpec)
    assert spec.id == "none"
    assert spec.files == {}


def test_get_task_affinity_shipped():
    assert get_task_affinity("none") == []
    assert get_task_affinity("cosmos") == ["cosmos-A", "cosmos-B"]
    assert get_task_affinity("pyvrp-instructions") == ["pyvrp-A", "pyvrp-B", "pyvrp-C"]


# --- controlled temp repo contexts ---

def _write_context(root: Path, context_id: str, manifest: str, files: dict[str, str]) -> None:
    cdir = root / context_id
    cdir.mkdir(parents=True)
    (cdir / "manifest.yaml").write_text(manifest, encoding="utf-8")
    for rel, content in files.items():
        target = cdir / rel
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(content, encoding="utf-8")


def test_get_task_affinity_specific(tmp_path):
    _write_context(
        tmp_path, "scoped",
        "id: scoped\ndescription: scoped\ntask_affinity: [task-A, task-B]\nnoop: true\n",
        {},
    )
    assert get_task_affinity("scoped", tmp_path) == ["task-A", "task-B"]


def test_load_repo_context_resolves_files(tmp_path):
    _write_context(
        tmp_path, "ctx",
        "id: ctx\ndescription: ctx\nharnesses:\n  claude-code:\n    - src: content/CLAUDE.md\n      dest: CLAUDE.md\n",
        {"content/CLAUDE.md": "# rules\nbe concise\n"},
    )
    spec = load_repo_context("ctx", "claude-code", tmp_path)
    assert spec.id == "ctx"
    assert spec.files == {"CLAUDE.md": ["# rules", "be concise"]}


def test_load_repo_context_missing_harness(tmp_path):
    _write_context(
        tmp_path, "ctx",
        "id: ctx\ndescription: ctx\nharnesses:\n  claude-code:\n    - src: content/CLAUDE.md\n      dest: CLAUDE.md\n",
        {"content/CLAUDE.md": "# rules\n"},
    )
    with pytest.raises(ValueError, match="Harness 'copilot' not found"):
        load_repo_context("ctx", "copilot", tmp_path)
