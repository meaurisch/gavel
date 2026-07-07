"""LLM-as-judge orchestration for one blind pair.

The judge consumes EXACTLY the payload a blind human grader sees — anonymized
diffs and the gate scorecard booleans; never cost/tokens/wall-time, never raw
axis ids (``build_prompt`` enforces that with ``forbidden_tokens``). Verdicts
come back as strict JSON (reasoning first, then the choice), parsed with a
self-correction retry loop. Position bias — the dominant pairwise-judge
failure mode — is mitigated by judging each pair twice with the sides
swapped; the two passes must agree or the pair is recorded as a tie with
``position_consistent = False``.
"""

from __future__ import annotations

import json
import math
import re
from dataclasses import dataclass, field

from grading.judge_providers import JudgeProviderError, ProviderResult

RUBRIC_DIMENSIONS = ("correctness", "minimality", "readability", "overengineering")

VALID_CHOICES = ("A", "B", "tie")

# Static preamble: rubric + output contract. It leads the prompt (before any
# per-pair content) so provider-side prompt caching can reuse it across every
# pair of a session.
_PREAMBLE = """You are an expert code reviewer judging a blind A/B contest \
between two candidate solutions to the same programming task. Both solutions \
already passed an automated test gate; your job is the qualitative call.

Compare them on four dimensions:
- correctness: does the change fully and robustly solve the task? Edge cases?
- minimality: is the change scoped to the task, without unrelated churn?
- readability: naming, structure, clarity; does it read like the surrounding code?
- overengineering: penalize needless abstractions, speculative generality, dead code.

Rules:
- Judge ONLY from the material below. Identifying markers were redacted \
(shown as [methodology], [model], etc.) — never guess what they hide, and do \
not reward or punish a solution for redaction artifacts.
- Diff size alone is not quality: prefer the change a maintainer would rather merge.
- "tie" is a real answer when the two are genuinely comparable.

Reply with ONLY a JSON object (no markdown fence, no prose around it):
{
  "rubric": {"correctness": "A|B|tie", "minimality": "A|B|tie", "readability": "A|B|tie", "overengineering": "A|B|tie"},
  "rationale": "<2-5 sentences: the decisive differences, dimension by dimension>",
  "confidence": <0.0-1.0>,
  "choice": "A" | "B" | "tie"
}
"""

# Side markers double as the parsing contract for the mock provider.
_SIDE_TEMPLATE = """=== SOLUTION {label} DIFF ===
{diff}
=== END SOLUTION {label} ===
"""


class JudgeError(Exception):
    """Judging a pair failed permanently (after retries). ``calls`` carries
    every provider call made before the failure — they were billed even
    though the pair produced no verdict, so the caller must still write
    them to the usage audit."""

    def __init__(self, message: str, calls: list["JudgeCall"] | None = None):
        super().__init__(message)
        self.calls: list[JudgeCall] = calls or []


class VerdictParseError(Exception):
    """The model's reply was not a valid verdict; message is human-readable
    and is fed back to the model on retry."""


class BlindingError(Exception):
    """A forbidden (axis-identifying) token survived into the prompt.
    Nothing is sent to any provider when this fires."""


@dataclass
class JudgeVerdict:
    choice: str
    rationale: str
    confidence: float
    rubric: dict[str, str] = field(default_factory=dict)


@dataclass
class JudgeCall:
    """One provider call, kept for the usage/cost audit trail — including
    failed calls, because they were billed too."""
    ordering: str            # "AB" or "BA"
    status: str              # "ok" | "parse_error" | "provider_error"
    input_tokens: int = 0
    output_tokens: int = 0
    usd_equiv: float | None = None
    wall_seconds: float = 0.0
    error: str | None = None


@dataclass
class PairJudgment:
    choice: str
    rationale: str
    confidence: float
    position_consistent: bool | None   # None on single-pass runs
    verdicts: list[JudgeVerdict]
    calls: list[JudgeCall]
    truncated: bool = False


# ---------------------------------------------------------------------------
# prompt
# ---------------------------------------------------------------------------

def _gate_line(gate: dict | None) -> str:
    if not gate:
        return "gate scorecard: unknown"
    def word(v):
        return "pass" if v else ("fail" if v is not None else "n/a")
    return (
        f"gate scorecard: compile={word(gate.get('compile_passed'))}, "
        f"visible tests={word(gate.get('visible_passed'))}, "
        f"hidden tests={word(gate.get('hidden_passed'))}"
    )


