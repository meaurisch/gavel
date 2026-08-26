import sys
from pathlib import Path

import pytest

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

from build_repo_context import (  # noqa: E402
    build_repo_context,
    list_buildable_contexts,
)


def _write_context(root: Path, context_id: str, manifest: str) -> Path:
    cdir = root / context_id
    cdir.mkdir(parents=True)
    (cdir / "manifest.yaml").write_text(manifest, encoding="utf-8")
    return cdir


def test_list_buildable_contexts_skips_hand_authored(tmp_path):
    _write_context(
        tmp_path, "hand-authored",
        "id: hand-authored\ndescription: hand-authored\nnoop: true\n",
    )
    _write_context(
        tmp_path, "derived",
        "id: derived\ndescription: derived\n"
        "build:\n  command: echo hi\n  source_ref: some-repo@some-ref\n",
    )
    assert list_buildable_contexts(tmp_path) == [("derived", "some-repo@some-ref")]


def test_build_repo_context_runs_declared_command(tmp_path):
    cdir = _write_context(
        tmp_path, "derived",
        "id: derived\ndescription: derived\n"
        f"build:\n  command: {sys.executable} -c \"open('content/.memory/out.txt', 'w').write('built')\"\n"
        "  source_ref: some-repo@some-ref\n",
    )
    (cdir / "content" / ".memory").mkdir(parents=True)

    build_repo_context("derived", tmp_path)

    assert (cdir / "content" / ".memory" / "out.txt").read_text(encoding="utf-8") == "built"


def test_build_repo_context_noop_without_build_block(tmp_path):
    _write_context(
        tmp_path, "hand-authored",
        "id: hand-authored\ndescription: hand-authored\nnoop: true\n",
    )
    # Must not raise even though there's nothing to build.
    build_repo_context("hand-authored", tmp_path)


def test_build_repo_context_missing_manifest(tmp_path):
    with pytest.raises(FileNotFoundError, match="No manifest.yaml"):
        build_repo_context("does-not-exist", tmp_path)


def test_build_repo_context_propagates_command_failure(tmp_path):
    _write_context(
        tmp_path, "derived",
        "id: derived\ndescription: derived\n"
        f"build:\n  command: {sys.executable} -c \"import sys; sys.exit(1)\"\n"
        "  source_ref: some-repo@some-ref\n",
    )
    with pytest.raises(Exception):
        build_repo_context("derived", tmp_path)
