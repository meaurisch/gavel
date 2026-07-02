"""Vendor external instruction packs at pinned commits.

Usage:
    python scripts/vendor_setup.py karpathy
    python scripts/vendor_setup.py superpowers
    python scripts/vendor_setup.py ecc
    python scripts/vendor_setup.py --all
"""

from __future__ import annotations

import argparse
import logging
import shutil
import subprocess
import tempfile
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

METHODOLOGIES_DIR = Path(__file__).resolve().parent.parent / "methodologies"

VENDOR_SOURCES: dict[str, list[str]] = {
    "karpathy": ["CLAUDE.md"],
    "superpowers": ["CLAUDE.md", "AGENTS.md", "skills/"],
    "ecc": ["CLAUDE.md", "skills/", "agents/", "rules/"],
}


def list_vendor_packs() -> list[tuple[str, bool]]:
    """Every methodology with an external source, with whether its vendor dir
    is populated. Single source of truth for `cli.py setup` and the doctor."""
    packs: list[tuple[str, bool]] = []
    for manifest in sorted(METHODOLOGIES_DIR.glob("*/manifest.yaml")):
        raw = yaml.safe_load(manifest.read_text(encoding="utf-8"))
        if not raw.get("source"):
            continue
        vendor_dir = manifest.parent / "vendor"
        present = vendor_dir.exists() and any(vendor_dir.iterdir())
        packs.append((manifest.parent.name, present))
    return packs


def vendor_methodology(methodology_id: str) -> None:
    manifest_path = METHODOLOGIES_DIR / methodology_id / "manifest.yaml"
    if not manifest_path.exists():
        raise FileNotFoundError(f"No manifest.yaml for methodology '{methodology_id}'")

    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    source = raw.get("source")
    if not source:
        logger.info("Methodology '%s' has no external source — skipping", methodology_id)
        return

    repo = source["repo"]
    commit = source["commit"]
    if commit == "PENDING":
        raise ValueError(
            f"Methodology '{methodology_id}' has commit=PENDING. "
            f"Run with --pin-head to pin to the current HEAD of the default branch."
        )

    repo_url = f"https://github.com/{repo}.git"
    vendor_dir = METHODOLOGIES_DIR / methodology_id / "vendor"

    if vendor_dir.exists():
        shutil.rmtree(vendor_dir)
    vendor_dir.mkdir(parents=True)

    with tempfile.TemporaryDirectory() as tmp:
        tmp_path = Path(tmp) / "repo"
        logger.info("Cloning %s @ %s ...", repo_url, commit)
        subprocess.run(
            ["git", "clone", "--depth", "1", repo_url, str(tmp_path)],
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "fetch", "--depth", "1", "origin", commit],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
            text=True,
        )
        subprocess.run(
            ["git", "checkout", commit],
            cwd=str(tmp_path),
            check=True,
            capture_output=True,
            text=True,
        )

        sources = VENDOR_SOURCES.get(methodology_id, [])
        for src in sources:
            src_path = tmp_path / src
            dest_path = vendor_dir / src
            if src_path.is_dir():
                shutil.copytree(src_path, dest_path, dirs_exist_ok=True)
            elif src_path.is_file():
                dest_path.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(src_path, dest_path)
            else:
                logger.warning("Source '%s' not found in %s — skipping", src, repo)

    logger.info("Vendored %s → %s", methodology_id, vendor_dir)


def resolve_head(methodology_id: str) -> str:
    manifest_path = METHODOLOGIES_DIR / methodology_id / "manifest.yaml"
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    source = raw.get("source")
    if not source:
        raise ValueError(f"Methodology '{methodology_id}' has no source")

    repo_url = f"https://github.com/{source['repo']}.git"
    result = subprocess.run(
        ["git", "ls-remote", repo_url, "HEAD"],
        check=True,
        capture_output=True,
        text=True,
    )
    sha = result.stdout.split()[0]
    return sha


def pin_commit(methodology_id: str, commit: str) -> None:
    manifest_path = METHODOLOGIES_DIR / methodology_id / "manifest.yaml"
    raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
    raw["source"]["commit"] = commit
    manifest_path.write_text(yaml.dump(raw, default_flow_style=False, sort_keys=False), encoding="utf-8")
    logger.info("Pinned %s to %s", methodology_id, commit)


def main() -> None:
    parser = argparse.ArgumentParser(description="Vendor external instruction packs")
    parser.add_argument("methodology_id", nargs="?", help="Methodology ID to vendor")
    parser.add_argument("--all", action="store_true", help="Vendor all external methodologies")
    parser.add_argument("--pin-head", action="store_true", help="Pin PENDING commits to current HEAD")
    parser.add_argument("--verbose", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    ids = list(VENDOR_SOURCES.keys()) if args.all else ([args.methodology_id] if args.methodology_id else [])
    if not ids:
        parser.error("Provide a methodology_id or use --all")

    for methodology_id in ids:
        if args.pin_head:
            manifest_path = METHODOLOGIES_DIR / methodology_id / "manifest.yaml"
            raw = yaml.safe_load(manifest_path.read_text(encoding="utf-8"))
            if raw.get("source", {}).get("commit") == "PENDING":
                sha = resolve_head(methodology_id)
                pin_commit(methodology_id, sha)

        vendor_methodology(methodology_id)


if __name__ == "__main__":
    main()
