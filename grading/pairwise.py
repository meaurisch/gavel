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


def anonymize_diff(
    diff: str,
    axis_ids_by_axis: dict[str, list[str]],
    skip_ids: frozenset[str] | set[str] = frozenset(),
) -> str:
    """Strip instruction files and redact axis ids from a diff.

    Ids are matched as whole tokens (case-insensitive), never inside larger
    identifiers — the repo-context id ``cosmos`` must not mangle a
    ``CosmosDbData`` namespace. ``skip_ids`` names causally-inert ids to leave
    alone: a value that lays down zero files (the ``none`` context, the
    ``baseline`` methodology) has no path into diff content, so any occurrence
    is incidental code — redacting it (e.g. Python's ``None``) would wreck
    readability without adding blinding.
    """
    hunks = _split_file_hunks(diff)

    # Preserve any text before the first "diff --git" (unlikely but safe)
    prefix = diff.split("diff --git")[0] if "diff --git" in diff else diff

    kept_parts: list[str] = [prefix] if prefix else []
    for file_path, hunk_text in hunks:
        if _is_instruction_file(file_path):
            continue
        kept_parts.append(hunk_text)

    cleaned = "".join(kept_parts)

    sid_tokens: list[tuple[str, str]] = []
    for axis, ids in axis_ids_by_axis.items():
        token = AXIS_TOKENS[axis]
        for sid in ids:
            if sid in skip_ids:
                continue
            sid_tokens.append((sid, token))

    for sid, token in sorted(sid_tokens, key=lambda pair: len(pair[0]), reverse=True):
        pattern = re.compile(rf"(?<!\w){re.escape(sid)}(?!\w)", re.IGNORECASE)
        cleaned = pattern.sub(token, cleaned)

    return cleaned


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
