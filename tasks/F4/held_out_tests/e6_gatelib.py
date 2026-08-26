"""Deterministic instrumentation shared by the E6 gate wrappers (studio#83).

No LLM anywhere: every line emitted from here is computed from files in the
worktree and from `git diff` against the trial's setup baseline. The file is
kept byte-identical in each E6 task's held_out_tests dir — the gate only lays
down the one task's directory, so it cannot be shared across task dirs.
"""
from __future__ import annotations

import ast
import re
import subprocess
import sys
from pathlib import Path

import yaml

BASELINE = "refs/worktree/setup-bench-baseline"

# An OpenRouter-shaped model id: "<vendor>/<name>[:<suffix>]". The lookbehind
# keeps URLs ("https://openrouter.ai/api/v1") and nested paths from matching.
MODEL_ID = re.compile(r"(?<![\w./:-])[\w.-]+/[\w.:-]+")
# Tokens that are shaped like a model id but are plainly a file path.
_PATHISH = re.compile(
    r"\.(md|py|ya?ml|json|txt|db|xml|html?|css|js|jsx|ts|tsx|png|jpe?g|svg|ini|cfg|toml|lock|sh|ps1)$",
    re.I,
)


def git(root: Path, *args: str) -> tuple[int, str]:
    p = subprocess.run(["git", *args], cwd=str(root), capture_output=True, text=True,
                       encoding="utf-8", errors="ignore")
    return p.returncode, p.stdout or ""


def have_baseline(root: Path) -> bool:
    rc, _ = git(root, "rev-parse", "--verify", BASELINE)
    return rc == 0


def load_yaml(path: Path):
    try:
        return yaml.safe_load(path.read_text(encoding="utf-8")) or {}
    except Exception:
        return {}


def baseline_yaml(root: Path, rel: str):
    rc, out = git(root, "show", f"{BASELINE}:{rel}")
    if rc != 0:
        return None
    try:
        return yaml.safe_load(out) or {}
    except Exception:
        return None


def diff_body(root: Path, *pathspec: str) -> str:
    """`git diff BASELINE` (committed + uncommitted) with the `---`/`+++` file
    headers dropped, so a header line can never be read as a content line."""
    args = ["diff", BASELINE]
    if pathspec:
        args += ["--", *pathspec]
    rc, out = git(root, *args)
    if rc != 0:
        return ""
    return "\n".join(l for l in out.splitlines()
                     if not l.startswith("+++ ") and not l.startswith("--- "))


def model_ids_in(text: str) -> set[str]:
    return {t for t in MODEL_ID.findall(text) if not _PATHISH.search(t)}


def is_model_id(value) -> bool:
    return isinstance(value, str) and bool(re.fullmatch(r"[\w.-]+/[\w.:-]+", value))


def configured_model_ids(llm) -> set[str]:
    """Every model-id-shaped string leaf under the `llm:` block (`api_key`
    excluded). Shape-agnostic: a single `model:` and a `models:` mapping of
    per-stage ids both land here, and non-id strings (`provider: openrouter`,
    a base URL) do not."""
    found: set[str] = set()

    def walk(node, key=None):
        if isinstance(node, dict):
            for k, v in node.items():
                walk(v, k)
        elif isinstance(node, (list, tuple)):
            for v in node:
                walk(v, key)
        elif key != "api_key" and is_model_id(node):
            found.add(node)

    walk(llm)
    return found


# --------------------------------------------------------------------------
# Locating and running the trial's OWN tests (baseline-independent: the files
# are found by content, never by diffing against a ref that may not exist)
# --------------------------------------------------------------------------

def find_test_files(root: Path, exclude: set[str]) -> list[Path]:
    """Every test file in the worktree's test tree, minus the held-out files."""
    found: list[Path] = list(root.glob("test_*.py"))
    if (root / "tests").is_dir():
        found += list((root / "tests").rglob("test_*.py"))
    return sorted({p for p in found if p.name not in exclude})


def list_test_functions(root: Path, path: Path) -> list[tuple[str, str]]:
    """[(pytest node id, source)] for every test function in `path`.

    Parsed with `ast` — the file is never imported, so a test that needs
    fixtures or heavy deps can still be located and named."""
    try:
        src = path.read_text(encoding="utf-8", errors="ignore")
        tree = ast.parse(src)
    except (OSError, SyntaxError):
        return []
    rel = path.relative_to(root).as_posix()
    out: list[tuple[str, str]] = []

    def visit(node, prefix: str) -> None:
        for child in getattr(node, "body", []):
            if isinstance(child, ast.ClassDef):
                visit(child, f"{prefix}{child.name}::")
            elif isinstance(child, (ast.FunctionDef, ast.AsyncFunctionDef)) \
                    and child.name.startswith("test_"):
                out.append((f"{rel}::{prefix}{child.name}",
                            ast.get_source_segment(src, child) or ""))

    visit(tree, "")
    return out


