from unittest.mock import patch
import pytest
from core.matrix import expand, HARNESS_MAP
from core.models import Trial


def test_expand_single_cell():
    with patch("core.matrix.load_methodology"):
        trials = expand(["task-A"], ["baseline"], ["model-1"], "claude-code", 1)
    assert len(trials) == 1
    t = trials[0]
    assert t.id == "task-A_baseline_model-1_claude-code_0"
    assert t.task_id == "task-A"
    assert t.methodology_id == "baseline"
    assert t.model == "model-1"
    assert t.runner == "claude-code"
    assert t.rep == 0


def test_expand_cartesian():
    with patch("core.matrix.load_methodology"):
        trials = expand(["t1", "t2"], ["s1", "s2"], ["m1", "m2"], "claude-code", 2)
    assert len(trials) == 16


def test_expand_filters_incompatible_methodologies():
    def fake_load(methodology_id, harness):
        if methodology_id == "bad":
            raise ValueError("no harness")

    with patch("core.matrix.load_methodology", side_effect=fake_load):
        trials = expand(["t1"], ["good", "bad"], ["m1"], "claude-code", 1)
    assert len(trials) == 1
    assert trials[0].methodology_id == "good"


def test_expand_reps():
    with patch("core.matrix.load_methodology"):
        trials = expand(["t1"], ["s1"], ["m1"], "nop", 3)
    assert len(trials) == 3
    assert [t.rep for t in trials] == [0, 1, 2]


def test_expand_empty_models():
    with patch("core.matrix.load_methodology"):
        trials = expand(["t1"], ["s1"], [], "claude-code", 1)
    assert trials == []


def test_harness_map_keys():
    assert HARNESS_MAP["claude-code"] == "claude-code"
    assert HARNESS_MAP["copilot-cli"] == "copilot"
    assert HARNESS_MAP["oracle"] == "claude-code"
    assert HARNESS_MAP["nop"] == "claude-code"
    assert HARNESS_MAP["manual"] == "claude-code"
