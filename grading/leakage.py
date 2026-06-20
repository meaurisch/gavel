"""Leakage detector: scans a repo for dangling references to reverted features."""

import argparse
import subprocess
import sys
from pathlib import Path

from core.models import LeakageReport


def _is_comment(line: str) -> bool:
    stripped = line.lstrip()
    return stripped.startswith("#") or "//" in stripped or "/*" in stripped


def scan(repo_path: Path, feature_terms: list[str], last_n: int = 20) -> LeakageReport:
    hits: list[str] = []

    tracked = subprocess.run(
        ["git", "ls-files"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
        check=True,
    ).stdout.splitlines()

    for relpath in tracked:
        fpath = repo_path / relpath
        try:
            text = fpath.read_text(encoding="utf-8", errors="ignore")
        except OSError:
            continue
        for lineno, line in enumerate(text.splitlines(), 1):
            if any(term in line for term in feature_terms):
                prefix = "comment " if _is_comment(line) else ""
                hits.append(f"{prefix}{relpath}:{lineno}")

    log_output = subprocess.run(
        ["git", "log", f"-n{last_n}", "-p", "--"],
        cwd=str(repo_path),
        capture_output=True,
        text=True,
    ).stdout
    for lineno, line in enumerate(log_output.splitlines(), 1):
        if any(term in line for term in feature_terms):
            hits.append(f"git-log:{lineno}")

    return LeakageReport(hits=hits, any_found=len(hits) > 0)


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Scan for dangling feature references")
    parser.add_argument("--repo", default=".", help="Repository path")
    parser.add_argument("--terms", nargs="+", required=True, help="Feature terms to search for")
    parser.add_argument("--last-n", type=int, default=20, help="Number of git log entries to scan")
    parser.add_argument("--verbose", action="store_true", help="Print all hits")
    args = parser.parse_args(argv)

    report = scan(Path(args.repo), args.terms, args.last_n)

    if report.any_found:
        for hit in report.hits:
            print(hit)
        print(f"\n{len(report.hits)} leakage hit(s) found", file=sys.stderr)
        return 1

    if args.verbose:
        print("No leakage found")
    return 0


if __name__ == "__main__":
    sys.exit(main())
