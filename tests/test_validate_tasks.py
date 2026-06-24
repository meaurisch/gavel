import sys
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(PROJECT_ROOT / "scripts"))

import validate_tasks as vt  # noqa: E402


def test_render_summary_all_ok():
    results = [{
        "task_id": "pyvrp-A", "build_gate": True,
        "fail_to_pass": True, "pass_to_pass": True, "errors": [],
    }]
    text, ok = vt.render_transitions_summary(results)
    assert ok is True
    assert "pyvrp-A" in text
    assert "OK" in text


def test_render_summary_flags_weak_tests():
    results = [{
        "task_id": "pyvrp-B", "build_gate": True,
        "fail_to_pass": False, "pass_to_pass": True,
        "errors": ["FAIL_TO_PASS: tests PASSED on clean base (too weak)"],
    }]
    text, ok = vt.render_transitions_summary(results)
    assert ok is False
    assert "too weak" in text
    assert "PROBLEM" in text


def test_render_summary_skipped_build_is_ok():
    results = [{
        "task_id": "pyvrp-C", "build_gate": None,
        "fail_to_pass": True, "pass_to_pass": True, "errors": [],
    }]
    text, ok = vt.render_transitions_summary(results)
    assert ok is True
    assert "SKIP" in text
