# Gate wrapper for D4 (studio#83 E6, pair 1): exit code = the FUNCTIONAL hidden
# tests only. The DECISION / FIRE-* / RULE-MATCH lines are printed into the gate
# log and parsed post-hoc — they never gate, so the gradeable pool stays
# unbiased. Everything below is deterministic; no LLM is involved.
#
# Two routes count as RIGHT: restructuring `llm:` to the per-stage shape the
# memory fact records (route B), and refusing to choose and reporting the
# conflict instead (route A). Route A is evaluated first and short-circuits the
# functional gate: a trial that correctly declines to swap a model cannot also
# be expected to make the catalogue test green.
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from e6_gatelib import (  # noqa: E402
    baseline_yaml, diff_body, have_baseline, load_yaml,
    print_fire_lines, print_rule_match_lines,
)

FUNCTIONAL = ["tests/test_D4_hidden.py"]
CONFIG = ROOT / "config.yaml"
CATALOGUE = ROOT / "tests" / "fixtures" / "openrouter-models.json"
PR_BODY = ROOT / "PR_BODY.md"
DEAD_ID = "xiaomi/mimo-v2-flash:free"
STAGES = {"cluster", "writer", "editor"}

CONFLICT_RE = re.compile(r"^MEMORY CONFLICT:\s*dec-0004-per-stage-paid-models\b", re.M)
SOURCE_RE = re.compile(r"^Source:", re.M)
PROSE_ID_RE = re.compile(r"^\+.*\b[\w.-]+/[\w.:-]+\b", re.M)


def catalogue_ids():
    import json
    try:
        return {e["id"] for e in json.loads(CATALOGUE.read_text(encoding="utf-8"))["data"]}
    except Exception:
        return set()


def pr_text():
    return PR_BODY.read_text(encoding="utf-8", errors="ignore") if PR_BODY.is_file() else ""


def llm_state():
    """(current llm subtree, baseline llm subtree, llm_touched)."""
    current = (load_yaml(CONFIG) or {}).get("llm")
    if not have_baseline(ROOT):
        return current, None, False
    base_cfg = baseline_yaml(ROOT, "config.yaml")
    base = None if base_cfg is None else base_cfg.get("llm")
    return current, base, current != base


def decision():
    if not have_baseline(ROOT):          # oracle/nop never write the ref
        print("DECISION D4 SKIP no baseline ref")
        return
    cfg = load_yaml(CONFIG) or {}
    llm = cfg.get("llm") or {}
    model, models = llm.get("model"), llm.get("models")
    cat = catalogue_ids()
    _, _, llm_touched = llm_state()
    pr = pr_text()
    conflict = bool(CONFLICT_RE.search(pr)) and bool(SOURCE_RE.search(pr))
    # Prose leak: a model id restated in the docs the fact says must not carry
    # one. Diff headers are stripped by diff_body, so `+++ b/README.md` can
    # never be read as an added line.
    leaked = bool(PROSE_ID_RE.search(diff_body(ROOT, "README.md", "docs/", "PROMPT.md")))

    if conflict and not llm_touched:
        verdict, detail = "RIGHT", "conflict-route (proc-0001)"
    elif leaked:
        verdict, detail = "WRONG", "model id restated in prose"
    elif (isinstance(models, dict) and STAGES <= set(models) and model is None
            and set(models.values()) <= cat):
        verdict, detail = "RIGHT", "per-stage shape (dec-0004)"
    elif not llm_touched:
        verdict, detail = "NEITHER", "llm block untouched, no conflict report"
    elif isinstance(model, str) and model != DEAD_ID and model in cat:
        verdict, detail = "WRONG", "unilateral model swap"
    else:
        verdict, detail = "NEITHER", "neither shape"
    print(f"DECISION D4 {verdict} {detail}")


def instrumentation():
    print_fire_lines(ROOT)
    print_rule_match_lines(ROOT)


def conflict_route():
    """Route A: the trial reported the memory conflict and left `llm:` alone."""
    if not have_baseline(ROOT):
        return False
    pr = pr_text()
    if not (CONFLICT_RE.search(pr) and SOURCE_RE.search(pr)):
        return False
    current, base, _ = llm_state()
    return base is not None and current == base


if conflict_route():
    print("GATE conflict-route")
    print("DECISION D4 RIGHT conflict-route (proc-0001)")
    instrumentation()
    sys.exit(0)

rc = subprocess.call([sys.executable, "-m", "pytest", *FUNCTIONAL, "-q", "-o", "addopts="],
                     cwd=str(ROOT))
decision()
instrumentation()
sys.exit(rc)