def run_pytest(root: Path, target: str, timeout: int = 300) -> int:
    """Run one pytest target in the worktree. `-o addopts=` drops the repo's
    own `-v --tb=short`; no cache provider, so nothing is written to the tree."""
    try:
        p = subprocess.run(
            [sys.executable, "-m", "pytest", target, "-q", "--tb=no",
             "-p", "no:cacheprovider", "-o", "addopts="],
            cwd=str(root), capture_output=True, text=True,
            encoding="utf-8", errors="ignore", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        return 124
    return p.returncode


# --------------------------------------------------------------------------
# memspace instrumentation
# --------------------------------------------------------------------------

def print_fire_lines(root: Path) -> None:
    """Counts from `.memspace/fire.log`, whose lines a compiled memspace hook
    writes as `FIRE <iso-ts> <fact-id> stop` / `BLOCK <iso-ts> <fact-id> <why>`.
    No log (no hooks, or none ever ran) means zero, never SKIP: the counts do
    not need the baseline ref."""
    counts: dict[str, int] = {}
    blocks = 0
    log = root / ".memspace" / "fire.log"
    if log.is_file():
        for line in log.read_text(encoding="utf-8", errors="ignore").splitlines():
            parts = line.split()
            if len(parts) < 3:
                continue
            if parts[0] == "FIRE":
                counts[parts[2]] = counts.get(parts[2], 0) + 1
            elif parts[0] == "BLOCK":
                blocks += 1
    for fact_id in sorted(counts):
        print(f"FIRE-COUNT {fact_id} {counts[fact_id]}")
    print(f"FIRE-TOTAL {sum(counts.values())}")
    print(f"BLOCK-COUNT {blocks}")


def glob_to_regex(glob: str) -> re.Pattern:
    """Translate a rule's `paths:` glob to a regex over forward-slash relative
    paths. `**/` means "any number of leading directories, including none", so
    `**/config.yaml` also matches a bare `config.yaml` at the repo root; `**`
    matches anything; `*` and `?` never cross a `/`; everything else is a
    literal and the whole path must match."""
    out: list[str] = []
    i = 0
    while i < len(glob):
        if glob.startswith("**/", i):
            out.append("(?:.*/)?")
            i += 3
        elif glob.startswith("**", i):
            out.append(".*")
            i += 2
        elif glob[i] == "*":
            out.append("[^/]*")
            i += 1
        elif glob[i] == "?":
            out.append("[^/]")
            i += 1
        else:
            out.append(re.escape(glob[i]))
            i += 1
    return re.compile("".join(out) + r"\Z")


def _rule_paths(rule_file: Path) -> list[str]:
    text = rule_file.read_text(encoding="utf-8", errors="ignore")
    if not text.startswith("---"):
        return []
    end = text.find("\n---", 3)
    if end < 0:
        return []
    try:
        front = yaml.safe_load(text[3:end]) or {}
    except Exception:
        return []
    paths = front.get("paths") or []
    return [str(p) for p in paths] if isinstance(paths, list) else []


def print_rule_match_lines(root: Path) -> None:
    """Rule-firing proxy: a `.claude/rules/<fact-id>.md` "fired" iff any path
    the trial changed since the baseline matches one of its frontmatter globs.
    Needs the baseline diff, so it SKIPs when the ref is absent."""
    if not have_baseline(root):
        print("RULE-MATCH SKIP no baseline ref")
        print("RULE-MATCH-TOTAL SKIP no baseline ref")
        return
    rc, out = git(root, "diff", BASELINE, "--name-only")
    changed = [p.strip() for p in out.splitlines() if p.strip()]
    fired = 0
    rules_dir = root / ".claude" / "rules"
    if rules_dir.is_dir():
        for rule in sorted(rules_dir.glob("*.md")):
            patterns = [glob_to_regex(g) for g in _rule_paths(rule)]
            hit = next((p for p in changed if any(r.match(p) for r in patterns)), None)
            if hit is not None:
                fired += 1
                print(f"RULE-MATCH {rule.stem} {hit}")
    print(f"RULE-MATCH-TOTAL {fired}")
