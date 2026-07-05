"""Free local experiment: would cosmos-A hidden-tier trials pass the oracle if
the AuditDocument date-property NAME dependency were removed?

For each cosmos-A trial that reached the hidden tier (compile+visible passed):
scratch worktree at the task base, apply the agent's captured diff, copy the
held-out tests in, rewrite the oracle's `DateCreatedUtc` token to the agent's
actual document property name, run the task's hidden run_cmd. No frozen file
is touched; zero API spend.
"""
import re
import shutil
import sqlite3
import subprocess
import sys
from pathlib import Path

ROOT = Path(r"C:\Users\norri\studio\setup-bench-fable")
REPO = ROOT / "repos" / "cosmos"
BASE = "456ec3958e9d23ab9ae83e5f80aa82da88bc80b7"
HELD = ROOT / "tasks" / "cosmos-A" / "held_out_tests"
RUN_CMD = ('dotnet test tests/CleanArchitectureCosmosDB.UnitTests/'
           'CleanArchitectureCosmosDB.UnitTests.csproj --filter "FullyQualifiedName~Mapper"')
SCRATCH = Path(sys.argv[1]) if len(sys.argv) > 1 else Path(__file__).parent / "sim"
SCRATCH.mkdir(exist_ok=True)

con = sqlite3.connect(ROOT / "results.db")
con.row_factory = sqlite3.Row
trials = con.execute("""
    select t.id, r2.diff from trial t
    join gate_result g on g.trial_id=t.id
    join run_result r2 on r2.trial_id=t.id
    where t.task_id='cosmos-A' and g.compile_passed=1 and g.visible_passed=1
    order by t.id""").fetchall()

def sh(args, cwd, timeout=600):
    return subprocess.run(args, cwd=str(cwd), capture_output=True, text=True,
                          timeout=timeout, shell=isinstance(args, str))

results = []
for row in trials:
    tid = row["id"]
    short = tid.replace("cosmos-A_", "").replace("_none_", "_").replace("_claude-code", "")
    wt = SCRATCH / f"wt-{abs(hash(tid)) % 10**8}"
    print(f"=== {tid}", flush=True)
    if wt.exists():
        sh(["git", "worktree", "remove", "--force", str(wt)], REPO)
        shutil.rmtree(wt, ignore_errors=True)
    r = sh(["git", "worktree", "add", "--detach", str(wt), BASE], REPO)
    if r.returncode != 0:
        print("  worktree add FAILED:", r.stderr[:500]); results.append((tid, "wt-error")); continue
    try:
        agent_diff = row["diff"] or ""
        if agent_diff.strip():
            patch = wt / "_agent.diff"
            # write_bytes: text-mode write would CRLF-ify the patch on Windows
            patch.write_bytes(agent_diff.encode("utf-8"))
            r = sh(["git", "apply", "--whitespace=nowarn", "_agent.diff"], wt)
            if r.returncode != 0:
                print("  git apply FAILED:", r.stderr[:500]); results.append((tid, "apply-error")); continue
            patch.unlink()
        else:
            print("  (empty agent diff — running oracle against bare base)")

        # copy held-out tests under tests/
        for f in HELD.rglob("*"):
            if f.is_file():
                dest = wt / "tests" / f.relative_to(HELD)
                dest.parent.mkdir(parents=True, exist_ok=True)
                shutil.copy2(f, dest)

        # find agent's AuditDocument date property name
        name = None
        for cand in wt.rglob("AuditDocument.cs"):
            if "tests" in cand.parts:
                continue
            m = re.search(r"public\s+DateTime\??\s+(\w+)", cand.read_text(encoding="utf-8", errors="replace"))
            if m:
                name = m.group(1); break
        print(f"  agent date property: {name}")
        if name and name != "DateCreatedUtc":
            tf = wt / "tests" / "CleanArchitectureCosmosDB.UnitTests" / "Infrastructure" / "Mappers" / "AuditMapperTest.cs"
            src = tf.read_text(encoding="utf-8")
            tf.write_text(re.sub(r"\bDateCreatedUtc\b", name, src), encoding="utf-8")

        r = sh(RUN_CMD, wt, timeout=900)
        passed = r.returncode == 0
        tail = (r.stdout + r.stderr)[-1200:]
        print(f"  hidden-with-fix: {'PASS' if passed else 'FAIL'}")
        if not passed:
            errs = sorted(set(re.findall(r"error (CS\d+)", r.stdout + r.stderr)))
            fails = re.findall(r"Failed!? +- Failed: +(\d+)", r.stdout + r.stderr) or \
                    re.findall(r"Failed: +(\d+)", r.stdout + r.stderr)
            print(f"  cs_errors={errs} failed_counts={fails}")
            print("  tail:", tail.replace("\n", " | ")[-600:])
        results.append((tid, "PASS" if passed else "FAIL"))
    finally:
        sh(["git", "worktree", "remove", "--force", str(wt)], REPO)
        shutil.rmtree(wt, ignore_errors=True)

print("\n===== SUMMARY (hidden gate with naming dependency removed) =====")
for tid, res in results:
    print(f"  {res:12} {tid}")
