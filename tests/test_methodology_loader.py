from pathlib import Path

import pytest
import yaml

from core.manifest import FileMapping, Manifest, Source
from core.methodology_loader import (
    METHODOLOGIES_DIR,
    check_overlap,
    list_methodologies,
    load_manifest,
    load_methodology,
)
from core.models import MethodologySpec


# --- list_methodologies ---

def test_list_methodologies():
    ids = list_methodologies()
    assert set(ids) == {"baseline", "custom", "ecc", "karpathy", "superpowers"}


# --- load_manifest ---

def test_load_manifest_baseline():
    m = load_manifest("baseline")
    assert m.id == "baseline"
    assert m.noop is True
    assert m.source is None
    assert m.harnesses == {}


def test_load_manifest_karpathy():
    m = load_manifest("karpathy")
    assert m.id == "karpathy"
    assert m.noop is False
    assert m.source is not None
    assert m.source.repo == "forrestchang/andrej-karpathy-skills"
    assert "claude-code" in m.harnesses
    assert "copilot" in m.harnesses
    assert len(m.harnesses["claude-code"]) == 1
    assert m.harnesses["claude-code"][0].dest == "CLAUDE.md"


# --- load_methodology noop ---

def test_load_methodology_noop():
    spec = load_methodology("baseline", "claude-code")
    assert isinstance(spec, MethodologySpec)
    assert spec.id == "baseline"
    assert spec.files == {}


# --- load_methodology empty harness ---

def test_load_methodology_empty_harness():
    spec = load_methodology("custom", "claude-code")
    assert isinstance(spec, MethodologySpec)
    assert spec.id == "custom"
    assert spec.files == {}


# --- load_methodology with real files ---

def test_load_methodology_with_files(tmp_path: Path):
    methodology_dir = tmp_path / "methodologies" / "test-methodology"
    methodology_dir.mkdir(parents=True)
    content_dir = methodology_dir / "content"
    content_dir.mkdir()
    (content_dir / "instructions.md").write_text("# Hello\nWorld\n", encoding="utf-8")

    manifest = {
        "id": "test-methodology",
        "description": "Test methodology",
        "harnesses": {
            "claude-code": [
                {"src": "content/instructions.md", "dest": "CLAUDE.md"},
            ],
        },
    }
    (methodology_dir / "manifest.yaml").write_text(yaml.dump(manifest), encoding="utf-8")

    spec = load_methodology("test-methodology", "claude-code", methodologies_dir=tmp_path / "methodologies")
    assert spec.id == "test-methodology"
    assert "CLAUDE.md" in spec.files
    assert spec.files["CLAUDE.md"] == ["# Hello", "World"]


# --- load_methodology directory src ---

def test_load_methodology_directory_src(tmp_path: Path):
    methodology_dir = tmp_path / "methodologies" / "dir-methodology"
    methodology_dir.mkdir(parents=True)
    skills_dir = methodology_dir / "vendor" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "planning.md").write_text("Plan first\n", encoding="utf-8")
    sub = skills_dir / "sub"
    sub.mkdir()
    (sub / "deep.md").write_text("Deep skill\n", encoding="utf-8")

    manifest = {
        "id": "dir-methodology",
        "description": "Directory source test",
        "harnesses": {
            "claude-code": [
                {"src": "vendor/skills/", "dest": ".claude/skills/test/"},
            ],
        },
    }
    (methodology_dir / "manifest.yaml").write_text(yaml.dump(manifest), encoding="utf-8")

    spec = load_methodology("dir-methodology", "claude-code", methodologies_dir=tmp_path / "methodologies")
    assert spec.id == "dir-methodology"
    assert ".claude/skills/test/planning.md" in spec.files
    assert ".claude/skills/test/sub/deep.md" in spec.files
    assert spec.files[".claude/skills/test/planning.md"] == ["Plan first"]
    assert spec.files[".claude/skills/test/sub/deep.md"] == ["Deep skill"]


# --- load_methodology missing harness ---

def test_load_methodology_missing_harness():
    with pytest.raises(ValueError, match="Harness 'nonexistent' not found"):
        load_methodology("karpathy", "nonexistent")


# --- check_overlap ---

def test_check_overlap(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text("existing\ninstructions\n", encoding="utf-8")

    methodology = MethodologySpec(id="test-pack", files={"CLAUDE.md": ["# New instructions"]})
    warnings = check_overlap(repo, methodology)
    assert len(warnings) == 1
    assert "test-pack" in warnings[0]
    assert "CLAUDE.md" in warnings[0]
    assert "2 lines" in warnings[0]
    assert "overwritten" in warnings[0]


def test_check_overlap_no_collision(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    methodology = MethodologySpec(id="clean", files={"CLAUDE.md": ["# Instructions"]})
    warnings = check_overlap(repo, methodology)
    assert warnings == []
