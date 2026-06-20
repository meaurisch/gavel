# Implementation Plan — Local Benchmarking Framework for Agentic Coding Setups

A from-scratch, local-first framework to compare agentic coding **setups** (instruction/skill packs) across **harnesses**, **models**, and **tasks**, scored on *would-I-merge* quality and on cost. Built to run on your personal machine against public proxy repos, with a minimal manual confirmation tier on the work machine. Working name: `setup-bench`.

---

## 0. Decisions locked for this plan

**Settled in discussion**

- **Build from scratch**, local-first. No Harbor runtime, no Docker, no cloud sandboxes. Borrow only invocation know-how (CLI flags) and the task-format *shape*.
- **Four axes**, independent and swappable: Harness × Model × Setup × Task.
- **Runner abstraction** is the backbone. Concrete runners: `claude-code` (headless), `copilot-cli` (headless), `manual` (human-in-IDE). New harnesses later = new runners.
- **Isolation** via fresh `git worktree` per trial; held-out tests live *outside* the worktree, applied only at grade time (leakage-safe by construction).
- **Quality** = binary held-out-test gate, then **blind pairwise forced-choice** ("A or B, which would I merge?") among survivors, with a 4-dim rubric recorded as explainer and diff proxies (lines/files/deps) as objective sanity checks.
- **Reps** = 2–3 per cell. Winner consistent across reps → trust it. Winner flips → record a **tie**. Flips are your noise floor.
- **Cost** = heterogeneous units, reconciled to a USD-equivalent while always keeping the native unit. Claude Code self-reports (`--output-format json` → `total_cost_usd` + `usage`). Copilot via a **standalone session-usage calculator** (tokens × published rate), built here as a reusable component (option 2).
- **No paid Pro+ month.** The hard frontloading gate relaxes to a lighter ordering principle: build + validate before measuring; all personal-machine work before the work machine; work tier stays minimal and manual.

**Recommended defaults you still own (change any without breaking the plan)**

| Decision | Default | Note |
|---|---|---|
| Setup shortlist | Baseline (repo instructions), Karpathy, Superpowers, ECC, your custom — all 5 | Baseline is the must-beat; Karpathy = lean end, ECC = heavy end |
| Claude Code model sweep | Haiku 4.5, Sonnet 4.6, Opus 4.8 | cheap → mid → top |
| Work model spread | 1 Anthropic (Sonnet-class) + 1 OpenAI (a GPT-5.x / Codex) | prune with Phase-1 results |
| Rubric | 4 dims (correctness, diff-minimality, readability/idiom, over-engineering), equal weight, **recorded not summed** | pairwise choice dominates; cost breaks ties |
| LLM judge | **Skip in v1** | you have few enough comparisons to do by hand; you are the gold standard |
| Decision rule | Quality×cost frontier; **stakes-based pick** | high-stakes paths → quality winner regardless of cost; routine → cheapest setup quality-indistinguishable from winner |
| Task count | 5 (2 discriminators + 1 under-specified + 2 from your mix) | keep FIXED once frozen |

---

## 1. Architecture

```
setup-bench/
  core/
    models.py          # Trial, TaskSpec, SetupSpec, RunResult, CostRecord schemas
    matrix.py          # expands Setup × Model × Task × Rep into Trials
    worktree.py        # fresh git worktree per trial; teardown
  runners/
    base.py            # Runner protocol: prepare() -> execute() -> collect()
    claude_code.py     # headless `claude -p --output-format json`
    copilot_cli.py     # headless `copilot -p -s --no-ask-user --model ...`
    manual.py          # human-in-IDE; tool prepares + collects, human executes
    oracle.py / nop.py # pipeline self-tests (oracle applies reference diff; nop does nothing)
  grading/
    gate.py            # apply held-out tests outside worktree -> pass/fail
    leakage.py         # post-revert scan for dangling references to the feature
    pairwise.py        # anonymize diffs, serve A/B, record choice + rubric
    aggregate.py       # win matrix, cost rollup, frontier, decision
  cost/
    copilot_usage.py   # STANDALONE reusable: tokens -> USD-equiv + credits
    claude_usage.py    # parse `--output-format json`
  tasks/
    <task_id>/
      task.yaml        # instruction, repo ref + commit, setup hook, run cmd
      held_out_tests/  # NEVER copied into the worktree the agent sees
      reference.diff   # the reverted feature (oracle runner + held-out source)
  setups/
    baseline/ karpathy/ superpowers/ ecc/ custom/
      manifest.yaml    # native files per harness: CLAUDE.md / AGENTS.md / copilot-instructions.md
  ui/                  # local web app for blind pairwise grading
  cli.py               # `setup-bench run|grade|report`
```

**Per-trial pipeline (identical across runners):**

1. `worktree.create()` — fresh worktree at the task's base commit (feature reverted).
2. Lay down the setup's instruction files (or none, for the instructions-OFF ablation).
3. Runner `execute()` — headless CLI call, or manual hand-off.
4. Capture `git diff` (the candidate solution) + cost record.
5. `gate.apply()` — copy held-out tests in *now*, run them, record pass/fail, then discard.
6. Emit one standard `Trial` record (diff, pass/fail, cost native + USD-equiv, tokens, metadata).
7. `worktree.destroy()`.

The only manual parts in the `manual` runner are: you drive your IDE, and the cost is read by the standalone calculator. Worktree setup, file placement, test execution, gating, and diff capture are automated identically.

---

## 2. Phasing & ordering