def _check_blinding(text: str, forbidden_tokens) -> None:
    for tok in forbidden_tokens or ():
        # Same matching rules as grading.pairwise.redact_axis_ids (whole
        # token, letters/digits boundary alphabet, case-INSENSITIVE): a case
        # variant of an axis id is still that id. Anything legitimate has
        # been redacted upstream before this net is cast, so a hit here is a
        # redaction bug — fail closed.
        pattern = re.compile(
            rf"(?<![A-Za-z0-9]){re.escape(tok)}(?![A-Za-z0-9])", re.IGNORECASE)
        if pattern.search(text):
            # Deliberately does NOT name the token: this error is rendered on
            # the blind progress page / SSE stream, which must stay blind.
            raise BlindingError(
                "an axis-identifying token would reach the judge — refusing "
                "to build the prompt (blind-grading invariant)"
            )


def build_prompt(
    task_instruction: str,
    left: dict,
    right: dict,
    *,
    forbidden_tokens: list[str] | None = None,
) -> str:
    """Assemble the judge prompt for one ordering. ``left``/``right`` are
    ``{"diff": <anonymized diff>, "gate": {tier: bool|None}}`` — the same
    payload a blind human sees. Raises BlindingError if any forbidden token
    (a raw axis id) appears anywhere in the assembled prompt."""
    parts = [
        _PREAMBLE,
        "\n--- TASK GIVEN TO BOTH SOLUTIONS ---\n",
        task_instruction.strip(),
        "\n\n--- SOLUTION A ---\n",
        _gate_line(left.get("gate")),
        "\n",
        _SIDE_TEMPLATE.format(label="A", diff=left["diff"].rstrip("\n")),
        "\n--- SOLUTION B ---\n",
        _gate_line(right.get("gate")),
        "\n",
        _SIDE_TEMPLATE.format(label="B", diff=right["diff"].rstrip("\n")),
        "\nNow give your verdict as the single JSON object described above.",
    ]
    prompt = "".join(parts)
    _check_blinding(prompt, forbidden_tokens)
    return prompt


# ---------------------------------------------------------------------------
# verdict parsing (self-correction retry loop feeds errors back)
# ---------------------------------------------------------------------------

_FENCE_RE = re.compile(r"^```(?:json)?\s*|\s*```$", re.MULTILINE)


def parse_verdict(text: str) -> JudgeVerdict:
    cleaned = _FENCE_RE.sub("", (text or "").strip()).strip()
    # Models sometimes wrap the object in prose (before AND after); take the
    # outermost {...} so a valid verdict with trailing chatter doesn't burn a
    # retry call.
    start, end = cleaned.find("{"), cleaned.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise VerdictParseError("reply contains no JSON object")
    cleaned = cleaned[start:end + 1]
    try:
        data = json.loads(cleaned)
    except json.JSONDecodeError as exc:
        raise VerdictParseError(f"reply is not valid JSON: {exc}") from exc
    if not isinstance(data, dict):
        raise VerdictParseError("top-level JSON value must be an object")

    choice = data.get("choice")
    if choice not in VALID_CHOICES:
        raise VerdictParseError(
            f'"choice" must be one of "A", "B", "tie" — got {choice!r}'
        )
    rationale = data.get("rationale")
    if not isinstance(rationale, str) or not rationale.strip():
        raise VerdictParseError('"rationale" must be a non-empty string')

    # An explicit null is the same signal as an absent key — don't burn a
    # billed retry call over it.
    raw_conf = data.get("confidence")
    if raw_conf is None:
        raw_conf = 0.5
    try:
        confidence = float(raw_conf)
    except (TypeError, ValueError):
        raise VerdictParseError(f'"confidence" must be a number — got {raw_conf!r}')
    if not math.isfinite(confidence):
        # NaN would sail through a min/max clamp as 1.0 — an unparseable
        # confidence recorded as full certainty. Reject; the retry loop
        # asks for a real number.
        raise VerdictParseError(f'"confidence" must be a finite number — got {raw_conf!r}')
    confidence = max(0.0, min(1.0, confidence))

    # The rubric is optional enrichment: a malformed one (list, string, ...)
    # degrades exactly like a missing one instead of crashing the run.
    rubric_raw = data.get("rubric")
    if not isinstance(rubric_raw, dict):
        rubric_raw = {}
    rubric = {
        dim: rubric_raw[dim]
        for dim in RUBRIC_DIMENSIONS
        if rubric_raw.get(dim) in VALID_CHOICES
    }
    return JudgeVerdict(choice=choice, rationale=rationale.strip(),
                        confidence=confidence, rubric=rubric)


