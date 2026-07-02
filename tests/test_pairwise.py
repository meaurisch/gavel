from grading.pairwise import generate_pairs, anonymize_diff, AXIS_TOKENS
from core.models import Trial, RunResult


def make_trial(**overrides) -> Trial:
    defaults = dict(
        id="trial-default",
        task_id="taskone",
        methodology_id="methoda",
        repo_context_id="ctxa",
        model="modelone",
        runner="runnera",
        rep=0,
    )
    defaults.update(overrides)
    return Trial(**defaults)


def _make_diff(*added_lines: str) -> str:
    """Build a minimal valid unified diff touching src/app.py."""
    body = "\n".join(f"+{line}" for line in added_lines)
    return (
        "diff --git a/src/app.py b/src/app.py\n"
        "--- a/src/app.py\n"
        "+++ b/src/app.py\n"
        "@@ -1,0 +1,{n} @@\n"
        "{body}\n"
    ).format(n=len(added_lines), body=body)


def test_anonymize_redacts_every_axis_id():
    diff = _make_diff(
        "methodology = superpowers",
        "context = pyvrp-instructions",
        "model = claude-opus-4-8",
        "runner = claude-code",
    )
    result = anonymize_diff(diff, {
        "methodology": ["superpowers"],
        "repo_context": ["pyvrp-instructions"],
        "model": ["claude-opus-4-8"],
        "runner": ["claude-code"],
    })
    for raw_id in ("superpowers", "pyvrp-instructions", "claude-opus-4-8", "claude-code"):
        assert raw_id not in result, f"{raw_id!r} was not redacted"
    for token in AXIS_TOKENS.values():
        assert token in result, f"{token!r} missing from redacted diff"


def test_anonymize_longest_first_substring():
    diff = _make_diff(
        "using gpt-5-codex for generation",
    )
    result = anonymize_diff(diff, {
        "model": ["gpt-5", "gpt-5-codex"],
    })
    assert "codex" not in result, "substring fragment 'codex' leaked"
    assert "[model]" in result


def test_anonymize_sorts_ids_globally_across_axes():
    diff = _make_diff(
        "runner = agent-v2-experimental",
    )
    result = anonymize_diff(diff, {
        "methodology": ["v2"],
        "model": [],
        "repo_context": [],
        "runner": ["agent-v2-experimental"],
    })
    assert "[runner]" in result
    assert "agent-" not in result, "leaked fragment 'agent-'"
    assert "experimental" not in result, "leaked fragment 'experimental'"
    assert "agent-v2-experimental" not in result


def test_anonymize_matches_whole_tokens_only():
    # The id "cosmos" must not mangle identifiers that merely contain it.
    diff = _make_diff(
        "namespace CleanArchitectureCosmosDB.Infrastructure.CosmosDbData",
        "// talks to Azure cosmos here",
    )
    result = anonymize_diff(diff, {"repo_context": ["cosmos"]})
    assert "CleanArchitectureCosmosDB" in result
    assert "CosmosDbData" in result
    assert "Azure [context] here" in result


def test_anonymize_snake_case_glued_ids_still_redact():
    # Underscore gluing is exactly how an agent leaks an axis id into
    # identifiers — `cosmos_client`, `tdd_utils.py` must still redact.
    diff = _make_diff(
        "cosmos_client = CosmosClient()",
        "import tdd_utils",
    )
    result = anonymize_diff(diff, {"repo_context": ["cosmos"], "methodology": ["tdd"]})
    assert "cosmos" not in result.lower().replace("cosmosclient", "")
    assert "[context]_client" in result
    assert "[methodology]_utils" in result
    # ...while letter-adjacent occurrences stay protected:
    assert "CosmosClient" in result


def test_anonymize_without_skip_ids_still_redacts_none():
    diff = _make_diff("value = None")
    result = anonymize_diff(diff, {"repo_context": ["none"]})
    assert "None" not in result
    assert "[context]" in result


def test_generate_pairs_groups_by_axis_model():
    trials = [
        make_trial(id="t-m1", model="m1"),
        make_trial(id="t-m2", model="m2"),
        make_trial(id="t-m3", model="m3"),
    ]
    pairs = generate_pairs(trials, {}, "model", seed=0)
    assert len(pairs) == 3  # C(3,2)
    for left, right in pairs:
        assert left.model != right.model
    all_models = set()
    for left, right in pairs:
        all_models.add(left.model)
        all_models.add(right.model)
    assert all_models == {"m1", "m2", "m3"}


def test_generate_pairs_only_compares_across_axis_values():
    trials = [
        make_trial(id="t-c1-r0", repo_context_id="c1", rep=0),
        make_trial(id="t-c1-r1", repo_context_id="c1", rep=1),
        make_trial(id="t-c2-r0", repo_context_id="c2", rep=0),
    ]
    pairs = generate_pairs(trials, {}, "repo_context", seed=0)
    # M=2 values, candidate pool = (c1r0,c2r0),(c1r1,c2r0) -> 2 unique pairs
    assert len(pairs) == 2
    for left, right in pairs:
        assert left.repo_context_id != right.repo_context_id
    # both reps of c1 are now used, not just rep 0
    c1_reps = {t.rep for pair in pairs for t in pair if t.repo_context_id == "c1"}
    assert c1_reps == {0, 1}


def test_generate_pairs_uses_multiple_reps_balanced():
    trials = [
        make_trial(id=f"t-{v}-r{r}", model=v, rep=r)
        for v in ("m1", "m2", "m3")
        for r in (0, 1, 2)
    ]
    pairs = generate_pairs(trials, {}, "model", seed=0)
    # default num_pairs = C(3,2) * 3 = 9
    assert len(pairs) == 9
    # no duplicate trial-pairs (order-insensitive)
    seen = {frozenset((l.id, r.id)) for l, r in pairs}
    assert len(seen) == 9
    # every pair crosses axis values
    for left, right in pairs:
        assert left.model != right.model
    # more than just rep 0 is sampled
    reps_used = {t.rep for pair in pairs for t in pair}
    assert len(reps_used) > 1


def test_generate_pairs_respects_num_pairs():
    trials = [
        make_trial(id=f"t-{v}-r{r}", model=v, rep=r)
        for v in ("m1", "m2", "m3")
        for r in (0, 1, 2)
    ]
    pairs = generate_pairs(trials, {}, "model", num_pairs=4, seed=0)
    assert len(pairs) == 4


def test_generate_pairs_caps_at_pool_size():
    # 2 values x 1 rep -> pool of 1 unique pair, even if num_pairs asks for more
    trials = [
        make_trial(id="t-m1", model="m1"),
        make_trial(id="t-m2", model="m2"),
    ]
    pairs = generate_pairs(trials, {}, "model", num_pairs=10, seed=0)
    assert len(pairs) == 1
