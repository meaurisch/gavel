"""Rebuild derived repo-context payloads from their declared source.

Repo-contexts that are exported/synthesized from another repo (rather than
authored by hand in place) declare a `build:` block in manifest.yaml:

    build:
      command: python export_memory.py --out content/.memory
      source_ref: studio-memory@seed/studio-conventions

`command` runs with cwd set to the repo-context's own directory, so relative
paths (like `--out content/.memory`) resolve against it. `source_ref` is
provenance only — a human-readable pointer to what was exported — this
script does not resolve it; the command itself is responsible for checking
out / fetching whatever it needs. This replaces one-off "REBUILD ME" prose
comments with a convention every derived context can follow the same way.

Usage:
    python scripts/build_repo_context.py studio-memory-full
    python scripts/build_repo_context.py --all
    python scripts/build_repo_context.py --list
"""

from __future__ import annotations

import argparse
import logging
import subprocess
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

REPO_CONTEXTS_DIR = Path(__file__).resolve().parent.parent / "repo_contexts"


def list_buildable_contexts(repo_contexts_dir: Path = REPO_CONTEXTS_DIR) -> list[tuple[str, str]]:
    """Every repo-context with a declared build step, as (id, source_ref).
    Single source of truth for `cli.py doctor`."""
    contexts: list[tuple[str, str]] = []
    for manifest in sorted(repo_contexts_dir.glob("*/manifest.yaml")):
        raw = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        build = raw.get("build")
        if not build:
            continue
        contexts.append((manifest.parent.name, build["source_ref"]))
    return contexts


def build_repo_context(context_id: str, repo_contexts_dir: Path = REPO_CONTEXTS_DIR) -> None:
    """Run the declared build command for one repo-context, regenerating its
    derived payload in place."""
    context_dir = repo_contexts_dir / context_id
    manifest_path = context_dir / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.yaml for repo context '{context_id}'")

    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    build = raw.get("build")
    if not build:
        logger.info("Repo context '%s' has no declared build step — skipping", context_id)
        return

    command = build["command"]
    logger.info("Rebuilding '%s' from %s ...", context_id, build["source_ref"])
    logger.info("$ %s", command)
    subprocess.run(command, shell=True, cwd=str(context_dir), check=True)
    logger.info("Rebuilt %s", context_id)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild derived repo-context payloads")
    parser.add_argument("context_id", nargs="?", help="Repo-context ID to rebuild")
    parser.add_argument("--all", action="store_true", help="Rebuild every repo-context with a declared build step")
    parser.add_argument("--list", action="store_true", help="List repo-contexts with a declared build step")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    if args.list:
        contexts = list_buildable_contexts()
        if not contexts:
            print("No repo-contexts declare a build step.")
        for context_id, source_ref in contexts:
            print(f"{context_id}: {source_ref}")
        return

    ids = [cid for cid, _ in list_buildable_contexts()] if args.all else ([args.context_id] if args.context_id else [])
    if not ids:
        parser.error("Provide a context_id, --all, or --list")

    for context_id in ids:
        build_repo_context(context_id)


if __name__ == "__main__":
    main()
