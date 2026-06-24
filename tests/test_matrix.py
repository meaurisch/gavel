from unittest.mock import patch
import pytest
from core.matrix import expand, HARNESS_MAP
from core.models import Trial


def _patch_loaders(affinity=None):
    """Patch matrix loaders so expand() runs without touching the filesystem.

    affinity: dict mapping repo_context_id -> task_affinity list (default empty).
    """
    affinity = affinity or {}

    def fake_affinity(rc):
        return affinity.get(rc, [])

    return (
        patch("core.matrix.load_methodology"),
        patch("core.matrix.load_repo_context"),
        patch("core.matrix.get_task_affinity", side_effect=fake_affinity),
    )


def test_expand_single_cell():
    p1, p2, p3 = _patch_loaders()
    with p1, p2, p3:
        trials = expand(["task-A"], ["baseline"], ["none"], ["model-1"], "claude-code", 1)
    assert len(trials) == 1
    t = trials[0]
    assert t.id == "task-A_baseline_none_model-1_claude-code_0"
    assert t.task_id == "task-A"
    assert t.methodology_id == "baseline"
    assert t.repo_context_id == "none"
    assert t.model == "model-1"
    assert t.runner == "claude-code"
    assert t.rep == 0


def test_expand_cartesian():
    p1, p2, p3 = _patch_loaders()
    with p1, p2, p3:
        trials = expand(["t1", "t2"], ["s1", "s2"], ["rc1", "rc2"], ["m1", "m2"], "claude-code", 2)
    # 2 tasks x 2 methodologies x 2 contexts x 2 models x 2 reps
    assert len(trials) == 32


def test_expand_filters_incompatible_methodologies():
    def fake_load(methodology_id, harness):
        if methodology_id == "bad":
            raise ValueError("no harness")

    _, p2, p3 = _patch_loaders()
    with patch("core.matrix.load_methodology", side_effect=fake_load), p2, p3:
        trials = expand(["t1"], ["good", "bad"], ["none"], ["m1"], "claude-code", 1)
    assert len(trials) == 1
    assert trials[0].methodology_id == "good"


def test_expand_filters_incompatible_repo_contexts():
    def fake_load(context_id, harness):
        if context_id == "bad":
            raise FileNotFoundError("missing content")

    p1, _, p3 = _patch_loaders()
    with p1, patch("core.matrix.load_repo_context", side_effect=fake_load), p3:
        trials = expand(["t1"], ["s1"], ["good", "bad"], ["m1"], "claude-code", 1)
    assert len(trials) == 1
    assert trials[0].repo_context_id == "good"


def test_expand_affinity_skips_unmatched_task():
    # rc-only-t1 only applies to task t1
    p1, p2, p3 = _patch_loaders(affinity={"rc-only-t1": ["t1"]})
    with p1, p2, p3:
        trials = expand(["t1", "t2"], ["s1"], ["none", "rc-only-t1"], ["m1"], "claude-code", 1)
    pairs = {(t.task_id, t.repo_context_id) for t in trials}
    # none applies to both tasks; rc-only-t1 only to t1
    assert ("t1", "rc-only-t1") in pairs
    assert ("t2", "rc-only-t1") not in pairs
    assert ("t1", "none") in pairs
    assert ("t2", "none") in pairs


def test_expand_full_matrix_ignores_affinity():
    p1, p2, p3 = _patch_loaders(affinity={"rc-only-t1": ["t1"]})
    with p1, p2, p3:
        filtered = expand(["t1", "t2"], ["s1"], ["none", "rc-only-t1"], ["m1"], "claude-code", 1)
    p1, p2, p3 = _patch_loaders(affinity={"rc-only-t1": ["t1"]})
    with p1, p2, p3:
        full = expand(["t1", "t2"], ["s1"], ["none", "rc-only-t1"], ["m1"], "claude-code", 1, full_matrix=True)
    # full_matrix re-adds the (t2, rc-only-t1) combo that affinity skipped
    assert len(full) > len(filtered)
    assert ("t2", "rc-only-t1") in {(t.task_id, t.repo_context_id) for t in full}


def test_expand_reps():
    p1, p2, p3 = _patch_loaders()
    with p1, p2, p3:
        trials = expand(["t1"], ["s1"], ["none"], ["m1"], "nop", 3)
    assert len(trials) == 3
    assert [t.rep for t in trials] == [0, 1, 2]


def test_expand_empty_models():
    p1, p2, p3 = _patch_loaders()
    with p1, p2, p3:
        trials = expand(["t1"], ["s1"], ["none"], [], "claude-code", 1)
    assert trials == []


def test_harness_map_keys():
    assert HARNESS_MAP["claude-code"] == "claude-code"
    assert HARNESS_MAP["copilot-cli"] == "copilot"
    assert HARNESS_MAP["oracle"] == "claude-code"
    assert HARNESS_MAP["nop"] == "claude-code"
    assert HARNESS_MAP["manual"] == "claude-code"
