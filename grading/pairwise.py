"""Pairwise comparison — blind grading of trial diffs."""

import itertools
import logging
import random
import re

from pydantic import BaseModel

from core.models import Trial, RunResult

logger = logging.getLogger(__name__)

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
    seed: int | None = None,
) -> list[tuple[Trial, Trial]]:
    by_methodology: dict[str, list[Trial]] = {}
    for t in trials:
        by_methodology.setdefault(t.methodology_id, []).append(t)

    representatives: list[Trial] = []
    for methodology_id, group in by_methodology.items():
        best = min(group, key=lambda t: t.rep)
        representatives.append(best)

    pairs = list(itertools.combinations(representatives, 2))

    rng = random.Random(seed)
    result: list[tuple[Trial, Trial]] = []
    for a, b in pairs:
        if rng.random() < 0.5:
            result.append((a, b))
        else:
            result.append((b, a))

    return result


def _is_methodology_file(path: str) -> bool:
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


def anonymize_diff(diff: str, methodology_ids: list[str]) -> str:
    hunks = _split_file_hunks(diff)

    # Preserve any text before the first "diff --git" (unlikely but safe)
    prefix = diff.split("diff --git")[0] if "diff --git" in diff else diff

    kept_parts: list[str] = [prefix] if prefix else []
    for file_path, hunk_text in hunks:
        if _is_methodology_file(file_path):
            continue
        kept_parts.append(hunk_text)

    cleaned = "".join(kept_parts)

    for sid in methodology_ids:
        pattern = re.compile(re.escape(sid), re.IGNORECASE)
        cleaned = pattern.sub("[methodology]", cleaned)

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
