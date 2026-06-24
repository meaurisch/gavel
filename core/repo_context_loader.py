from pathlib import Path

from core.manifest import Manifest
from core.methodology_loader import load_manifest, _resolve_mapping
from core.models import RepoContextSpec

REPO_CONTEXTS_DIR = Path(__file__).parent.parent / "repo_contexts"


def load_repo_context(
    context_id: str, harness: str, repo_contexts_dir: Path = REPO_CONTEXTS_DIR
) -> RepoContextSpec:
    """Resolve a (context_id, harness) pair into a RepoContextSpec with populated files dict."""
    manifest = load_manifest(context_id, repo_contexts_dir)

    if manifest.noop:
        return RepoContextSpec(id=context_id, files={})

    if harness not in manifest.harnesses:
        raise ValueError(
            f"Harness '{harness}' not found in manifest for repo context '{context_id}'. "
            f"Available harnesses: {list(manifest.harnesses.keys())}"
        )

    mappings = manifest.harnesses[harness]
    if not mappings:
        return RepoContextSpec(id=context_id, files={})

    context_root = repo_contexts_dir / context_id
    files: dict[str, list[str]] = {}

    for mapping in mappings:
        _resolve_mapping(context_root, mapping, files)

    return RepoContextSpec(id=context_id, files=files)


def get_task_affinity(context_id: str, repo_contexts_dir: Path = REPO_CONTEXTS_DIR) -> list[str]:
    """Return the task_affinity list for a repo context (empty = applies to all tasks)."""
    manifest: Manifest = load_manifest(context_id, repo_contexts_dir)
    return manifest.task_affinity


def list_repo_contexts(repo_contexts_dir: Path = REPO_CONTEXTS_DIR) -> list[str]:
    """Return repo context IDs (subdirs containing manifest.yaml)."""
    if not repo_contexts_dir.exists():
        return []
    return sorted(
        d.name
        for d in repo_contexts_dir.iterdir()
        if d.is_dir() and (d / "manifest.yaml").exists()
    )
