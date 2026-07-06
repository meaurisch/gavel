"""grading.judge — prompt construction, verdict parsing, position-swap
merging, diff budgets, agreement math, and the mock provider."""

import json

import pytest

from grading.judge import (
    BlindingError,
    JudgeError,
    PairJudgment,
    VerdictParseError,
    build_prompt,
    cohens_kappa,
    grader_agreement,
    merge_passes,
    parse_verdict,
    run_pair,
    swap_choice,
    truncate_diff,
)
from grading.judge_providers import MockJudgeProvider, ProviderResult


DIFF_A = (
    "diff --git a/src/app.py b/src/app.py\n"
    "--- a/src/app.py\n+++ b/src/app.py\n"
    "@@ -1,0 +1,1 @@\n+left_change = 1\n"
)
DIFF_B = (
    "diff --git a/src/app.py b/src/app.py\n"
    "--- a/src/app.py\n+++ b/src/app.py\n"
    "@@ -1,0 +1,1 @@\n+right_change = 2\n"
)
GATE = {"compile_passed": True, "visible_passed": True, "hidden_passed": True}

VALID_VERDICT = {
    "rubric": {
        "correctness": "A",
        "minimality": "tie",
        "readability": "B",
        "overengineering": "tie",
    },
    "choice": "A",
    "confidence": 0.8,
    "rationale": "Solution A fixes the bug with fewer moving parts.",
}


def _sides():
    left = {"diff": DIFF_A, "gate": GATE}
    right = {"diff": DIFF_B, "gate": GATE}
    return left, right


# ---------------------------------------------------------------------------
# build_prompt
# ---------------------------------------------------------------------------

def test_prompt_contains_task_diffs_rubric_and_schema():
    left, right = _sides()
    prompt = build_prompt("Implement the frobnicator", left, right)
    assert "Implement the frobnicator" in prompt
    assert "left_change = 1" in prompt
    assert "right_change = 2" in prompt
    for dim in ("correctness", "minimality", "readability", "overengineering"):
        assert dim in prompt
    # strict JSON contract
    assert '"choice"' in prompt
    assert '"rationale"' in prompt


def test_prompt_static_preamble_precedes_task_content():
    """The rubric/preamble must lead the prompt so provider-side prompt
    caching can reuse it across pairs; the task instruction is volatile."""
    left, right = _sides()
    p1 = build_prompt("task one instruction", left, right)
    p2 = build_prompt("task two instruction", left, right)
    prefix_len = 200
    assert p1[:prefix_len] == p2[:prefix_len]
    assert p1.index("correctness") < p1.index("task one instruction")


def test_prompt_marks_sides_a_and_b_in_order():
    left, right = _sides()
    prompt = build_prompt("t", left, right)
    assert prompt.index("left_change") < prompt.index("right_change")


def test_prompt_includes_gate_scorecard_but_never_cost_fields():
    left, right = _sides()
    left = dict(left, gate={"compile_passed": True, "visible_passed": False, "hidden_passed": True})
    prompt = build_prompt("t", left, right)
    assert "compile" in prompt.lower()
    for banned in ("usd", "tokens", "wall_seconds", "cost"):
        assert banned not in prompt.lower()


def test_prompt_raises_on_unblinded_token():
    left, right = _sides()
    left = dict(left, diff=DIFF_A + "+methodology superpowers\n")
    with pytest.raises(BlindingError):
        build_prompt("t", left, right, forbidden_tokens=["superpowers"])


def test_prompt_forbidden_tokens_match_whole_tokens_only():
    left, right = _sides()
    # "none" must not trip on Python's None; same boundary rule as redact_axis_ids
    prompt = build_prompt("returns None on error", left, right, forbidden_tokens=["none"])
    assert "None" in prompt


# ---------------------------------------------------------------------------
# parse_verdict
# ---------------------------------------------------------------------------

def test_parse_valid_verdict():
    v = parse_verdict(json.dumps(VALID_VERDICT))
    assert v.choice == "A"
    assert v.confidence == pytest.approx(0.8)
    assert "fewer moving parts" in v.rationale
    assert v.rubric["readability"] == "B"


