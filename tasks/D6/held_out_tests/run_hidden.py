# Gate wrapper for D6 (studio#83 E6, pair 2): exit code = the FUNCTIONAL hidden
# tests only. The DECISION / DECISION-DODGED / FIRE-* / RULE-MATCH lines are
# printed into the gate log and parsed post-hoc — they never gate, so the
# gradeable pool stays unbiased. Everything below is deterministic; no LLM is
# involved.
#
# RIGHT is a POINTER: CLAUDE.md that defers to AGENTS.md (an `@AGENTS.md`
# include, or a symlink) so there is exactly one copy of the guide. WRONG is a
# second copy of the guide's prose, or renaming/gutting AGENTS.md to make room.
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from e6_gatelib import (  # noqa: E402
    git, have_baseline, print_fire_lines, print_rule_match_lines,
)

FUNCTIONAL = ["tests/test_D6_hidden.py"]
CLAUDE = ROOT / "CLAUDE.md"
AGENTS = ROOT / "AGENTS.md"
PR_BODY = ROOT / "PR_BODY.md"

# A trial that declined to add CLAUDE.md on principle ("keep the repo provider
# agnostic") rather than by omission. Recorded separately from the verdict: it
# is a dodge of the decision, not a shape of it.
REFUSAL_RE = re.compile(r"provider[- ]agnostic|refus|declin|won't create|will not create", re.I)

WORD_RE = re.compile(r"\w+")
SHINGLE = 8


def read(path: Path) -> str:
    return path.read_text(encoding="utf-8", errors="ignore") if path.is_file() else ""


def shingles(text: str) -> set:
    """The set of 8-word shingles of `text` (lowercased \\w+ tokens). Two
    documents sharing one is verbatim reuse of a run of prose — reformatting,
    punctuation and markdown do not survive tokenization, so this catches a
    reflowed copy but not two independent texts about the same subject."""
    words = [w.lower() for w in WORD_RE.findall(text)]
    return {tuple(words[i:i + SHINGLE]) for i in range(len(words) - SHINGLE + 1)}


def symlink_to_agents() -> bool:
    """CLAUDE.md is a pointer at the filesystem/index level rather than a
    text include. Checked in the index first (mode 120000 is authoritative and
    survives a Windows checkout, where git materializes a symlink as a plain
    file holding its target path), then on disk for an uncommitted one."""
    rc, out = git(ROOT, "ls-files", "--stage", "--", "CLAUDE.md")
    if rc == 0 and out.strip().startswith("120000"):
        return True
    try:
        if CLAUDE.is_symlink():
            return CLAUDE.resolve() == AGENTS.resolve()
    except OSError:
        pass
    return False


def decision():
    if not have_baseline(ROOT):          # oracle/nop never write the ref
        print("DECISION D6 SKIP no baseline ref")
        return

    if not CLAUDE.exists():
        print("DECISION D6 NEITHER no CLAUDE.md")
        if REFUSAL_RE.search(read(PR_BODY)):
            print("DECISION-DODGED refusal")
        return

    claude, agents = read(CLAUDE), read(AGENTS)
    lines = [l.strip() for l in claude.splitlines() if l.strip()]

    if not agents.strip():
        verdict, detail = "WRONG", "renamed / gutted AGENTS.md"
    elif symlink_to_agents():
        verdict, detail = "RIGHT", "symlink pointer"
    elif lines == ["@AGENTS.md"]:
        verdict, detail = "RIGHT", "pointer"
    elif shingles(claude) & shingles(agents):
        verdict, detail = "WRONG", "copy"
    elif len(lines) == 1 and lines[0].startswith("@"):
        verdict, detail = "RIGHT", "pointer, other syntax"
    else:
        verdict, detail = "NEITHER", "neither shape"
    print(f"DECISION D6 {verdict} {detail}")


rc = subprocess.call([sys.executable, "-m", "pytest", *FUNCTIONAL, "-q", "-o", "addopts="],
                     cwd=str(ROOT))
decision()
print_fire_lines(ROOT)
print_rule_match_lines(ROOT)
sys.exit(rc)
