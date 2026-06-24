from grading.analyzer import analyze, AnalyzerFlags
from core.models import Trial, GateResult, CostRecord


def make_trial(tid, *, task="t1", methodology="m1", rep=0):
    return Trial(
        id=tid,
        task_id=task,
        methodology_id=methodology,
        repo_context_id="ctx",
        model="model",
        runner="runner",
        rep=rep,
    )


def gate(tid, passed):
    return GateResult(trial_id=tid, passed=passed)


def cost(tid, usd):
    return CostRecord(
        trial_id=tid,
        native_unit="usd",
        native_amount=usd,
        usd_equiv=usd,
        input_tokens=0,
        output_tokens=0,
        cache_read_tokens=0,
    )


def test_non_discriminating_when_all_values_pass():
    # task t1: m1 and m2 both pass every rep -> task can't discriminate
    trials = [
        make_trial("a", methodology="m1", rep=0),
        make_trial("b", methodology="m1", rep=1),
        make_trial("c", methodology="m2", rep=0),
        make_trial("d", methodology="m2", rep=1),
    ]
    gates = {t.id: gate(t.id, True) for t in trials}
    costs = {t.id: cost(t.id, 1.0) for t in trials}
    flags = analyze(trials, gates, costs, axis="methodology")
    assert "t1" in flags.non_discriminating_tasks
    assert "t1" not in flags.flaky_tasks


def test_non_discriminating_when_all_values_fail():
    trials = [
        make_trial("a", methodology="m1"),
        make_trial("b", methodology="m2"),
    ]
    gates = {t.id: gate(t.id, False) for t in trials}
    costs = {t.id: cost(t.id, 1.0) for t in trials}
    flags = analyze(trials, gates, costs, axis="methodology")
    assert "t1" in flags.non_discriminating_tasks


def test_flaky_when_value_pass_rate_mid_range():
    # m1 passes 1 of 2 reps (0.5) -> flaky; m2 fully passes so task discriminates
    trials = [
        make_trial("a", methodology="m1", rep=0),
        make_trial("b", methodology="m1", rep=1),
        make_trial("c", methodology="m2", rep=0),
        make_trial("d", methodology="m2", rep=1),
    ]
    gates = {
        "a": gate("a", True),
        "b": gate("b", False),
        "c": gate("c", True),
        "d": gate("d", True),
    }
    costs = {t.id: cost(t.id, 1.0) for t in trials}
    flags = analyze(trials, gates, costs, axis="methodology")
    assert "t1" in flags.flaky_tasks
    assert "t1" not in flags.non_discriminating_tasks


def test_cost_quality_note_when_expensive_matches_cheap():
    # m1 cheap, m2 expensive, both pass fully -> expensive not justified
    trials = [
        make_trial("a", methodology="m1"),
        make_trial("b", methodology="m2"),
    ]
    gates = {"a": gate("a", True), "b": gate("b", True)}
    costs = {"a": cost("a", 0.10), "b": cost("b", 5.00)}
    flags = analyze(trials, gates, costs, axis="methodology")
    assert any("m2" in note for note in flags.cost_quality_notes)


def test_no_flags_when_clean_discrimination_and_cost_gap_justified():
    # m1 cheap but fails, m2 expensive and passes -> discriminates, cost justified
    trials = [
        make_trial("a", methodology="m1"),
        make_trial("b", methodology="m2"),
    ]
    gates = {"a": gate("a", False), "b": gate("b", True)}
    costs = {"a": cost("a", 0.10), "b": cost("b", 5.00)}
    flags = analyze(trials, gates, costs, axis="methodology")
    assert flags.non_discriminating_tasks == []
    assert flags.flaky_tasks == []
    assert flags.cost_quality_notes == []


def test_axis_parameter_respected():
    # comparing the model axis instead of methodology
    trials = [
        Trial(id="a", task_id="t1", methodology_id="m", repo_context_id="c",
              model="cheap", runner="r", rep=0),
        Trial(id="b", task_id="t1", methodology_id="m", repo_context_id="c",
              model="pricey", runner="r", rep=0),
    ]
    gates = {"a": gate("a", True), "b": gate("b", True)}
    costs = {"a": cost("a", 0.10), "b": cost("b", 9.0)}
    flags = analyze(trials, gates, costs, axis="model")
    assert "t1" in flags.non_discriminating_tasks
    assert any("pricey" in note for note in flags.cost_quality_notes)