def test_parse_strips_code_fences_and_prose():
    text = "Here is my verdict:\n```json\n" + json.dumps(VALID_VERDICT) + "\n```\nDone."
    v = parse_verdict(text)
    assert v.choice == "A"


def test_parse_rejects_non_json():
    with pytest.raises(VerdictParseError):
        parse_verdict("I think A is better overall.")


def test_parse_rejects_bad_choice():
    bad = dict(VALID_VERDICT, choice="C")
    with pytest.raises(VerdictParseError) as exc:
        parse_verdict(json.dumps(bad))
    assert "choice" in str(exc.value)


def test_parse_rejects_missing_rationale():
    bad = {k: v for k, v in VALID_VERDICT.items() if k != "rationale"}
    with pytest.raises(VerdictParseError) as exc:
        parse_verdict(json.dumps(bad))
    assert "rationale" in str(exc.value)


def test_parse_clamps_confidence():
    v = parse_verdict(json.dumps(dict(VALID_VERDICT, confidence=7)))
    assert v.confidence == 1.0


def test_parse_tolerates_missing_rubric():
    ok = {k: v for k, v in VALID_VERDICT.items() if k != "rubric"}
    v = parse_verdict(json.dumps(ok))
    assert v.rubric == {}


# ---------------------------------------------------------------------------
# swap / merge
# ---------------------------------------------------------------------------

def test_swap_choice():
    assert swap_choice("A") == "B"
    assert swap_choice("B") == "A"
    assert swap_choice("tie") == "tie"


def test_merge_agreeing_passes():
    first = parse_verdict(json.dumps(VALID_VERDICT))                       # A
    second = parse_verdict(json.dumps(dict(VALID_VERDICT, choice="B")))    # swapped: B means original A
    choice, consistent = merge_passes(first, second)
    assert choice == "A"
    assert consistent is True


def test_merge_disagreeing_passes_is_tie():
    first = parse_verdict(json.dumps(VALID_VERDICT))                       # A
    second = parse_verdict(json.dumps(VALID_VERDICT))                      # swapped A = original B
    choice, consistent = merge_passes(first, second)
    assert choice == "tie"
    assert consistent is False


def test_merge_single_pass():
    first = parse_verdict(json.dumps(VALID_VERDICT))
    choice, consistent = merge_passes(first, None)
    assert choice == "A"
    assert consistent is None


# ---------------------------------------------------------------------------
# diff budget
# ---------------------------------------------------------------------------

def test_truncate_under_budget_is_identity():
    text, truncated = truncate_diff(DIFF_A, max_chars=10_000)
    assert text == DIFF_A
    assert truncated is False


def test_truncate_over_budget_keeps_head_and_marks():
    long_diff = DIFF_A + ("+filler\n" * 5000)
    text, truncated = truncate_diff(long_diff, max_chars=500)
    assert truncated is True
    assert len(text) < len(long_diff)
    assert "truncated" in text
    assert text.startswith("diff --git")


# ---------------------------------------------------------------------------
# run_pair orchestration
# ---------------------------------------------------------------------------

class ScriptedProvider:
    """Returns canned responses in order; records the prompts it saw."""

    id = "scripted"
    label = "Scripted"
    billing = "free"

    def __init__(self, responses):
        self.responses = list(responses)
        self.prompts = []

    def complete(self, prompt: str, model: str) -> ProviderResult:
        self.prompts.append(prompt)
        return ProviderResult(text=self.responses.pop(0), input_tokens=10, output_tokens=5)


def test_run_pair_double_pass_swaps_sides_and_merges():
    left, right = _sides()
    provider = ScriptedProvider([
        json.dumps(VALID_VERDICT),                      # pass 1: A (= left)
        json.dumps(dict(VALID_VERDICT, choice="B")),    # pass 2 swapped: B (= left)
    ])
    result = run_pair(provider, "some-model", "task", left, right, passes=2)
    assert isinstance(result, PairJudgment)
    assert result.choice == "A"
    assert result.position_consistent is True
    assert len(provider.prompts) == 2
    # second pass must present the diffs in swapped order
    p2 = provider.prompts[1]
    assert p2.index("right_change") < p2.index("left_change")
    assert len(result.calls) == 2
    assert all(c.input_tokens == 10 for c in result.calls)


