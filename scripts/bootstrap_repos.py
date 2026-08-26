"""Reproducible task-repo bootstrap.

Task base commits are LOCAL synthesized commits — a task's feature
reverse-applied onto a pinned upstream anchor (PyVRP), or a migration patch
applied (cosmos). They exist in no upstream remote, so a fresh clone of
setup-bench cannot run any trial until they are rebuilt.

This script rebuilds them deterministically from `tasks/_repo_setup/
repos.lock.yaml`: pure git plumbing (read-tree + apply --cached +
commit-tree) under a fixed author/committer/date, so the resulting sha is
identical on every machine and must match the lock file's `expect` value and
each task.yaml's `base_commit`.

Usage:
    python scripts/bootstrap_repos.py            # clone + build everything
    python scripts/bootstrap_repos.py --check    # report state, change nothing
(or simply `python cli.py setup`.)
"""

from __future__ import annotations

import argparse
import logging
import os
import subprocess
import sys
from pathlib import Path

import yaml

logger = logging.getLogger(__name__)

ROOT = Path(__file__).resolve().parent.parent
LOCK_FILE = ROOT / "tasks" / "_repo_setup" / "repos.lock.yaml"
REPOS_ROOT = ROOT / "repos"

# Fixed identity for synthesized commits — part of the sha, never change it.
_COMMIT_ENV = {
    "GIT_AUTHOR_NAME": "setup-bench",
    "GIT_AUTHOR_EMAIL": "setup-bench@local",
    "GIT_COMMITTER_NAME": "setup-bench",
    "GIT_COMMITTER_EMAIL": "setup-bench@local",
    "GIT_AUTHOR_DATE": "2026-01-01T00:00:00 +0000",
    "GIT_COMMITTER_DATE": "2026-01-01T00:00:00 +0000",
}


class BootstrapError(RuntimeError):
    pass


def _git(repo: Path, *args: str, env: dict | None = None, input_bytes: bytes | None = None) -> str:
    full_env = {**os.environ, **(env or {})}
    proc = subprocess.run(
        ["git", *args],
        cwd=str(repo),
        env=full_env,
        input=input_bytes,
        capture_output=True,
    )
    if proc.returncode != 0:
        raise BootstrapError(
            f"git {' '.join(args)} failed in {repo}: {proc.stderr.decode('utf-8', 'replace')[:800]}"
        )
    return proc.stdout.decode("utf-8", "replace").strip()


def load_lock(lock_file: Path = LOCK_FILE) -> dict:
    return yaml.safe_load(lock_file.read_text(encoding="utf-8"))


def commit_exists(repo: Path, sha: str) -> bool:
    try:
        return _git(repo, "cat-file", "-t", sha) == "commit"
    except BootstrapError:
        return False


def ensure_repo(repo_id: str, url: str, repos_root: Path = REPOS_ROOT) -> Path:
    """Clone the task repo if absent. autocrlf is disabled so worktree bytes
    match the committed blobs (reference diffs are byte-exact)."""
    repo_dir = repos_root / repo_id
    if (repo_dir / ".git").exists():
        return repo_dir
    repos_root.mkdir(parents=True, exist_ok=True)
    logger.info("Cloning %s -> %s ...", url, repo_dir)
    proc = subprocess.run(
        ["git", "clone", "--config", "core.autocrlf=false", url, str(repo_dir)],
        capture_output=True,
        text=True,
    )
    if proc.returncode != 0:
        raise BootstrapError(f"clone of {url} failed: {proc.stderr[:800]}")
    return repo_dir


