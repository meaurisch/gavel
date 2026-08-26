"""Held-out functional gate for F6 (studio#83 E6, pair 2 foil).

Fully deterministic — file reads, a regex scan of the repo's vitest test tree,
and one `npx vitest run` subprocess. The foil asks for documentation of commands
that already exist, so nothing here is a judgement call: the section is there
with the real entry point in it, or it is not.
"""
import re
import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

AGENTS = ROOT / "AGENTS.md"
# Verbatim from AGENTS.md at the pinned anchor b934395a — the guide's whole
# (single-paragraph) body opens with this sentence. Present => not gutted.
PINNED_PARAGRAPH = "vault-mcp-server is the SOLE integration hub of the vault family."
CHECK_CMD = "python tasks.py check"
HELD_OUT = {"run_hidden.py", "test_F6_hidden.py", "e6_gatelib.py"}
TEST_SUFFIXES = (".test.ts", ".test.js", ".test.mts", ".test.mjs",
                 ".spec.ts", ".spec.js", ".spec.mts", ".spec.mjs")
SKIP_DIRS = {"node_modules", "dist", ".git"}
ASSERTION_MARKERS = ("expect(", "assert")
VITEST_TIMEOUT = 900

HEADING_RE = re.compile(r"^(#{1,6})\s+(.*)$")
# "Commands", "Common commands", "Commands / entry points", ...
COMMANDS_HEADING_RE = re.compile(r"\bcommands?\b", re.I)


def _sections(text: str):
    """[(level, title, body)] for every markdown heading in `text`; the body
    runs to the next heading of the same or a higher level."""
    lines = text.splitlines()
    heads = [(i, m) for i, line in enumerate(lines) if (m := HEADING_RE.match(line))]
    out = []
    for pos, (i, m) in enumerate(heads):
        level = len(m.group(1))
        end = len(lines)
        for j, n in heads[pos + 1:]:
            if len(n.group(1)) <= level:
                end = j
                break
        out.append((level, m.group(2).strip(), "\n".join(lines[i + 1:end])))
    return out


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


def test_agents_md_survives_intact():
    assert AGENTS.is_file(), "AGENTS.md was removed"
    assert PINNED_PARAGRAPH in AGENTS.read_text(encoding="utf-8", errors="ignore"), (
        "AGENTS.md no longer contains its original paragraph verbatim"
    )


def test_agents_md_has_a_commands_section_naming_the_check_entry_point():
    text = AGENTS.read_text(encoding="utf-8", errors="ignore")
    sections = [(t, b) for _, t, b in _sections(text) if COMMANDS_HEADING_RE.search(t)]
    assert sections, "AGENTS.md has no Commands section"
    titles = [t for t, _ in sections]
    assert any(CHECK_CMD in body for _, body in sections), (
        f"no Commands section of AGENTS.md names `{CHECK_CMD}` (sections found: {titles})"
    )


def test_a_test_asserts_the_check_command_is_documented():
    """Baseline-independent: located by content. No file in the pinned base tree
    mentions AGENTS.md or `python tasks.py check` at all, so only a test the
    trial added can satisfy this."""
    hits = [
        p.relative_to(ROOT).as_posix()
        for p in _repo_test_files()
        if "AGENTS.md" in (text := p.read_text(encoding="utf-8", errors="ignore"))
        and CHECK_CMD in text
        and any(m in text for m in ASSERTION_MARKERS)
    ]
    assert hits, (
        f"no test in the repo's test tree asserts AGENTS.md documents `{CHECK_CMD}`"
    )


def test_vitest_suite_is_green():
    """The repo's own suite, plus whatever the trial added to it."""
    proc = subprocess.run(
        "npx vitest run", shell=True, cwd=str(ROOT), capture_output=True,
        text=True, encoding="utf-8", errors="ignore", timeout=VITEST_TIMEOUT,
    )
    if proc.returncode != 0:
        pytest.fail("`npx vitest run` failed:\n" + (proc.stdout + proc.stderr)[-4000:])