def test_run_pair_single_pass():
    left, right = _sides()
    provider = ScriptedProvider([json.dumps(dict(VALID_VERDICT, choice="tie"))])
    result = run_pair(provider, "m", "task", left, right, passes=1)
    assert result.choice == "tie"
    assert result.position_consistent is None
    assert len(provider.prompts) == 1


def test_run_pair_retries_malformed_reply_with_error_feedback():
    left, right = _sides()
    provider = ScriptedProvider([
        "utter garbage",
        json.dumps(VALID_VERDICT),
        json.dumps(dict(VALID_VERDICT, choice="B")),
    ])
    result = run_pair(provider, "m", "task", left, right, passes=2, max_retries=2)
    assert result.choice == "A"
    # the retry prompt must carry the parse error back to the model
    assert "garbage" in provider.prompts[1] or "invalid" in provider.prompts[1].lower()
    assert len(result.calls) == 3   # failed call is still recorded (it was billed)


def test_run_pair_raises_after_retries_exhausted():
    left, right = _sides()
    provider = ScriptedProvider(["nope", "still nope", "nope again"])
    with pytest.raises(JudgeError):
        run_pair(provider, "m", "task", left, right, passes=1, max_retries=2)


def test_run_pair_enforces_blinding():
    left, right = _sides()
    left = dict(left, diff=DIFF_A + "+superpowers rules\n")
    provider = ScriptedProvider([json.dumps(VALID_VERDICT)])
    with pytest.raises(BlindingError):
        run_pair(provider, "m", "task", left, right, passes=1,
                 forbidden_tokens=["superpowers"])
    assert provider.prompts == []   # nothing may reach the provider


# ---------------------------------------------------------------------------
# mock provider
# ---------------------------------------------------------------------------

def test_mock_provider_returns_parseable_verdict():
    left, right = _sides()
    provider = MockJudgeProvider()
    prompt = build_prompt("task", left, right)
    result = provider.complete(prompt, model="mock-judge")
    v = parse_verdict(result.text)
    assert v.choice in ("A", "B", "tie")


def test_mock_provider_is_position_consistent():
    """The mock judges by content, so a double pass must agree with itself —
    this is what makes the demo/E2E flow show a clean consistency stat."""
    left, right = _sides()
    provider = MockJudgeProvider()
    result = run_pair(provider, "mock-judge", "task", left, right, passes=2)
    assert result.position_consistent is True


def test_mock_provider_availability_is_always_ok():
    ok, reason = MockJudgeProvider().availability()
    assert ok is True


# ---------------------------------------------------------------------------
# agreement math
# ---------------------------------------------------------------------------

def test_cohens_kappa_perfect_agreement():
    assert cohens_kappa(["A", "B", "tie"], ["A", "B", "tie"]) == pytest.approx(1.0)


def test_cohens_kappa_no_agreement_beyond_chance():
    # every label constant for one rater -> chance agreement undefined-ish;
    # use a classic mixed example instead
    a = ["A", "A", "B", "B"]
    b = ["A", "B", "A", "B"]
    assert cohens_kappa(a, b) == pytest.approx(0.0)


def test_cohens_kappa_empty_is_none():
    assert cohens_kappa([], []) is None


def _judgment(left, right, choice, grader):
    return {"left_trial_id": left, "right_trial_id": right, "choice": choice, "grader": grader}


def test_grader_agreement_matches_pairs_including_reversed_orientation():
    human = [
        _judgment("t1", "t2", "A", "human"),
        _judgment("t3", "t4", "tie", "human"),
    ]
    llm = [
        _judgment("t2", "t1", "B", "llm:mock:mock-judge"),   # reversed: B(t1) == human's A(t1)
        _judgment("t3", "t4", "A", "llm:mock:mock-judge"),
    ]
    result = grader_agreement(human, llm)
    assert result["n_shared"] == 2
    assert result["n_agree"] == 1
    assert result["rate"] == pytest.approx(0.5)
    assert "kappa" in result


def test_grader_agreement_no_overlap():
    result = grader_agreement([_judgment("t1", "t2", "A", "human")], [])
    assert result["n_shared"] == 0
    assert result["rate"] is None