def build_base(repo: Path, base_id: str, spec: dict, project_root: Path = ROOT) -> str:
    """Deterministically rebuild one task base commit; returns its sha.

    The patch is applied to a throwaway INDEX only (never a worktree), so no
    eol/smudge filter can perturb the bytes — the tree, and therefore the
    commit sha, is a pure function of (anchor, patch, fixed metadata).
    """
    anchor = spec["anchor"]
    expect = spec.get("expect")
    if anchor == "PENDING" or expect == "PENDING":
        raise BootstrapError(f"{base_id}: lock entry is PENDING — not buildable")

    if expect and commit_exists(repo, expect):
        logger.info("%s: base %s already present", base_id, expect[:12])
        _git(repo, "update-ref", f"refs/heads/task-base-{base_id}", expect)
        return expect

    if not commit_exists(repo, anchor):
        logger.info("%s: fetching anchor %s ...", base_id, anchor[:12])
        _git(repo, "fetch", "origin", anchor)

    index_file = repo / ".git" / f"sb-bootstrap-index-{base_id}"
    env = {**_COMMIT_ENV, "GIT_INDEX_FILE": str(index_file)}
    try:
        _git(repo, "read-tree", anchor, env=env)
        if "reverse_diff" in spec:
            patch = (project_root / spec["reverse_diff"]).read_bytes()
            _git(repo, "apply", "-R", "--cached", "-", env=env, input_bytes=patch)
            message = f"setup-bench: {base_id} task base (feature reverse-applied onto upstream {anchor})"
        elif "apply_patch" in spec:
            patch = (project_root / spec["apply_patch"]).read_bytes()
            _git(repo, "apply", "--cached", "-", env=env, input_bytes=patch)
            message = f"setup-bench: {base_id} (patch applied onto upstream {anchor})"
        else:
            raise BootstrapError(f"{base_id}: lock entry has neither reverse_diff nor apply_patch")
        tree = _git(repo, "write-tree", env=env)
        sha = _git(repo, "commit-tree", tree, "-p", anchor, "-m", message, env=env)
    finally:
        index_file.unlink(missing_ok=True)

    if expect and sha != expect:
        raise BootstrapError(
            f"{base_id}: rebuilt base {sha} does not match locked expect {expect} — "
            "the lock file, the patch, or the anchor changed"
        )
    _git(repo, "update-ref", f"refs/heads/task-base-{base_id}", sha)
    logger.info("%s: built base %s", base_id, sha[:12])
    return sha


def bootstrap(check_only: bool = False, repos_root: Path = REPOS_ROOT) -> list[tuple[str, str, str]]:
    """Returns [(base_id, status, detail)] with status in ok/missing/error."""
    results: list[tuple[str, str, str]] = []
    lock = load_lock()
    for repo_id, cfg in lock.items():
        try:
            if check_only:
                repo_dir = repos_root / repo_id
                if not (repo_dir / ".git").exists():
                    for base_id in cfg.get("bases", {}):
                        results.append((base_id, "missing", f"repos/{repo_id} not cloned"))
                    continue
            else:
                repo_dir = ensure_repo(repo_id, cfg["url"], repos_root)
        except BootstrapError as e:
            for base_id in cfg.get("bases", {}):
                results.append((base_id, "error", str(e)))
            continue

        for base_id, spec in cfg.get("bases", {}).items():
            expect = spec.get("expect")
            try:
                if expect == "PENDING" or spec.get("anchor") == "PENDING":
                    if check_only:
                        results.append((base_id, "missing", "lock entry PENDING"))
                    else:
                        logger.warning("%s: lock entry is PENDING — skipping build", base_id)
                        results.append((base_id, "missing", "lock entry PENDING, skipped"))
                elif check_only:
                    if expect and commit_exists(repo_dir, expect):
                        results.append((base_id, "ok", expect))
                    else:
                        results.append((base_id, "missing", f"base {expect} not built"))
                else:
                    sha = build_base(repo_dir, base_id, spec)
                    results.append((base_id, "ok", sha))
            except BootstrapError as e:
                results.append((base_id, "error", str(e)))
    return results


def main() -> int:
    parser = argparse.ArgumentParser(description="Clone task repos and rebuild base commits")
    parser.add_argument("--check", action="store_true", help="Report state without changing anything")
    parser.add_argument("--verbose", "-v", action="store_true")
    args = parser.parse_args()

    logging.basicConfig(
        level=logging.DEBUG if args.verbose else logging.INFO,
        format="%(levelname)s: %(message)s",
    )

    results = bootstrap(check_only=args.check)
    width = max((len(r[0]) for r in results), default=10)
    failed = False
    for base_id, status, detail in results:
        mark = {"ok": "OK  ", "missing": "MISS", "error": "ERR "}[status]
        print(f"{mark} {base_id:<{width}}  {detail}")
        failed = failed or status != "ok"
    return 1 if failed else 0


if __name__ == "__main__":
    sys.exit(main())
