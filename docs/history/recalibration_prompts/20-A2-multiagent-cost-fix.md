# A2 follow-up — Multi-agent cost = $0 bug (capture fixture, then TDD the parser)

**Service:** Claude Code. Paste the block below into a **fresh** session. Found
during the methodology-axis shakeout (A2): methodologies whose agent delegates to
subagents (the `custom` claude-code pack) record `$0 / 0 tokens` even though the
run really cost ~$2. Single-agent methodologies record cost correctly. This is a
cost-axis integrity bug — it will silently zero the cost of any delegating setup.

The fix is small but **must be TDD'd against a real CLI JSON sample**, because the
`usage` vs `modelUsage` shapes are the whole point. Step 0 captures that sample.
Launch in an autonomous permission mode so the `claude` capture run and commits
don't prompt.

---

Paste to Claude Code:

```
You are fixing ONE bug in setup-bench: subagent-delegating trials record $0 cost
and 0 tokens. Work TDD. Do not start any other recalibration item. Do not push.

BACKGROUND (verified 2026-06-30, do not re-derive):
- cost/claude_usage.py:parse_claude_output reads token counts. At the `if usage:`
  branch it trusts the top-level `usage` object whenever it exists. In a run where
  the orchestrator DELEGATES to subagents (Task tool), the top-level `usage`
  reports ~0 input/output tokens; the real per-model totals (including subagent
  models) live in the top-level `modelUsage` dict, which is only a fallback that
  never fires. So input_tokens/output_tokens come back 0.
- Then cost/pricing.py:compute_api_rate_usd on 0 tokens returns ~$0, and
  runners/claude_code.py sets `usd_equiv = api_usd if api_usd is not None else
  total_cost_usd` — api_usd is 0.0 (not None), so the real self-reported
  total_cost_usd is discarded and usd_equiv becomes 0.
- Evidence: a `custom` claude-code trial recorded cost_record.usd_equiv=0.0,
  input_tokens=0, output_tokens=0, but native_amount (self-reported) = $2.03.
  Single-agent trials (baseline/ecc/karpathy) recorded correct non-zero tokens.

STEP 0 — CAPTURE A REAL FIXTURE (do this before touching code):
You need one genuine `claude --output-format json` payload from a DELEGATING run
(non-zero modelUsage, ~zero top-level usage) and one from a SINGLE-AGENT run.
- Single-agent sample: run, in any throwaway dir,
    echo "Reply with the single word: ok" | claude -p --output-format json \
      --model claude-haiku-4-5 --dangerously-skip-permissions --max-turns 2 \
      > C:\Users\norri\AppData\Local\Temp\sb-single.json
- Delegating sample: force a subagent dispatch so modelUsage has 2+ models. In a
  throwaway dir create `.claude/agents/echoer.md` with frontmatter
  (name: echoer / description / model: haiku / tools: Read) and a one-line body,
  then:
    printf '%s' "Use the Task tool to dispatch the echoer subagent with the prompt: say ok. Then reply done." \
      | claude -p --output-format json --model claude-haiku-4-5 \
        --dangerously-skip-permissions --max-turns 6 \
        > C:\Users\norri\AppData\Local\Temp\sb-multi.json
  If the model refuses to delegate, retry with a blunter instruction. Confirm
  sb-multi.json has a `modelUsage` object with >1 model and a top-level `usage`
  whose input_tokens+output_tokens is ~0 relative to modelUsage. If you genuinely
  cannot produce a delegating sample, fall back to capturing from a real `custom`
  trial: temporarily make runners/claude_code.py dump `stdout` to a file, run
  `cli.py run --task cosmos-A --methodology custom --repo-context none --model
  claude-haiku-4-5 --reps 1 --db scratch.db`, grab the JSON, then REVERT the dump
  patch and delete scratch.db.
- Save the two payloads (trimmed to the token-bearing fields if huge) as test
  fixtures, e.g. tests/fixtures/claude_usage_single.json and
  claude_usage_multiagent.json. Keep the REAL field names/shape from the capture.

STEP 1 — RED:
- parse_claude_output is currently tested in tests/test_claude_runner.py. Add a
  test loading the multi-agent fixture and asserting input_tokens>0 AND
  output_tokens>0 (the real modelUsage totals). Add/keep a single-agent test so
  the fix can't regress the common path. Run them; the multi-agent one must FAIL.

STEP 2 — GREEN (minimal):
- In cost/claude_usage.py prefer the `modelUsage` aggregate when it carries real
  tokens: aggregate input/output/cache across all modelUsage entries, and use that
  when it is non-zero; only fall back to top-level `usage` when modelUsage is
  absent or empty. (Match whatever field names the captured fixture actually uses
  — verify against the JSON, do not assume.)
- Also harden runners/claude_code.py so a computed api_usd of 0 does NOT override a
  non-zero self-reported total_cost_usd: when tokens are 0 / api_usd is 0 but
  total_cost_usd>0, fall back to the self-reported value for usd_equiv. Add a unit
  test for that fallback if one doesn't already cover it.

STEP 3 — VERIFY:
- Run `.venv\Scripts\python.exe -m pytest -q` — must be all green.
- Re-run one delegating trial end to end to confirm the DB now stores non-zero
  cost: `.venv\Scripts\python.exe cli.py run --task cosmos-A --methodology custom
  --repo-context none --model claude-haiku-4-5 --reps 1 --db scratch.db`, then
  query cost_record for that trial_id and confirm usd_equiv>0 and tokens>0. Delete
  scratch.db and remove any kept worktrees afterward (git -C repos/cosmos worktree
  remove --force ... ; git -C repos/cosmos worktree prune).

COMMIT: one commit, short honest message, e.g.
  "cost: aggregate modelUsage so subagent token usage isn't lost (fixes $0 cost)".
Co-Authored-By line as per repo convention. Do NOT push.

FINAL REPORT: the two fixture shapes (one line each), the failing-then-passing
test names, the verification cost numbers (before $0 / after $X), and the commit
SHA. Update the multiagent-cost-zero memory note to mark it FIXED with the SHA.
```