# ---------------------------------------------------------------------------
# position-swap merge
# ---------------------------------------------------------------------------

def swap_choice(choice: str) -> str:
    return {"A": "B", "B": "A"}.get(choice, choice)


def merge_passes(first: JudgeVerdict, second: JudgeVerdict | None) -> tuple[str, bool | None]:
    """Combine the A/B pass with the swapped B/A pass. The second verdict is
    in SWAPPED coordinates (its "A" is the original right side); normalize,
    then: agreement -> that choice, disagreement -> tie (the honest reading
    of a position-dependent verdict)."""
    if second is None:
        return first.choice, None
    second_normalized = swap_choice(second.choice)
    if first.choice == second_normalized:
        return first.choice, True
    return "tie", False


# ---------------------------------------------------------------------------
# diff budget
# ---------------------------------------------------------------------------

def truncate_diff(diff: str, max_chars: int) -> tuple[str, bool]:
    """Cap a diff's contribution to the prompt. Head is kept (file headers
    and the first hunks carry the most signal); the cut is marked so the
    judge knows it saw a prefix."""
    if len(diff) <= max_chars:
        return diff, False
    head = diff[:max_chars]
    # cut on a line boundary so we don't split a hunk line mid-escape
    nl = head.rfind("\n")
    if nl > 0:
        head = head[:nl]
    omitted = len(diff) - len(head)
    return head + f"\n[... diff truncated for the judge: {omitted} chars omitted ...]", True


# ---------------------------------------------------------------------------
# one pair, end to end
# ---------------------------------------------------------------------------

_RETRY_TEMPLATE = """{prompt}

--- CORRECTION REQUIRED ---
Your previous reply was invalid: {error}
Previous reply (do not repeat this mistake):
{raw}

Reply again with ONLY the JSON object in the exact format specified above.
"""


def _call_with_retries(provider, model: str, prompt: str, ordering: str,
                       max_retries: int, calls: list[JudgeCall]) -> JudgeVerdict:
    attempt_prompt = prompt
    last_error: Exception | None = None
    for _attempt in range(max_retries + 1):
        try:
            result: ProviderResult = provider.complete(attempt_prompt, model)
        except JudgeProviderError as exc:
            calls.append(JudgeCall(ordering=ordering, status="provider_error", error=str(exc)))
            raise JudgeError(f"judge provider failed: {exc}") from exc
        try:
            verdict = parse_verdict(result.text)
            calls.append(JudgeCall(
                ordering=ordering, status="ok",
                input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                usd_equiv=result.usd_equiv, wall_seconds=result.wall_seconds,
            ))
            return verdict
        except VerdictParseError as exc:
            calls.append(JudgeCall(
                ordering=ordering, status="parse_error",
                input_tokens=result.input_tokens, output_tokens=result.output_tokens,
                usd_equiv=result.usd_equiv, wall_seconds=result.wall_seconds,
                error=str(exc),
            ))
            last_error = exc
            attempt_prompt = _RETRY_TEMPLATE.format(
                prompt=prompt, error=exc, raw=(result.text or "")[:2000]
            )
    raise JudgeError(
        f"judge reply stayed unparseable after {max_retries + 1} attempts: {last_error}"
    )


