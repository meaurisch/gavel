"""Pairwise comparison — blind grading of trial diffs."""

import itertools
import logging
import random
import re

from pydantic import BaseModel

from core.models import Trial, RunResult

logger = logging.getLogger(__name__)

AXIS_FIELDS = {
    "methodology": "methodology_id",
    "model": "model",
    "repo_context": "repo_context_id",
    "runner": "runner",
}
AXIS_TOKENS = {
    "methodology": "[methodology]",
    "repo_context": "[context]",
    "model": "[model]",
    "runner": "[runner]",
}

METHODOLOGY_FILE_PATTERNS = {
    "CLAUDE.md",
    ".github/copilot-instructions.md",
    "AGENTS.md",
}

METHODOLOGY_DIR_PREFIXES = (
    ".claude/skills/",
    ".claude/agents/",
    ".claude/rules/",
    ".github/agents/",
    # Planning/progress artifacts an agent COMMITS while working. Not laid
    # down by a pack, so the leakage scanner never saw them — but their mere
    # presence in a served diff names the methodology. Stripped at serve time
    # so recorded and future runs are both covered (2026-08-02).
    ".agent-plans/",
)

DEP_FILES = {"requirements.txt", "pyproject.toml", "package.json"}
DEP_EXTENSIONS = {".csproj"}


class DiffProxy(BaseModel):
    lines_added: int
    lines_removed: int
    files_touched: int
    file_list: list[str]
    new_deps: list[str]


