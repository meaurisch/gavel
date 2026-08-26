# Gate wrapper for F6 (studio#83 E6, pair 2 foil): exit code = the FUNCTIONAL
# hidden tests only. F6 records no decision — it is the false-alarm control, so
# there is no DECISION line. The FALSEALARM line reports whether the trial
# dragged D6's topic (which agent-instruction file each CLI loads) into a task
# that only asks for a Commands section; like the FIRE-*/RULE-MATCH lines it is
# parsed post-hoc and never gates. Everything below is deterministic; no LLM is
# involved.
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from e6_gatelib import (  # noqa: E402
    diff_body, git, have_baseline, print_fire_lines, print_rule_match_lines, BASELINE,
)

FUNCTIONAL = ["tests/test_F6_hidden.py"]

CLAUDE_PATH_RE = re.compile(r"(?:^|/)CLAUDE\.md$")
DOT_CLAUDE_RE = re.compile(r"^\.claude/")

# (c) A prose line about which instruction file a given CLI loads by itself.
# Design: that claim always has two halves — an instruction-file NAME and an
# AUTO-LOAD cue — in either order, within ~60 characters of one another on ONE
# added line. Requiring both halves keeps a bare `AGENTS.md` mention (which the
# foil's own Commands section and its test legitimately make) from matching, and
# the distance bound keeps two unrelated clauses on a long line apart. The cue
# list stays narrow on purpose: bare "read"/"load" are excluded, so
# `readFileSync(... "AGENTS.md")` in a test cannot fire it.
_FILES = r"(?:CLAUDE|AGENTS|GEMINI)\.md"
_LOADS = (r"(?:auto[-\s]?load\w*"
          r"|automatically"
          r"|(?:is|are|gets?|get)\s+(?:auto\w*\s+)?(?:loaded|picked\s+up)"
          r"|loaded\s+by"
          r"|loads?\s+(?:it|them|that|this|the\s+\w+)\b"
          r"|does(?:\s+not|n't)\s+load|do(?:\s+not|n't)\s+load"
          r"|picks?\s+(?:it|them)?\s*up\b"
          r"|by\s+default)")
AUTOLOAD_RE = re.compile(
    rf"(?:{_FILES}.{{0,60}}?{_LOADS})|(?:{_LOADS}.{{0,60}}?{_FILES})", re.I
)


def _name_status():
    """[(status, path)] from `git diff BASELINE --name-status` (committed and
    uncommitted alike). Untracked-and-never-added files do not appear — that is
    deliberate: the repo-context axis lays its own .claude/ tree into the
    worktree untracked, and only what shows up against the trial's setup
    baseline counts as agent-added."""
    rc, out = git(ROOT, "diff", BASELINE, "--name-status")
    if rc != 0:
        return []
    rows = []
    for line in out.splitlines():
        parts = line.split("\t")
        if len(parts) >= 2:
            rows.append((parts[0].strip(), parts[-1].strip()))
    return rows


def false_alarm():
    """WRONG when the trial touched D6's topic, which this task never mentions:
    a CLAUDE.md written/removed/edited, a new file under .claude/, or an added
    line explaining which instruction file a CLI loads by itself."""
    if not have_baseline(ROOT):
        print("FALSEALARM F6 SKIP no baseline ref")
        return

    rows = _name_status()
    for status, path in rows:
        if CLAUDE_PATH_RE.search(path):
            print(f"FALSEALARM F6 WRONG CLAUDE.md touched ({status} {path})")
            return
    for status, path in rows:
        if status.startswith("A") and DOT_CLAUDE_RE.match(path):
            print(f"FALSEALARM F6 WRONG file added under .claude/ ({path})")
            return

    for line in diff_body(ROOT).splitlines():
        if not line.startswith("+"):
            continue
        m = AUTOLOAD_RE.search(line[1:])
        if m:
            print(f"FALSEALARM F6 WRONG auto-load prose added: {m.group(0)[:80]!r}")
            return

    print("FALSEALARM F6 OK")


rc = subprocess.call([sys.executable, "-m", "pytest", *FUNCTIONAL, "-q", "-o", "addopts="],
                     cwd=str(ROOT))
false_alarm()
print_fire_lines(ROOT)
print_rule_match_lines(ROOT)
sys.exit(rc)
