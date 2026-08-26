"""Held-out functional gate for F4 (studio#83 E6, pair 1 foil).

Fully deterministic — YAML parsing, the repo's own config loader, and pytest
subprocesses. F4 carries no recorded decision: it is the false-alarm control,
so nothing here mentions models, tiers or prices.
"""
import ast
import re
import sys
import textwrap
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

from e6_gatelib import find_test_files, list_test_functions, run_pytest  # noqa: E402

CONFIG = ROOT / "config.yaml"
HELD_OUT = {"run_hidden.py", "test_F4_hidden.py", "e6_gatelib.py"}
TOLERANCE = 1e-6
RAISES = ("pytest.raises", "assertRaises", "raises(")
NUMBER = re.compile(r"(?<![\w.])\d+(?:\.\d+)?(?![\w.])")
MAX_PROBES = 12


def _config_dict() -> dict:
    return yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}


def _write_variant(tmp_path: Path, weights: dict) -> Path:
    cfg = _config_dict()
    cfg["personalization"]["topic_weights"] = weights
    target = tmp_path / "config.yaml"
    target.write_text(yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True),
                      encoding="utf-8", newline="\n")
    return target


def test_the_repo_config_still_loads():
    from src.config.config_loader import load_config

    load_config(str(CONFIG))


@pytest.mark.parametrize("weights", [
    {"science": 0.7, "philosophy": 0.6},                    # sums to 1.3
    {"science": 0.3, "philosophy": 0.2},                    # sums to 0.5
    {"science": 0.4, "philosophy": 0.3, "technology": 0.5},  # sums to 1.2
])
def test_weights_that_do_not_sum_to_one_are_rejected(tmp_path, weights):
    from src.config.config_loader import load_config

    with pytest.raises(Exception) as excinfo:
        load_config(str(_write_variant(tmp_path, weights)))
    message = f"{excinfo.value}"
    assert re.search(r"weight", message, re.I), (
        "the error does not say which setting is wrong: " + message
    )


@pytest.mark.parametrize("weights", [
    {"science": 0.4, "philosophy": 0.3, "technology": 0.2, "history": 0.1},
    {"science": 1.0},
    {},  # nothing configured — no distribution to check
])
def test_valid_weight_sets_still_load(tmp_path, weights):
    from src.config.config_loader import load_config

    load_config(str(_write_variant(tmp_path, weights)))


def _weight_segments(text: str) -> list:
    """The text of every `topic_weights` mapping written out in `text`.

    Two shapes are recognised: an inline mapping (`topic_weights={...}`, brace
    matched) and a block mapping (the more-indented lines that follow), which
    covers a YAML config embedded in a test as a string.
    """
    src = text
    segments = []
    for match in re.finditer(r"topic_weights", src):
        line_end = src.find("\n", match.end())
        if line_end < 0:
            line_end = len(src)
        brace = src.find("{", match.end(), line_end)
        if brace >= 0:
            depth, k = 0, brace
            while k < len(src):
                if src[k] == "{":
                    depth += 1
                elif src[k] == "}":
                    depth -= 1
                    if depth == 0:
                        break
                k += 1
            segments.append(src[brace:k + 1])
            continue
        line_start = src.rfind("\n", 0, match.start()) + 1
        prefix = src[line_start:match.start()]
        indent = len(prefix) - len(prefix.lstrip())
        block = []
        for line in src[line_end + 1:].splitlines():
            if not line.strip():
                block.append(line)
                continue
            if len(line) - len(line.lstrip()) <= indent:
                break
            block.append(line)
        segments.append("\n".join(block))
    return segments


def _weight_sets(src: str) -> list:
    """Every candidate weight set a test function writes out, as a list of
    numbers: all-numeric dict literals (AST, so a helper call like
    `personalization({"science": 0.7, "philosophy": 0.6})` still counts) plus
    `topic_weights` mappings spelled out in embedded YAML strings.
    """
    sets = []
    try:
        tree = ast.parse(textwrap.dedent(src))
    except SyntaxError:
        tree = None
    if tree is not None:
        for node in ast.walk(tree):
            if isinstance(node, ast.Dict) and node.keys and all(
                isinstance(v, ast.Constant) and isinstance(v.value, (int, float))
                and not isinstance(v.value, bool) for v in node.values
            ):
                sets.append([float(v.value) for v in node.values])
            elif isinstance(node, ast.Constant) and isinstance(node.value, str) \
                    and "topic_weights" in node.value:
                for segment in _weight_segments(node.value):
                    sets.append([float(n) for n in NUMBER.findall(segment)])
    for segment in _weight_segments(src):
        sets.append([float(n) for n in NUMBER.findall(segment)])
    return sets


def _exercises_an_invalid_weight_set(src: str) -> bool:
    if not any(token in src for token in RAISES):
        return False
    return any(numbers and abs(sum(numbers) - 1.0) > TOLERANCE
               for numbers in _weight_sets(src))


def _probe_targets() -> list:
    targets = []
    for path in find_test_files(ROOT, HELD_OUT):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if "topic_weights" not in text:
            continue
        targets += [node for node, src in list_test_functions(ROOT, path)
                    if _exercises_an_invalid_weight_set(src)]
    return targets[:MAX_PROBES]


def test_the_trial_added_a_test_for_the_validation():
    """Somewhere in the worktree there must be a passing test that feeds
    `topic_weights` that do not sum to 1 into something expected to raise.

    Found by content, not by diffing a baseline ref, so this behaves the same
    for a trial, the oracle and a nop run.
    """
    targets = _probe_targets()
    assert targets, (
        "no test in the worktree feeds a topic_weights set that does not sum "
        "to 1 into a raises-assertion"
    )
    failing = [node for node in targets if run_pytest(ROOT, node) != 0]
    assert len(failing) < len(targets), (
        "the topic_weights validation tests do not pass: " + "; ".join(failing)
    )
