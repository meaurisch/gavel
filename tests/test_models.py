from pydantic import TypeAdapter

from core.models import (
    CostRecord,
    GateResult,
    LeakageReport,
    RunResult,
    SetupSpec,
    TaskSpec,
    Trial,
)


def test_task_spec_roundtrip():
    obj = TaskSpec(
        id="cosmos-001",
        repo_url="https://github.com/example/cosmos",
        base_commit="abc123",
        instruction="Fix the broken import in main.py",
        run_cmd="pytest tests/",
        held_out_tests_path="tests/test_hidden.py",
        reference_diff_path="diffs/cosmos-001.patch",
    )
    ta = TypeAdapter(TaskSpec)
    data = ta.dump_python(obj)
    restored = ta.validate_python(data)
    assert restored == obj


def test_setup_spec_roundtrip():
    obj = SetupSpec(
        id="vanilla",
        files={"pyproject.toml": ["[tool.pytest.ini_options]", "minversion = '8'"]},
    )
    ta = TypeAdapter(SetupSpec)
    data = ta.dump_python(obj)
    restored = ta.validate_python(data)
    assert restored == obj


def test_trial_roundtrip():
    obj = Trial(
        id="cosmos-001_vanilla_claude-3-5-sonnet_claude-code_0",
        task_id="cosmos-001",
        setup_id="vanilla",
        model="claude-3-5-sonnet",
        runner="claude-code",
        rep=0,
    )
    ta = TypeAdapter(Trial)
    data = ta.dump_python(obj)
    restored = ta.validate_python(data)
    assert restored == obj


def test_run_result_roundtrip():
    obj = RunResult(
        trial_id="cosmos-001_vanilla_claude-3-5-sonnet_claude-code_0",
        diff="--- a/main.py\n+++ b/main.py\n@@ -1 +1 @@\n-import foo\n+import bar",
        exit_status=0,
        wall_seconds=42.5,
    )
    ta = TypeAdapter(RunResult)
    data = ta.dump_python(obj)
    restored = ta.validate_python(data)
    assert restored == obj


def test_cost_record_roundtrip():
    obj = CostRecord(
        trial_id="cosmos-001_vanilla_claude-3-5-sonnet_claude-code_0",
        native_unit="tokens",
        native_amount=15000.0,
        usd_equiv=0.045,
        input_tokens=10000,
        output_tokens=5000,
        cache_read_tokens=2000,
    )
    ta = TypeAdapter(CostRecord)
    data = ta.dump_python(obj)
    restored = ta.validate_python(data)
    assert restored == obj


def test_gate_result_roundtrip():
    obj = GateResult(
        trial_id="cosmos-001_vanilla_claude-3-5-sonnet_claude-code_0",
        passed=True,
        test_output="All 12 tests passed.",
    )
    ta = TypeAdapter(GateResult)
    data = ta.dump_python(obj)
    restored = ta.validate_python(data)
    assert restored == obj


def test_leakage_report_roundtrip():
    obj = LeakageReport(
        hits=["src/main.py:42", "comment src/util.py:10", "git-log:7"],
        any_found=True,
    )
    ta = TypeAdapter(LeakageReport)
    data = ta.dump_python(obj)
    restored = ta.validate_python(data)
    assert restored == obj
