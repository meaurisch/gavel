from pathlib import Path

import pytest
import yaml

from core.manifest import FileMapping, Manifest, Source
from core.setup_loader import (
    SETUPS_DIR,
    check_overlap,
    list_setups,
    load_manifest,
    load_setup,
)
from core.models import SetupSpec


# --- list_setups ---

def test_list_setups():
    ids = list_setups()
    assert set(ids) == {"baseline", "custom", "ecc", "karpathy", "repo-instructions", "superpowers"}


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


# --- load_setup noop ---

def test_load_setup_noop():
    spec = load_setup("baseline", "claude-code")
    assert isinstance(spec, SetupSpec)
    assert spec.id == "baseline"
    assert spec.files == {}


# --- load_setup empty harness ---

def test_load_setup_empty_harness():
    spec = load_setup("custom", "claude-code")
    assert isinstance(spec, SetupSpec)
    assert spec.id == "custom"
    assert spec.files == {}


# --- load_setup with real files ---

def test_load_setup_with_files(tmp_path: Path):
    setup_dir = tmp_path / "setups" / "test-setup"
    setup_dir.mkdir(parents=True)
    content_dir = setup_dir / "content"
    content_dir.mkdir()
    (content_dir / "instructions.md").write_text("# Hello\nWorld\n", encoding="utf-8")

    manifest = {
        "id": "test-setup",
        "description": "Test setup",
        "harnesses": {
            "claude-code": [
                {"src": "content/instructions.md", "dest": "CLAUDE.md"},
            ],
        },
    }
    (setup_dir / "manifest.yaml").write_text(yaml.dump(manifest), encoding="utf-8")

    spec = load_setup("test-setup", "claude-code", setups_dir=tmp_path / "setups")
    assert spec.id == "test-setup"
    assert "CLAUDE.md" in spec.files
    assert spec.files["CLAUDE.md"] == ["# Hello", "World"]


# --- load_setup directory src ---

def test_load_setup_directory_src(tmp_path: Path):
    setup_dir = tmp_path / "setups" / "dir-setup"
    setup_dir.mkdir(parents=True)
    skills_dir = setup_dir / "vendor" / "skills"
    skills_dir.mkdir(parents=True)
    (skills_dir / "planning.md").write_text("Plan first\n", encoding="utf-8")
    sub = skills_dir / "sub"
    sub.mkdir()
    (sub / "deep.md").write_text("Deep skill\n", encoding="utf-8")

    manifest = {
        "id": "dir-setup",
        "description": "Directory source test",
        "harnesses": {
            "claude-code": [
                {"src": "vendor/skills/", "dest": ".claude/skills/test/"},
            ],
        },
    }
    (setup_dir / "manifest.yaml").write_text(yaml.dump(manifest), encoding="utf-8")

    spec = load_setup("dir-setup", "claude-code", setups_dir=tmp_path / "setups")
    assert spec.id == "dir-setup"
    assert ".claude/skills/test/planning.md" in spec.files
    assert ".claude/skills/test/sub/deep.md" in spec.files
    assert spec.files[".claude/skills/test/planning.md"] == ["Plan first"]
    assert spec.files[".claude/skills/test/sub/deep.md"] == ["Deep skill"]


# --- load_setup missing harness ---

def test_load_setup_missing_harness():
    with pytest.raises(ValueError, match="Harness 'nonexistent' not found"):
        load_setup("karpathy", "nonexistent")


# --- check_overlap ---

def test_check_overlap(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()
    (repo / "CLAUDE.md").write_text("existing\ninstructions\n", encoding="utf-8")

    setup = SetupSpec(id="test-pack", files={"CLAUDE.md": ["# New instructions"]})
    warnings = check_overlap(repo, setup)
    assert len(warnings) == 1
    assert "test-pack" in warnings[0]
    assert "CLAUDE.md" in warnings[0]
    assert "2 lines" in warnings[0]
    assert "overwritten" in warnings[0]


def test_check_overlap_no_collision(tmp_path: Path):
    repo = tmp_path / "repo"
    repo.mkdir()

    setup = SetupSpec(id="clean", files={"CLAUDE.md": ["# Instructions"]})
    warnings = check_overlap(repo, setup)
    assert warnings == []