- **Phase 0 — Scaffold & validate the engine.** Build core data model, runner abstraction, `manual` + `oracle` + `nop` runners, the grader and leakage checker. Prove the pipeline on one toy task: `oracle` passes the gate, `nop` fails it. No real measurement yet.
- **Phase 1 — Claude Code surface (the precise surface).** Add the `claude-code` headless runner + cost JSON capture. Author the real tasks (revert + held-out tests + leakage check). Install + freeze the 5 setup packs. Build the pairwise grading UI. Run the Anthropic model sweep × setup bake-off on the proxy repos. Grade.
- **Phase 1.5 — Copilot CLI spike (15 min, personal machine, public repo).** Install Copilot CLI, auth with your own token, run one `copilot -p` task, eyeball behavior vs your VS Code agent-mode experience. Outcome selects the Phase-2 runner: `copilot-cli` if representative + permitted, else `manual`.
- **Phase 2 — Copilot surface.** Add the chosen runner + build the standalone usage calculator. Run the work-model matrix on the proxy repos. Prune cells using Phase-1 results.
- **Phase 3 — Work confirmation (minimal, manual).** On the work machine, run the shortlist on the *real* repos with the *real* instructions, in VS Code, by hand. Read credit deltas via the usage calculator. Confirm the proxy ranking holds.
- **Phase 4 — Decision rollup.** Frontier + stakes-based pick.

---

## 3. Definition of Ready (gate before any *measurement* run)

Green-light Phase 1's measurement (and again before Phase 3) only when all are true:

- [ ] Proxy repos cloned; Cosmos augmentation done and **capped at 1–2 aggregates** (AutoMapper replaced with hand-written mappers + per-pair mapping tests).
- [ ] Each task authored: feature reverted cleanly, base commit pinned, run command verified.
- [ ] Held-out tests extracted **and strengthened** beyond what the original PR shipped (insufficient tests = false-positive merges).
- [ ] Leakage check **green** for every task (no dangling references in tree / recent git log / comments).
- [ ] 5 setup packs installed in each harness's native form and **frozen** (snapshot committed).
- [ ] Instructions-OFF ablation toggle works.
- [ ] Grader validated: `oracle` → pass, `nop` → fail, on every task.
- [ ] Runner abstraction validated with `manual` + `claude-code`.
- [ ] Cost capture validated: Claude JSON parsed correctly; Copilot calculator reproduces a known dashboard delta within tolerance.
- [ ] Pairwise UI tested with dummy diffs (anonymization confirmed — grader cannot tell which setup is which).
- [ ] Matrix driver scripted; full dry run on one task × all setups completed.

---

## 4. Verbatim Claude Code prompts

The ordered build prompts live as one file each in `prompts/` (P0.1 → P3). Paste them
into Claude Code in order; each assumes prior steps are done. Pin your CLI version
first (a known `-p` bug shipped in one 2.1.x release):
`npm install -g @anthropic-ai/claude-code@latest`, then record the version in this
repo's README.

---

## 5. Run protocol per surface

**Claude Code (personal, automated).** `setup-bench run --task all --setup all --model haiku,sonnet,opus --runner claude-code --reps 3`. Fully automated: cost self-reported, gate automatic. Stagger across the day if you brush rate limits; the driver is resumable. This is your precise surface — the model sweep and setup bake-off both live here.

**Copilot CLI (personal, automated — if the spike passed).** Same command with `--runner copilot-cli --model <work models>`, `COPILOT_GITHUB_TOKEN` exported. Diffs and gate are automatic; cost is filled afterward by `copilot-usage` from the org report or a debug-view export, joined on trial_id. Prune the grid using Phase-1 Claude results so you don't run cells whose ranking is already obvious.

**Manual (work confirmation, minimal).** `setup-bench run --runner manual` prepares each trial (fresh worktree, setup files placed, instruction printed) and waits. You complete the one task in VS Code exactly as you normally work, press Enter; the tool captures the diff and runs the held-out gate. Bracket the session and feed the token counts to `copilot-usage` for the credit/USD figure. Keep this tier to the shortlist only — it exists to confirm the proxy ranking holds on real repos with real instructions, nothing more.

**Grading (all surfaces).** Launch the UI, grade blind pairwise per (task, model) over gate-passers, advance with the keyboard. Then `setup-bench report`.

---

## 6. How results become the adoption decision

1. **Gate** removes anything that doesn't pass the strengthened held-out tests — those are simply out.
2. **Blind pairwise** over survivors yields, per task, a direction (which setup you'd merge), collapsed across reps with flips counted as ties.
3. **Preponderance** across tasks gives an overall quality ordering — not a significance claim, a consistent-direction read calibrated to your own merge bar.
4. **Cost** (measured exactly even at small n) breaks quality ties and draws the frontier.
5. **Stakes rule** turns the frontier into one pick per tier: high-stakes → the quality winner; routine → the cheapest setup indistinguishable from it.
6. **Confirm** that pick survives the manual work-repo tier before adopting. Adopt, stay alert, don't carve it in stone — this is a decision aid sized to your downside (a slightly suboptimal setup), not a published benchmark.

---

## 7. Open knobs to set before you execute

These don't block the build; set them before the **measurement** runs:

- Final task set (the 2 discriminators + under-specified + 2 mix), each tagged with a stakes tier.
- Which specific work models go in the Copilot grid (after the spike confirms the surface).
- `--max-turns` cap per harness and the rep count (2 vs 3).
- Whether the `custom` setup is frozen and ready to vendor.
