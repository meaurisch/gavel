# R1 — Build P2.1 + P2.2 (Claude Code)  — only if the spike PASSED

**Service:** Claude Code (TDD). This project is in Agent Mode — let the
studio-conductor plan, studio-executor implement.
**Goal:** implement the two remaining prompts. The canonical prompt text already
exists in the repo; this file tells you how to drive them.

---

### P2.1 — Copilot CLI runner. Paste to Claude Code:

```
Implement the Copilot CLI runner. The verbatim spec is in
prompts/P2.1-copilot-runner.md — read it and implement it exactly:
runners/copilot_cli.py against the Runner protocol in runners/base.py, executing
  copilot -p "<task.instruction>" -s --no-ask-user --model <work_model> --allow-tool='write, shell'
in the worktree, authenticated via COPILOT_GITHUB_TOKEN from .env. Capture the
diff via collect(); attach NO cost at execute time (cost comes from P2.2, joined
on trial_id); record the model actually used into the Trial. Add a smoke test
behind an env flag so it only runs when COPILOT_GITHUB_TOKEN is present.

Use TDD. Mirror the structure/tests of runners/claude_code.py. Run
`.venv\Scripts\python.exe -m pytest -q` (green) and commit.
```

### P2.2 — Standalone Copilot usage calculator. Paste to Claude Code:

```
Implement the standalone Copilot usage calculator. The verbatim spec is in
prompts/P2.2-copilot-usage-calculator.md — read it and implement it exactly:
cost/copilot_usage.py as a STANDALONE module + CLI with ZERO dependency on
setup-bench internals (pip-installable elsewhere). Inputs as pluggable sources
(VS Code Chat Debug View dump; GitHub org Copilot usage report). Config
rates.yaml (model -> input/output/cached per-MTok + credits_per_usd: 100).
Output a SessionCost(model, input_tokens, output_tokens, cached_tokens, usd,
credits) + one-line summary. CLI: `copilot-usage from-debug <file> --model <m>`
and `copilot-usage from-report --user <u> --since <t>`. Unit-test the math
against a hand-worked example. THEN add a thin adapter in setup-bench that calls
it to fill CostRecord for copilot trials, joined on trial_id.

Keep studio conventions: type hints, pydantic models, argparse/Typer with
--help, exit codes 0/1/2. Use TDD. Green pytest, commit. Finally update
prompts/README.md to mark P2.1 and P2.2 done, and README.md "Current state" so
copilot-cli is no longer described as a stub.
```

---

After both land and tests are green, tick **R1**, then prompt `13`.
