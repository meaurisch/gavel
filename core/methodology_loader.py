from pathlib import Path

import yaml

from core.manifest import FileMapping, Manifest
from core.models import MethodologySpec

METHODOLOGIES_DIR = Path(__file__).parent.parent / "methodologies"

INSTRUCTION_FILENAMES = {
    "CLAUDE.md",
    "copilot-instructions.md",
    "AGENTS.md",
}


def load_manifest(methodology_id: str, methodologies_dir: Path = METHODOLOGIES_DIR) -> Manifest:
    """Read and validate methodologies/<id>/manifest.yaml into a Manifest."""
    manifest_path = methodologies_dir / methodology_id / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.yaml found for methodology '{methodology_id}' at {manifest_path}")
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    return Manifest(**raw)


def load_methodology(methodology_id: str, harness: str, methodologies_dir: Path = METHODOLOGIES_DIR) -> MethodologySpec:
    """Resolve a (methodology_id, harness) pair into a MethodologySpec with populated files dict."""
    manifest = load_manifest(methodology_id, methodologies_dir)

    if manifest.noop:
        return MethodologySpec(id=methodology_id, files={})

    if harness not in manifest.harnesses:
        raise ValueError(
            f"Harness '{harness}' not found in manifest for methodology '{methodology_id}'. "
            f"Available harnesses: {list(manifest.harnesses.keys())}"
        )

    mappings = manifest.harnesses[harness]
    if not mappings:
        return MethodologySpec(id=methodology_id, files={})

    methodology_root = methodologies_dir / methodology_id
    files: dict[str, list[str]] = {}

    for mapping in mappings:
        _resolve_mapping(methodology_root, mapping, files)

    return MethodologySpec(id=methodology_id, files=files)


def _resolve_mapping(
    methodology_root: Path, mapping: FileMapping, files: dict[str, list[str]]
) -> None:
    """Resolve a single FileMapping into entries in the files dict."""
    src_path = methodology_root / mapping.src

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


def check_overlap(repo_path: Path, methodology: MethodologySpec) -> list[str]:
    """Check if the repo already has files that collide with methodology targets."""
    warnings: list[str] = []
    for dest in methodology.files:
        target = repo_path / dest
        if target.exists():
            line_count = len(target.read_text(encoding="utf-8").splitlines())
            warnings.append(
                f"{methodology.id} places {dest} but repo already has one "
                f"({line_count} lines) — content will be overwritten"
            )
    return warnings


def list_methodologies(methodologies_dir: Path = METHODOLOGIES_DIR) -> list[str]:
    """Return methodology IDs (subdirs containing manifest.yaml)."""
    if not methodologies_dir.exists():
        return []
    return sorted(
        d.name
        for d in methodologies_dir.iterdir()
        if d.is_dir() and (d / "manifest.yaml").exists()
    )