def generate_pairs(
    trials: list[Trial],
    run_results: dict[str, RunResult],
    axis: str = "methodology",
    num_pairs: int | None = None,
    seed: int | None = None,
) -> list[tuple[Trial, Trial]]:
    """Sample balanced cross-value pairs from a cell.

    Callers pass exactly one cell's passing trials — all other axes already fixed —
    so the only thing varying is the comparison axis. Unlike a rep-0-only scheme,
    this draws from every rep: the candidate pool is all unique cross-value trial
    pairs, and sampling prefers under-used trials so the reps stay balanced.

    M = distinct axis values, R reps each => pool of ~C(M,2) * R * R pairs.
    ``num_pairs`` defaults to C(M,2) * 3.
    """
    field = AXIS_FIELDS[axis]
    by_axis_value: dict[str, list[Trial]] = {}
    for t in trials:
        by_axis_value.setdefault(getattr(t, field), []).append(t)

    # Candidate pool: every unique pair of trials from two different axis values.
    groups = list(by_axis_value.values())
    candidates: list[tuple[Trial, Trial]] = []
    for ga, gb in itertools.combinations(groups, 2):
        for a in ga:
            for b in gb:
                candidates.append((a, b))

    m = len(by_axis_value)
    if num_pairs is None:
        num_pairs = (m * (m - 1) // 2) * 3
    num_pairs = min(num_pairs, len(candidates))

    rng = random.Random(seed)
    rng.shuffle(candidates)

    # Greedy balanced selection: repeatedly take the candidate whose two trials
    # have the lowest combined usage so far, so reps get spread evenly.
    use_count: dict[str, int] = {}
    selected: list[tuple[Trial, Trial]] = []
    remaining = candidates[:]
    while remaining and len(selected) < num_pairs:
        best_i = min(
            range(len(remaining)),
            key=lambda i: (
                max(use_count.get(remaining[i][0].id, 0), use_count.get(remaining[i][1].id, 0)),
                use_count.get(remaining[i][0].id, 0) + use_count.get(remaining[i][1].id, 0),
            ),
        )
        a, b = remaining.pop(best_i)
        use_count[a.id] = use_count.get(a.id, 0) + 1
        use_count[b.id] = use_count.get(b.id, 0) + 1
        # Randomly assign left/right.
        selected.append((a, b) if rng.random() < 0.5 else (b, a))

    return selected


def insert_probes(
    pairs: list[tuple],
    k: int | None = None,
    seed: int | None = None,
) -> tuple[list[tuple], dict[int, int]]:
    """E2.1 consistency probes: duplicate ``k`` randomly-chosen pairs with
    their sides SWAPPED and reinsert each at a random position after its
    original. A probe is indistinguishable from a real pair on every blind
    surface; only the session record (``probe_of``) knows. Judged probes
    yield the instrument's self-agreement and side-swap flip rate and are
    excluded from Bradley-Terry.

    Default ``k`` ≈ 10% of pairs, min 2, capped at one probe per pair.
    Returns (pairs_with_probes, {probe_index: original_index}).
    """
    n = len(pairs)
    if n == 0:
        return list(pairs), {}
    if k is None:
        k = max(2, round(0.1 * n))
    k = min(k, n)

    rng = random.Random(seed)
    chosen = rng.sample(range(n), k)

    # Work on (kind, original_index) tags so positions can shift freely as
    # probes are inserted; resolve final indices at the end.
    items: list[tuple[str, int]] = [("orig", i) for i in range(n)]
    for oi in chosen:
        pos = items.index(("orig", oi))
        items.insert(rng.randint(pos + 1, len(items)), ("probe", oi))

    out: list[tuple] = []
    orig_at: dict[int, int] = {}
    for idx, (kind, oi) in enumerate(items):
        if kind == "orig":
            orig_at[oi] = idx
            out.append(pairs[oi])
        else:
            left, right = pairs[oi]
            out.append((right, left))
    probe_of = {
        idx: orig_at[oi]
        for idx, (kind, oi) in enumerate(items)
        if kind == "probe"
    }
    return out, probe_of


class ProbeStats(BaseModel):
    """The instrument numbers a session's probes yield. ``n_evaluated``
    counts probes where BOTH the probe and its original were judged;
    agreement compares content choices across the side swap (original A ≙
    probe B). A flip is a pair of non-tie verdicts that named opposite
    contents — the judge followed the side, not the diff."""
    n_probes: int
    n_evaluated: int
    n_agree: int
    n_flips: int
    self_agreement: float | None
    flip_rate: float | None


_PROBE_SWAP = {"A": "B", "B": "A", "tie": "tie"}


def compute_probe_stats(probe_of: dict[int, int], choices: dict[int, str]) -> ProbeStats:
    """``choices`` maps pair_index -> A|B|tie for every judged pair."""
    n_evaluated = n_agree = n_flips = 0
    for probe_idx, orig_idx in probe_of.items():
        orig, probe = choices.get(orig_idx), choices.get(probe_idx)
        if orig is None or probe is None:
            continue
        n_evaluated += 1
        if _PROBE_SWAP.get(probe) == orig:
            n_agree += 1
        elif orig != "tie" and probe != "tie":
            n_flips += 1
    return ProbeStats(
        n_probes=len(probe_of),
        n_evaluated=n_evaluated,
        n_agree=n_agree,
        n_flips=n_flips,
        self_agreement=(n_agree / n_evaluated) if n_evaluated else None,
        flip_rate=(n_flips / n_evaluated) if n_evaluated else None,
    )


def _is_instruction_file(path: str) -> bool:
    if path in METHODOLOGY_FILE_PATTERNS:
        return True
    for prefix in METHODOLOGY_DIR_PREFIXES:
        if path.startswith(prefix):
            return True
    return False


def _split_file_hunks(diff: str) -> list[tuple[str, str]]:
    """Split a unified diff into (file_path, hunk_text) pairs."""
    marker = "diff --git "
    parts = diff.split(marker)
    result: list[tuple[str, str]] = []

    for part in parts[1:]:
        first_line = part.split("\n", 1)[0]
        # "diff --git a/path b/path" => extract b/path
        tokens = first_line.split(" ")
        file_path = tokens[-1]
        if file_path.startswith("b/"):
            file_path = file_path[2:]

        full_text = marker + part
        result.append((file_path, full_text))

    return result


# Per-trial worktree temp paths (sb-wt-<hex>, see core.worktree) are opaque
# but joinable against unblinded surfaces (Browse/trial detail) that show the
# same hash next to the axis value. Scrubbed from EVERY blind surface here —
# diffs, gate logs, reconstructed originals — so a future agent that bakes
# its absolute worktree path into committed content can't reopen the channel.
_WORKTREE_RE = re.compile(r"sb-wt-[0-9a-f]+", re.IGNORECASE)


def redact_axis_ids(text: str, axis_ids_by_axis: dict[str, list[str]]) -> str:
    """Redact every given axis id from arbitrary text (diffs, gate logs,
    reconstructed file content — anything served during blind comparison).

    Ids match as whole tokens (case-insensitive) with letters/digits as the
    boundary alphabet: the repo-context id ``cosmos`` must not mangle a
    ``CosmosDbData`` namespace, but ``cosmos_client`` / ``tdd_utils.py``
    (underscore-glued) MUST still redact — snake_case gluing is exactly how an
    agent leaks an axis id into identifiers. Callers decide which ids to
    redact; causally-inert ids (specs that lay down zero files) should be
    filtered out before calling (see ui.server._inert_axis_ids).

    This is THE redaction implementation for the blind-grading invariant —
    every UI surface must go through it, not reimplement it.
    """
    sid_tokens: list[tuple[str, str]] = []
    for axis, ids in axis_ids_by_axis.items():
        token = AXIS_TOKENS[axis]
        for sid in ids:
            sid_tokens.append((sid, token))

    for sid, token in sorted(sid_tokens, key=lambda pair: len(pair[0]), reverse=True):
        pattern = re.compile(rf"(?<![A-Za-z0-9]){re.escape(sid)}(?![A-Za-z0-9])", re.IGNORECASE)
        text = pattern.sub(token, text)

    return _WORKTREE_RE.sub("sb-wt-[redacted]", text)


def anonymize_diff(diff: str, axis_ids_by_axis: dict[str, list[str]]) -> str:
    """Strip instruction files and redact every given axis id from a diff
    (see redact_axis_ids for the redaction rules)."""
    hunks = _split_file_hunks(diff)

    # Preserve any text before the first "diff --git" (unlikely but safe)
    prefix = diff.split("diff --git")[0] if "diff --git" in diff else diff

    kept_parts: list[str] = [prefix] if prefix else []
    for file_path, hunk_text in hunks:
        if _is_instruction_file(file_path):
            continue
        kept_parts.append(hunk_text)

    return redact_axis_ids("".join(kept_parts), axis_ids_by_axis)


def _extract_dep_name(line: str, filename: str) -> str:
    if filename == "requirements.txt":
        raw = line[1:].strip()
        # "somepackage==1.0" -> "somepackage"
        for sep in ("==", ">=", "<=", "!=", "~=", ">", "<", "[", ";", " "):
            idx = raw.find(sep)
            if idx != -1:
                raw = raw[:idx]
        return raw.strip()
    return line[1:].strip()


def compute_proxy(diff: str) -> DiffProxy:
    lines_added = 0
    lines_removed = 0
    files: list[str] = []
    new_deps: list[str] = []

    current_file: str | None = None

    for line in diff.splitlines():
        if line.startswith("+++ b/"):
            path = line[6:]
            if path not in files:
                files.append(path)
            current_file = path.rsplit("/", 1)[-1] if "/" in path else path
            continue

        if line.startswith("--- "):
            continue

        if line.startswith("+"):
            lines_added += 1
            is_dep_file = current_file and (
                current_file in DEP_FILES
                or any(current_file.endswith(ext) for ext in DEP_EXTENSIONS)
            )
            if is_dep_file:
                dep = _extract_dep_name(line, current_file)
                if dep:
                    new_deps.append(dep)
        elif line.startswith("-"):
            lines_removed += 1

    return DiffProxy(
        lines_added=lines_added,
        lines_removed=lines_removed,
        files_touched=len(files),
        file_list=files,
        new_deps=new_deps,
    )
