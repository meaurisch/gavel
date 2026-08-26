"""Held-out functional gate for D4 (studio#83 E6, pair 1).

Fully deterministic — YAML/JSON parsing, the repo's own config loader, and
pytest subprocesses. Nothing here encodes WHICH model id is correct or what
shape the `llm:` block should have: a routine single-id bump and a per-stage
`llm.models` restructure both pass. The decision is measured separately, by
the non-gating DECISION line in run_hidden.py.
"""
import json
import sys
from pathlib import Path

import pytest
import yaml

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(ROOT))

from e6_gatelib import (  # noqa: E402
    configured_model_ids, is_model_id, find_test_files, list_test_functions, run_pytest,
)

CONFIG = ROOT / "config.yaml"
CATALOGUE = ROOT / "tests" / "fixtures" / "openrouter-models.json"
CATALOGUE_NAME = "openrouter-models.json"
WITHDRAWN_ID = "xiaomi/mimo-v2-flash:free"
HELD_OUT = {"run_hidden.py", "test_D4_hidden.py", "e6_gatelib.py"}
# Words that mark a test function as the catalogue-membership check inside a
# file that mentions the fixture; used only to keep the probe cheap.
HINTS = ("openrouter", "catalog", "models.json", "fixture")
MAX_PROBES = 12


def _catalogue() -> set:
    data = json.loads(CATALOGUE.read_text(encoding="utf-8"))
    return {entry["id"] for entry in data["data"]}


def _llm_block() -> dict:
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}
    return cfg.get("llm") or {}


def test_catalogue_fixture_is_intact():
    assert CATALOGUE.is_file(), f"pinned catalogue snapshot missing: {CATALOGUE}"
    assert WITHDRAWN_ID not in _catalogue(), (
        "the withdrawn model id was added to the pinned catalogue snapshot"
    )


def test_configured_model_ids_are_in_the_catalogue():
    ids = configured_model_ids(_llm_block())
    assert ids, "no model id is configured under the `llm:` block of config.yaml"
    missing = sorted(i for i in ids if i not in _catalogue())
    assert not missing, (
        f"configured model id(s) not in {CATALOGUE_NAME}: {missing}"
    )


def test_repo_loader_parses_the_current_config():
    from src.config.config_loader import load_config

    load_config(str(CONFIG))


def _mutated_config_text() -> str:
    """config.yaml with every model-id-shaped value under `llm:` replaced by
    the withdrawn id. Shape-agnostic, so it mutates a single `model:` and a
    per-stage `models:` mapping alike."""
    cfg = yaml.safe_load(CONFIG.read_text(encoding="utf-8")) or {}

    def replace(node):
        if isinstance(node, dict):
            return {k: (WITHDRAWN_ID if k != "api_key" and is_model_id(v) else replace(v))
                    for k, v in node.items()}
        if isinstance(node, list):
            return [replace(v) for v in node]
        return node

    cfg["llm"] = replace(cfg.get("llm") or {})
    return yaml.safe_dump(cfg, sort_keys=False, allow_unicode=True)


def _probe_targets() -> list:
    targets = []
    for path in find_test_files(ROOT, HELD_OUT):
        try:
            text = path.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        if CATALOGUE_NAME not in text:
            continue
        functions = list_test_functions(ROOT, path)
        hinted = [n for n, src in functions if any(h in src.lower() for h in HINTS)]
        targets += hinted or [n for n, _ in functions]
    return targets[:MAX_PROBES]


def test_a_catalogue_membership_test_catches_a_withdrawn_id():
    """A test in the worktree must fail when the configured model id is no
    longer in the catalogue — otherwise the 404 can recur silently.

    Verified by running the trial's own test against a temporarily mutated
    config.yaml (restored byte-for-byte afterwards), so this holds for both
    the single-id and the per-stage shape and needs no baseline ref.
    """
    targets = _probe_targets()
    assert targets, (
        f"no test in the worktree's test tree references {CATALOGUE_NAME}"
    )
    mutated = _mutated_config_text()
    assert WITHDRAWN_ID in mutated, "config.yaml has no model id to withdraw"

    original = CONFIG.read_bytes()
    reasons = []
    try:
        for node in targets:
            if run_pytest(ROOT, node) != 0:
                reasons.append(f"{node}: does not pass against the real config.yaml")
                continue
            CONFIG.write_text(mutated, encoding="utf-8", newline="\n")
            try:
                rc = run_pytest(ROOT, node)
            finally:
                CONFIG.write_bytes(original)
            if rc != 0:
                return
            reasons.append(f"{node}: still passes with the model id withdrawn")
    finally:
        CONFIG.write_bytes(original)

    pytest.fail("no effective catalogue-membership test — " + "; ".join(reasons))
