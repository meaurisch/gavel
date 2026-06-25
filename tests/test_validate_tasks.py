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


# --- static rubric lint checks ---

def _complete_task() -> dict:
    return {
        "id": "pyvrp-X",
        "base_commit": "abc123",
        "instruction": "Add a ReplaceGroup local-search operator to pyvrp.search "
        "so VRP variants with mutually-exclusive client groups get better placements.",
        "run_cmd": "pytest tests/search/test_ReplaceGroup.py -v",
        "held_out_tests_path": "tasks/pyvrp-X/held_out_tests",
        "reference_diff_path": "tasks/pyvrp-X/reference.diff",
        "build_cmd": "pip install -e . 2>&1",
    }


def test_check_required_fields_passes_complete():
    assert vt.check_required_fields(_complete_task()).status == "PASS"


def test_check_required_fields_flags_missing():
    task = _complete_task()
    del task["run_cmd"]
    c = vt.check_required_fields(task)
    assert c.status == "FAIL"
    assert "run_cmd" in c.detail


def test_check_required_fields_flags_empty():
    task = _complete_task()
    task["base_commit"] = "   "
    c = vt.check_required_fields(task)
    assert c.status == "FAIL"
    assert "base_commit" in c.detail


def test_check_instruction_length_floor():
    assert vt.check_instruction_length("too short").status == "FAIL"


def test_check_instruction_length_ok():
    assert vt.check_instruction_length(_complete_task()["instruction"]).status == "PASS"


def test_check_instruction_length_warns_when_overlong():
    long = " ".join(["word"] * 400)
    assert vt.check_instruction_length(long).status == "WARN"


def test_check_held_out_nontrivial_fails_when_no_tests(tmp_path):
    (tmp_path / "held_out").mkdir()
    assert vt.check_held_out_nontrivial(tmp_path / "held_out").status == "FAIL"


def test_check_held_out_nontrivial_fails_when_missing_dir(tmp_path):
    assert vt.check_held_out_nontrivial(tmp_path / "nope").status == "FAIL"


def test_check_held_out_nontrivial_passes_with_real_test(tmp_path):
    d = tmp_path / "held_out"
    d.mkdir()
    (d / "test_thing.py").write_text(
        "def test_behaviour():\n    assert add(2, 2) == 4\n"
    )
    assert vt.check_held_out_nontrivial(d).status == "PASS"


def test_check_held_out_nontrivial_fails_when_test_has_no_asserts(tmp_path):
    d = tmp_path / "held_out"
    d.mkdir()
    (d / "test_thing.py").write_text("x = 1\n")
    assert vt.check_held_out_nontrivial(d).status == "FAIL"


def test_check_held_out_nontrivial_passes_with_csharp_xunit(tmp_path):
    d = tmp_path / "held_out"
    d.mkdir()
    (d / "ThingMapperTest.cs").write_text(
        "public class ThingMapperTest {\n"
        "    [Fact]\n"
        "    public void ToDocument_MapsId() { Assert.Equal(1, 1); }\n"
        "}\n"
    )
    assert vt.check_held_out_nontrivial(d).status == "PASS"


def test_check_held_out_nontrivial_fails_csharp_without_asserts(tmp_path):
    d = tmp_path / "held_out"
    d.mkdir()
    (d / "ThingMapperTest.cs").write_text(
        "public class ThingMapperTest {\n"
        "    public void Helper() { var x = 1; }\n"
        "}\n"
    )
    assert vt.check_held_out_nontrivial(d).status == "FAIL"


def test_check_reference_diff_fails_empty():
    assert vt.check_reference_diff("").status == "FAIL"


def test_check_reference_diff_warns_single_file():
    diff = (
        "diff --git a/foo.py b/foo.py\n"
        "--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-old\n+new\n"
    )
    assert vt.check_reference_diff(diff).status == "WARN"


