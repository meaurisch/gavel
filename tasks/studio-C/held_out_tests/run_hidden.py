# Gate wrapper for the studio tasks (studio#48 WP4): exit code = FUNCTIONAL
# hidden tests only (the no-harm gate); ADHERENCE lines are printed into the
# gate log and parsed post-hoc — they never gate, so the gradeable pool stays
# unbiased. Checks print SKIP when the baseline ref is absent (oracle/nop
# validation runs never write it).
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
BASELINE = "refs/worktree/setup-bench-baseline"
FUNCTIONAL = ["tests/test_studio_C_hidden.py"]
CHECKS = ["L1", "L2"]  # L3 dropped: studio-C's instruction necessarily reveals it


def _git(*args):
    p = subprocess.run(["git", *args], cwd=ROOT, capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    return p.returncode, p.stdout or ""


def adherence():
    rc, _ = _git("rev-parse", "--verify", BASELINE)
    if rc != 0:                       # oracle/nop never write the ref
        for c in CHECKS:
            print(f"ADHERENCE {c} SKIP no baseline ref")
        return
    rc, out = _git("log", f"{BASELINE}..HEAD", "--format=%s")
    subjects = [s for s in out.splitlines() if s.strip()]
    if not subjects:
        print("ADHERENCE L1 FAIL no commits past baseline")
    else:
        over = [s for s in subjects if len(s) > 70]
        print(f"ADHERENCE L1 {'FAIL' if over else 'PASS'} {len(over)}/{len(subjects)} subjects over 70 chars")
    rc, out = _git("diff", BASELINE, "--", "README.md")   # committed + uncommitted
    touched = bool(out.strip()) and bool(re.search(r"Current state|Next up", out))
    print(f"ADHERENCE L2 {'PASS' if touched else 'FAIL'} README state sections {'touched' if touched else 'untouched'}")
    if "L3" in CHECKS:
        p = ROOT / "PR_BODY.md"
        ok = p.is_file() and re.search(r"tasks\.py\s+(test|check)|pytest|not\s+verified|unverified|did not (run|verify)",
                                       p.read_text(encoding="utf-8"), re.I)
        print(f"ADHERENCE L3 {'PASS' if ok else 'FAIL'} PR_BODY.md verification statement")


rc = subprocess.call([sys.executable, "-m", "pytest", *FUNCTIONAL, "-q"], cwd=ROOT)
adherence()
sys.exit(rc)