def run_pair(
    provider,
    model: str,
    task_instruction: str,
    left: dict,
    right: dict,
    *,
    passes: int = 2,
    max_retries: int = 2,
    diff_char_budget: int = 60_000,
    forbidden_tokens: list[str] | None = None,
) -> PairJudgment:
    """Judge one blind pair: build prompt(s), call the provider, parse with
    retries, merge the position-swapped passes. ``passes`` is 1 (cheap) or 2
    (position-debiased, default)."""
    if passes not in (1, 2):
        raise ValueError("passes must be 1 or 2")

    l_diff, l_trunc = truncate_diff(left["diff"], diff_char_budget)
    r_diff, r_trunc = truncate_diff(right["diff"], diff_char_budget)
    left = dict(left, diff=l_diff)
    right = dict(right, diff=r_diff)

    # Build BOTH prompts before any provider call: a blinding failure must
    # abort the pair before a single token is spent.
    prompt_ab = build_prompt(task_instruction, left, right,
                             forbidden_tokens=forbidden_tokens)
    prompt_ba = None
    if passes == 2:
        prompt_ba = build_prompt(task_instruction, right, left,
                                 forbidden_tokens=forbidden_tokens)

    calls: list[JudgeCall] = []
    try:
        first = _call_with_retries(provider, model, prompt_ab, "AB", max_retries, calls)
        second = None
        if prompt_ba is not None:
            second = _call_with_retries(provider, model, prompt_ba, "BA", max_retries, calls)
    except JudgeError as exc:
        # The pair failed, but its attempts were still billed — hand the
        # call records to the caller so the usage audit stays honest.
        exc.calls = calls
        raise

    choice, consistent = merge_passes(first, second)

    if second is None:
        rationale = first.rationale
        confidence = first.confidence
    elif consistent:
        rationale = first.rationale
        confidence = (first.confidence + second.confidence) / 2
    else:
        rationale = (
            "Position-swapped passes disagreed "
            f"(A/B pass said {first.choice!r}, swapped pass said "
            f"{swap_choice(second.choice)!r} in original coordinates) — "
            "recorded as a tie. First pass reasoning: " + first.rationale
        )
        confidence = 0.0

    return PairJudgment(
        choice=choice,
        rationale=rationale,
        confidence=confidence,
        position_consistent=consistent,
        verdicts=[v for v in (first, second) if v is not None],
        calls=calls,
        truncated=l_trunc or r_trunc,
    )


# ---------------------------------------------------------------------------
# agreement analytics (human <-> LLM)
# ---------------------------------------------------------------------------

def cohens_kappa(labels_a: list[str], labels_b: list[str]) -> float | None:
    """Cohen's kappa over two aligned label lists. None when empty; 1.0 when
    the raters agree everywhere (even if chance agreement is 1 too)."""
    if not labels_a or len(labels_a) != len(labels_b):
        return None
    n = len(labels_a)
    observed = sum(1 for a, b in zip(labels_a, labels_b) if a == b) / n
    categories = set(labels_a) | set(labels_b)
    chance = sum(
        (labels_a.count(c) / n) * (labels_b.count(c) / n) for c in categories
    )
    if chance >= 1.0:
        return 1.0 if observed == 1.0 else 0.0
    return (observed - chance) / (1.0 - chance)


def _normalize(judgment: dict) -> tuple[tuple[str, str], str]:
    """Key a judgment by its unordered trial pair and express the choice in
    canonical orientation (winner relative to the lexicographically smaller
    trial id) so reversed presentations still compare."""
    left, right = judgment["left_trial_id"], judgment["right_trial_id"]
    choice = judgment["choice"]
    if left <= right:
        return (left, right), choice
    return (right, left), swap_choice(choice)


def grader_agreement(human_judgments: list[dict], llm_judgments: list[dict]) -> dict:
    """Per-pair agreement between human and LLM verdicts over the trial pairs
    both graded. Judgments are dicts with left_trial_id/right_trial_id/choice
    (orientation may differ between graders — normalized here)."""
    human_by_pair: dict[tuple[str, str], str] = {}
    for j in human_judgments:
        key, choice = _normalize(j)
        human_by_pair[key] = choice
    llm_by_pair: dict[tuple[str, str], str] = {}
    for j in llm_judgments:
        key, choice = _normalize(j)
        llm_by_pair[key] = choice

    shared = sorted(set(human_by_pair) & set(llm_by_pair))
    if not shared:
        return {"n_shared": 0, "n_agree": 0, "rate": None, "kappa": None}

    human_labels = [human_by_pair[k] for k in shared]
    llm_labels = [llm_by_pair[k] for k in shared]
    n_agree = sum(1 for a, b in zip(human_labels, llm_labels) if a == b)
    return {
        "n_shared": len(shared),
        "n_agree": n_agree,
        "rate": n_agree / len(shared),
        "kappa": cohens_kappa(human_labels, llm_labels),
    }
