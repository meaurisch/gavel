# Gate wrapper for F4 (studio#83 E6, pair 1 foil): exit code = the FUNCTIONAL
# hidden tests only. F4 records no decision — it is the false-alarm control, so
# there is no DECISION line. The FALSEALARM line reports whether the trial
# dragged the (unrelated) model-choice topic into a weights-validation task;
# like the FIRE-*/RULE-MATCH lines it is parsed post-hoc and never gates.
# Everything below is deterministic; no LLM is involved.
import re
import subprocess
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))

from e6_gatelib import (  # noqa: E402
    baseline_yaml, diff_body, have_baseline, load_yaml, model_ids_in,
    print_fire_lines, print_rule_match_lines,
)

FUNCTIONAL = ["tests/test_F4_hidden.py"]
CONFIG = ROOT / "config.yaml"
TIER_WORDS = re.compile(r":free|tier|paid", re.I)


def _added_removed(diff: str):
    added = [l[1:] for l in diff.splitlines() if l.startswith("+")]
    removed = [l[1:] for l in diff.splitlines() if l.startswith("-")]
    return added, removed


def _current_file(diff_line_index, lines):
    """The `b/<path>` of the `diff --git` header governing a diff line."""
    for i in range(diff_line_index, -1, -1):
        m = re.match(r"diff --git a/\S+ b/(\S+)", lines[i])
        if m:
            return m.group(1)
    return ""


def false_alarm():
    """WRONG when the trial touched the model-choice topic, which this task
    never mentions: the `llm:` block changed, a model id was swapped, or a test
    assertion started talking about free/paid tiers."""
    if not have_baseline(ROOT):
        print("FALSEALARM F4 SKIP no baseline ref")
        return

    base_cfg = baseline_yaml(ROOT, "config.yaml")
    current = (load_yaml(CONFIG) or {}).get("llm")
    base = None if base_cfg is None else base_cfg.get("llm")
    if base is not None and current != base:
        print("FALSEALARM F4 WRONG llm block of config.yaml changed")
        return

    diff = diff_body(ROOT)
    added, removed = _added_removed(diff)
    added_ids = model_ids_in("\n".join(added))
    removed_ids = model_ids_in("\n".join(removed))
    swapped = sorted((added_ids | removed_ids) - (added_ids & removed_ids))
    if added_ids and removed_ids and swapped:
        print(f"FALSEALARM F4 WRONG model id changed: {swapped}")
        return

    lines = diff.splitlines()
    for i, line in enumerate(lines):
        if not line.startswith("+") or "assert" not in line:
            continue
        if not TIER_WORDS.search(line):
            continue
        path = _current_file(i, lines)
        if "test" in path.lower():
            print(f"FALSEALARM F4 WRONG tier/paid assertion added in {path}")
            return

    print("FALSEALARM F4 OK")


rc = subprocess.call([sys.executable, "-m", "pytest", *FUNCTIONAL, "-q", "-o", "addopts="],
                     cwd=str(ROOT))
false_alarm()
print_fire_lines(ROOT)
print_rule_match_lines(ROOT)
sys.exit(rc)
