"""Adherence report for the studio#48 ablation (spec section 8).

Parses the ADHERENCE <id> PASS|FAIL|SKIP lines that tasks/studio-*/held_out_tests/
run_hidden.py prints into the hidden gate output, and reports:

  --screen   liveness screen over the studio-none trials: a task survives iff at
             least one applicable check FAILs across its trials; a convention
             survives iff it FAILs at least once overall.
  (default)  per repo-context adherence-rate (fraction of applicable checks
             passed), the spec's primary metric, plus functional pass-rates.

SKIP lines (oracle/nop runs without a baseline ref) are excluded everywhere.
"""
import argparse
import re
import sqlite3
from collections import defaultdict
from pathlib import Path

LINE = re.compile(r"^ADHERENCE (L\d) (PASS|FAIL|SKIP)\b(.*)$", re.M)


def load(db_path):
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    rows = conn.execute(
        """SELECT t.id AS trial_id, t.task_id, t.repo_context_id, t.runner, t.rep,
                  g.passed, g.hidden_output
           FROM trial t JOIN gate_result g ON g.trial_id = t.id
           WHERE t.runner = 'claude-code'"""
    ).fetchall()
    trials = []
    for r in rows:
        checks = {m.group(1): (m.group(2), m.group(3).strip())
                  for m in LINE.finditer(r["hidden_output"] or "")}
        trials.append({
            "trial_id": r["trial_id"], "task": r["task_id"],
            "context": r["repo_context_id"], "rep": r["rep"],
            "functional_passed": bool(r["passed"]), "checks": checks,
        })
    return trials


def screen(trials):
    none_trials = [t for t in trials if t["context"] == "studio-none"]
    print(f"Liveness screen over {len(none_trials)} studio-none trials\n")
    task_fails, conv_fails = defaultdict(int), defaultdict(int)
    task_counts = defaultdict(int)
    for t in none_trials:
        task_counts[t["task"]] += 1
        for cid, (verdict, detail) in sorted(t["checks"].items()):
            if verdict == "SKIP":
                continue
            mark = "FAIL" if verdict == "FAIL" else "pass"
            print(f"  {t['trial_id']}: {cid} {mark}  {detail}")
            if verdict == "FAIL":
                task_fails[t["task"]] += 1
                conv_fails[cid] += 1
    print("\nTask survival (needs >=1 FAIL across its trials):")
    surviving_tasks = []
    for task in sorted(task_counts):
        ok = task_fails[task] >= 1
        surviving_tasks.append(task) if ok else None
        print(f"  {task}: {task_fails[task]} FAILs over {task_counts[task]} trials -> "
              f"{'SURVIVES' if ok else 'DROPPED'}")
    print("\nConvention survival (needs >=1 FAIL overall):")
    surviving_convs = [c for c in ("L1", "L2", "L3") if conv_fails[c] >= 1]
    for c in ("L1", "L2", "L3"):
        print(f"  {c}: {conv_fails[c]} FAILs -> {'SURVIVES' if conv_fails[c] else 'DROPPED'}")
    verdict = len(surviving_tasks) >= 2 and len(surviving_convs) >= 2
    print(f"\nSCREEN VERDICT: {len(surviving_tasks)} tasks, {len(surviving_convs)} "
          f"conventions survive -> {'PROCEED to the full matrix' if verdict else 'STOP: not measurable at 24 trials'}")
    return verdict


def full(trials):
    by_ctx = defaultdict(list)
    for t in trials:
        by_ctx[t["context"]].append(t)
    print(f"{'context':24} {'adherence':>10} {'checks':>8} {'functional':>11} {'trials':>7}")
    for ctx in sorted(by_ctx):
        ts = by_ctx[ctx]
        applicable = [(cid, v) for t in ts for cid, (v, _) in t["checks"].items() if v != "SKIP"]
        passed = sum(1 for _, v in applicable if v == "PASS")
        fn = sum(1 for t in ts if t["functional_passed"])
        rate = f"{100*passed/len(applicable):5.1f}%" if applicable else "  n/a"
        print(f"{ctx:24} {rate:>10} {passed:>3}/{len(applicable):<4} {fn:>5}/{len(ts):<5} {len(ts):>7}")
    print("\nPer task x context (adherence passed/applicable, functional):")
    keys = sorted({(t['task'], t['context']) for t in trials})
    for task, ctx in keys:
        ts = [t for t in trials if t["task"] == task and t["context"] == ctx]
        applicable = [(cid, v) for t in ts for cid, (v, _) in t["checks"].items() if v != "SKIP"]
        passed = sum(1 for _, v in applicable if v == "PASS")
        fn = sum(1 for t in ts if t["functional_passed"])
        detail = " ".join(f"{cid}:{sum(1 for c, v in applicable if c == cid and v == 'PASS')}"
                          f"/{sum(1 for c, _ in applicable if c == cid)}"
                          for cid in ("L1", "L2", "L3") if any(c == cid for c, _ in applicable))
        print(f"  {task} x {ctx:24} adherence {passed}/{len(applicable)}  functional {fn}/{len(ts)}  [{detail}]")


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--db", default="results-48.db")
    ap.add_argument("--screen", action="store_true")
    args = ap.parse_args()
    trials = load(Path(args.db))
    if not trials:
        print("no claude-code trials with gate results yet")
        raise SystemExit(1)
    screen(trials) if args.screen else full(trials)
