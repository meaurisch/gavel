from pathlib import Path

import yaml

from core.manifest import FileMapping, Manifest
from core.models import SetupSpec

SETUPS_DIR = Path(__file__).parent.parent / "setups"

INSTRUCTION_FILENAMES = {
    "CLAUDE.md",
    "copilot-instructions.md",
    "AGENTS.md",
}


def load_manifest(setup_id: str, setups_dir: Path = SETUPS_DIR) -> Manifest:
    """Read and validate setups/<id>/manifest.yaml into a Manifest."""
    manifest_path = setups_dir / setup_id / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.yaml found for setup '{setup_id}' at {manifest_path}")
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    return Manifest(**raw)


def load_setup(setup_id: str, harness: str, setups_dir: Path = SETUPS_DIR) -> SetupSpec:
    """Resolve a (setup_id, harness) pair into a SetupSpec with populated files dict."""
    manifest = load_manifest(setup_id, setups_dir)

    if manifest.noop:
        return SetupSpec(id=setup_id, files={})

    if harness not in manifest.harnesses:
        raise ValueError(
            f"Harness '{harness}' not found in manifest for setup '{setup_id}'. "
            f"Available harnesses: {list(manifest.harnesses.keys())}"
        )

    mappings = manifest.harnesses[harness]
    if not mappings:
        return SetupSpec(id=setup_id, files={})

    setup_root = setups_dir / setup_id
    files: dict[str, list[str]] = {}

    for mapping in mappings:
        _resolve_mapping(setup_root, mapping, files)

    return SetupSpec(id=setup_id, files=files)


def _resolve_mapping(
    setup_root: Path, mapping: FileMapping, files: dict[str, list[str]]
) -> None:
    """Resolve a single FileMapping into entries in the files dict."""
    src_path = setup_root / mapping.src

    if src_path.is_dir():
        for child in sorted(src_path.rglob("*")):
            if child.is_file():
                rel = child.relative_to(src_path)
                dest = str(Path(mapping.dest) / rel).replace("\\", "/")
                lines = child.read_text(encoding="utf-8").splitlines()
                files[dest] = lines
    elif src_path.is_file():
        lines = src_path.read_text(encoding="utf-8").splitlines()
        dest = mapping.dest.replace("\\", "/")
        files[dest] = lines
    else:
        raise FileNotFoundError(
            f"Source path '{mapping.src}' not found at {src_path}"
        )


def check_overlap(repo_path: Path, setup: SetupSpec) -> list[str]:
    """Check if the repo already has files that collide with setup targets."""
    warnings: list[str] = []
    for dest in setup.files:
        target = repo_path / dest
        if target.exists():
            line_count = len(target.read_text(encoding="utf-8").splitlines())
            warnings.append(
                f"{setup.id} places {dest} but repo already has one "
                f"({line_count} lines) — content will be overwritten"
            )
    return warnings


def list_setups(setups_dir: Path = SETUPS_DIR) -> list[str]:
    """Return setup IDs (subdirs containing manifest.yaml)."""
    if not setups_dir.exists():
        return []
    return sorted(
        d.name
        for d in setups_dir.iterdir()
        if d.is_dir() and (d / "manifest.yaml").exists()
    )
