"""Held-out functional gate for D6 (studio#83 E6, pair 2).

Fully deterministic — file reads, a regex scan of the repo's vitest test tree,
and one `npx vitest run` subprocess. Nothing here encodes pointer-vs-copy: a
CLAUDE.md that duplicates the whole guide passes this gate just as a one-line
`@AGENTS.md` pointer does. The decision is measured separately, by the
non-gating DECISION line in run_hidden.py.
"""
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

CLAUDE = ROOT / "CLAUDE.md"
AGENTS = ROOT / "AGENTS.md"
# Verbatim from AGENTS.md at the pinned anchor b934395a — the guide's whole
# (single-paragraph) body opens with this sentence. Present => not gutted.
PINNED_PARAGRAPH = "vault-mcp-server is the SOLE integration hub of the vault family."
HELD_OUT = {"run_hidden.py", "test_D6_hidden.py", "e6_gatelib.py"}
# vitest's default `include`, restricted to the extensions this repo uses.
TEST_SUFFIXES = (".test.ts", ".test.js", ".test.mts", ".test.mjs",
                 ".spec.ts", ".spec.js", ".spec.mts", ".spec.mjs")
SKIP_DIRS = {"node_modules", "dist", ".git"}
ASSERTION_MARKERS = ("expect(", "assert")
VITEST_TIMEOUT = 900
# `test/deploy-rollback.test.ts` shells out to `scripts/deploy-health-gate.sh`
# via spawnSync. Under gavel's gate shell (cmd.exe, whose PATH has no bash on
# this host) that exits 127 instead of the exit code the file asserts, so the
# file is red on the untouched base for reasons no trial can fix or cause.
# Excluding exactly this one file — never any other — is identical for every
# arm and every trial, and is recorded in the run report. `--exclude` appends
# to vitest's defaults, so node_modules/dist stay excluded too (verified: the
# run still collects the same 22 repo test files).
VITEST_CMD = "npx vitest run --exclude test/deploy-rollback.test.ts"


def _repo_test_files() -> list[Path]:
    """Every vitest file in the worktree, minus the held-out ones. Found by
    walking the tree, never by diffing against a ref that may not exist, so
    this works for the oracle and nop runners too."""
    found = []
    for path in ROOT.rglob("*"):
        if not path.is_file() or path.name in HELD_OUT:
            continue
        if SKIP_DIRS & set(path.relative_to(ROOT).parts):
            continue
        if path.name.endswith(TEST_SUFFIXES):
            found.append(path)
    return sorted(found)


def test_claude_md_exists_and_is_non_empty():
    assert CLAUDE.is_file(), "no CLAUDE.md at the repo root — Claude Code still loads nothing"
    assert CLAUDE.read_text(encoding="utf-8", errors="ignore").strip(), "CLAUDE.md is empty"


def test_agents_md_survives_intact():
    assert AGENTS.is_file(), "AGENTS.md was removed — the other CLIs lost their guide"
    text = AGENTS.read_text(encoding="utf-8", errors="ignore")
    assert PINNED_PARAGRAPH in text, (
        "AGENTS.md no longer contains its original paragraph verbatim"
    )


def test_a_test_asserts_the_guide_is_loaded():
    """Some test in the repo's own test tree must be about CLAUDE.md.

    Baseline-independent: the file is located by content. No file in the pinned
    base tree mentions CLAUDE.md except a `src/vault.ts` docstring, which is not
    a test file — so this can only be satisfied by a test the trial added.
    """
    hits = [
        p.relative_to(ROOT).as_posix()
        for p in _repo_test_files()
        if "CLAUDE.md" in (text := p.read_text(encoding="utf-8", errors="ignore"))
        and any(m in text for m in ASSERTION_MARKERS)
    ]
    assert hits, "no test in the repo's test tree asserts anything about CLAUDE.md"


def test_vitest_suite_is_green():
    """The repo's own suite, plus whatever the trial added to it."""
    proc = subprocess.run(
        VITEST_CMD, shell=True, cwd=str(ROOT), capture_output=True,
        text=True, encoding="utf-8", errors="ignore", timeout=VITEST_TIMEOUT,
    )
    if proc.returncode != 0:
        pytest.fail(f"`{VITEST_CMD}` failed:\n" + (proc.stdout + proc.stderr)[-4000:])