def test_check_reference_diff_passes_multifile():
    diff = (
        "diff --git a/foo.py b/foo.py\n--- a/foo.py\n+++ b/foo.py\n@@ -1 +1 @@\n-a\n+b\n"
        "diff --git a/bar.cpp b/bar.cpp\n--- a/bar.cpp\n+++ b/bar.cpp\n@@ -1 +1 @@\n-c\n+d\n"
    )
    assert vt.check_reference_diff(diff).status == "PASS"


def test_check_instruction_leakage_passes_clean_with_classname():
    # Naming the public deliverable (ReplaceGroup) is the spec, not leakage.
    assert vt.check_instruction_leakage(_complete_task()["instruction"]).status == "PASS"


def test_check_instruction_leakage_flags_diff_marker():
    instr = "Fix it.\ndiff --git a/x.py b/x.py\n@@ -1 +1 @@\n-old\n+new\n"
    assert vt.check_instruction_leakage(instr).status == "FAIL"


def test_check_instruction_leakage_flags_code_fence():
    instr = "Implement the function:\n```python\ndef solve():\n    return 42\n```\n"
    assert vt.check_instruction_leakage(instr).status == "FAIL"


def test_check_difficulty_warns_when_absent():
    assert vt.check_difficulty_present(_complete_task()).status == "WARN"


def test_check_difficulty_passes_when_present():
    task = _complete_task()
    task["difficulty"] = "medium"
    assert vt.check_difficulty_present(task).status == "PASS"


def test_render_lint_summary_ok():
    results = [{
        "task_id": "pyvrp-X",
        "checks": [
            vt.Check("required_fields", "PASS", ""),
            vt.Check("difficulty", "WARN", "no difficulty field"),
        ],
    }]
    text, ok = vt.render_lint_summary(results)
    assert ok is True
    assert "pyvrp-X" in text
    assert "WARN" in text


def test_render_lint_summary_flags_fail():
    results = [{
        "task_id": "pyvrp-Y",
        "checks": [vt.Check("instruction_length", "FAIL", "too short")],
    }]
    text, ok = vt.render_lint_summary(results)
    assert ok is False
    assert "FAIL" in text
    assert "PROBLEM" in text


# --- generalization beyond PyVRP: per-task repo, discovery, build dispatch ---

def test_repo_dir_uses_explicit_repo_field():
    d = vt._repo_dir_for_task({"id": "cosmos-A", "repo": "cosmos"})
    assert d.name == "cosmos"
    assert d.parent.name == "repos"


def test_repo_dir_infers_from_id_prefix_when_no_repo_field():
    d = vt._repo_dir_for_task({"id": "pyvrp-A"})
    assert d.name == "pyvrp"
    assert d.parent.name == "repos"


def test_is_editable_pip_install_true_for_pyvrp():
    assert vt._is_editable_pip_install("pip install -e . 2>&1") is True


def test_is_editable_pip_install_false_for_dotnet():
    assert vt._is_editable_pip_install("dotnet build CleanArchitectureCosmosDB.sln") is False


def test_requires_native_toolchain_true_when_any_editable_pip():
    tasks = [{"build_cmd": "dotnet build x.sln"}, {"build_cmd": "pip install -e ."}]
    assert vt._requires_native_toolchain(tasks) is True


def test_requires_native_toolchain_false_for_dotnet_only():
    tasks = [{"build_cmd": "dotnet build x.sln"}]
    assert vt._requires_native_toolchain(tasks) is False


def test_discover_task_dirs_finds_any_task_yaml(tmp_path):
    (tmp_path / "pyvrp-A").mkdir()
    (tmp_path / "pyvrp-A" / "task.yaml").write_text("id: pyvrp-A\n")
    (tmp_path / "cosmos-A").mkdir()
    (tmp_path / "cosmos-A" / "task.yaml").write_text("id: cosmos-A\n")
    (tmp_path / "not-a-task").mkdir()  # no task.yaml -> ignored
    found = {d.name for d in vt._discover_task_dirs(tmp_path)}
    assert found == {"pyvrp-A", "cosmos-A"}
