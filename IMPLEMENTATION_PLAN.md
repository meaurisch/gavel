# Implementation Plan — Local Benchmarking Framework for Agentic Coding Methodologies

A from-scratch, local-first framework to compare agentic coding **methodologies**
(instruction / skill packs) across **repo-contexts**, **models**, **runners**
(harnesses), and **tasks**, scored on *would-I-merge* quality and on cost. Built
to run on your personal machine against public proxy repos, with a minimal manual
confirmation tier on the work machine. Working name: `setup-bench`.

---

## 0. Decisions locked for this plan

**Settled in discussion**

- **Build from scratch**, local-first. No Harbor runtime, no Docker, no cloud sandboxes. Borrow only invocation know-how (CLI flags) and the task-format *shape*.
- **Five axes**, independent and swappable: **Task × Methodology × Repo-Context × Model × Runner**. "Setup" (the original framing) split into two: **methodology** = the instruction/skill pack under test; **repo-context** = repo-specific instructions laid into the worktree *under* the methodology. They are applied sequentially, never merged.
- **Comparison is axis-general.** *Any* axis can be the comparison target. The chosen axis varies while every other axis is held fixed per "cell"; the diffs shown to the grader redact **every** axis id, so blind A/B works for whichever axis you're comparing. Default comparison axis is methodology, but model, repo-context, or runner are all selectable.
- **Runner abstraction** is the backbone. Concrete runners: `claude-code` (headless), `copilot-cli` (headless), `manual` (human-in-IDE). New harnesses later = new runners.
- **Isolation** via fresh `git worktree` per trial; held-out tests live *outside* the worktree, applied only at grade time (leakage-safe by construction).
- **Quality** = a **three-tier gate scorecard** (compile → visible tests → hidden tests) recorded per trial, then **blind pairwise forced-choice** ("A or B, which would I merge?") among hidden-gate passers, with **multi-rep sampling** and a **Bradley-Terry** ranking (Elo-style scores + bootstrap CIs). A 4-dim rubric is recorded as explainer; diff proxies (lines/files/deps) are objective sanity checks.
- **Reps** = 2–3 per cell. Multi-rep sampling feeds all reps into pairwise comparison; Bradley-Terry collapses the votes into a ranking with confidence intervals. Overlapping CIs = statistically indistinguishable.
- **Cost** = computed from **token counts × published API rates** (data-driven pricing table in `cost/pricing.toml`, refreshable via `setup-bench pricing fetch`). Self-reported cost (Claude Code `--output-format json` → `total_cost_usd`) is kept as a secondary reference value. Copilot tokens priced through the same table.
- **No paid Pro+ month.** The hard frontloading gate relaxes to a lighter ordering principle: build + validate before measuring; all personal-machine work before the work machine; work tier stays minimal and manual.

**Recommended defaults you still own (change any without breaking the plan)**

| Decision | Default | Note |
|---|---|---|
| Methodology shortlist | Baseline (no instructions), Karpathy, Superpowers, ECC, your custom — all 5 | Baseline is the must-beat; Karpathy = lean end, ECC = heavy end |
| Repo-context | `none` (ablation) + your repo-specific instructions | `none` is the control; repo-contexts carry `task_affinity` so nonsensical pairings are skipped |
| Comparison axis | Methodology | Any axis (methodology / model / repo-context / runner) is selectable as the comparison target; the rest are held fixed |
| Claude Code model sweep | Haiku 4.5, Sonnet 4.6, Opus 4.8 | cheap → mid → top |
| Work model spread | 1 Anthropic (Sonnet-class) + 1 OpenAI (a GPT-5.x / Codex) | prune with Phase-1 results |
| Rubric | 4 dims (correctness, diff-minimality, readability/idiom, over-engineering), equal weight, **recorded not summed** | pairwise choice dominates; cost breaks ties |
| LLM judge | **Skip in v1** | you have few enough comparisons to do by hand; you are the gold standard |
| Decision rule | Quality×cost frontier; **stakes-based pick** | high-stakes paths → quality winner regardless of cost; routine → cheapest indistinguishable from winner |
| Task count | 5 (2 discriminators + 1 under-specified + 2 from your mix) | keep FIXED once frozen |

---

## 1. Architecture

```
setup-bench/
  core/
    models.py            # Trial, TaskSpec, MethodologySpec, RepoContextSpec, GateResult, RunResult, CostRecord
    matrix.py            # expands Task × Methodology × Repo-Context × Model × Rep into Trials (5-axis)
    methodology_loader.py# resolve (methodology_id, harness) -> MethodologySpec
    repo_context_loader.py# resolve (repo_context_id, harness) -> RepoContextSpec; task-affinity
    worktree.py          # fresh git worktree per trial; teardown
  runners/
    base.py              # Runner protocol: prepare() -> execute() -> collect(); lay_down_files()
    claude_code.py       # headless `claude -p --output-format json`
    copilot_cli.py       # headless `copilot -p -s --no-ask-user --model ...`
    manual.py            # human-in-IDE; tool prepares + collects, human executes
    oracle.py / nop.py   # pipeline self-tests (oracle applies reference diff; nop does nothing)
  grading/
    gate.py              # three-tier gate scorecard: compile -> visible -> hidden -> GateResult
    leakage.py           # post-revert scan for dangling references to the feature
    pairwise.py          # generate_pairs(trials, axis) within a cell; anonymize ALL axis ids; serve A/B
    bradley_terry.py     # MLE BT fit + bootstrap CIs + Elo-style display scores
    analyzer.py          # non-discriminating / flaky / cost-quality flags per comparison-axis value
    aggregate.py         # cost rollup, frontier, stakes decision
  cost/
    pricing.toml         # published API rates (Anthropic + OpenAI); `pricing fetch`/`pricing add`
    copilot_usage.py     # STANDALONE reusable: tokens -> USD-equiv + credits
    claude_usage.py      # parse `--output-format json` (secondary, self-reported)
  tasks/
    <task_id>/
      task.yaml          # instruction, repo ref + commit, run cmd
      held_out_tests/    # NEVER copied into the worktree the agent sees
      reference.diff     # the reverted feature (oracle runner + held-out source)
  methodologies/
    baseline/ karpathy/ superpowers/ ecc/ custom/
      manifest.yaml      # native files per harness: CLAUDE.md / AGENTS.md / copilot-instructions.md
  repo_contexts/
    cosmos/ none/ pyvrp-instructions/
      manifest.yaml      # noop control + repo-specific instructions; `task_affinity` tags
  ui/                    # local web app for blind pairwise grading (axis picker + cascading cells)
  cli.py                 # `setup-bench run|grade|report|pricing`
```

**Per-trial pipeline (identical across runners):**

1. `worktree.create()` — fresh worktree at the task's base commit (feature reverted).
2. Lay down files in order: **repo-context files first** (the fixed environment), **methodology files second** (the thing under test) — two commits, applied sequentially, never merged. (`baseline` / `none` lay down nothing — the ablation controls.)
3. Runner `execute()` — headless CLI call, or manual hand-off.
4. Capture `git diff` (the candidate solution) + cost record (tokens → USD via `pricing.toml`).
5. `gate.apply()` — run the **three-tier gate** (compile → visible tests → hidden tests), copying held-out tests in *now*, recording a `GateResult` scorecard, then discarding them.
6. Emit one standard `Trial` record (diff, gate scorecard, cost native + USD, tokens, all 5 axis ids).
7. `worktree.destroy()`.

The only manual parts in the `manual` runner are: you drive your IDE, and (for Copilot) the cost is read by the standalone calculator. Worktree setup, file placement, the gate, and diff capture are automated identically.

---

## 2. Phasing & ordering

- **Phase 0 — Scaffold & validate the engine.** Build core data model, runner abstraction, `manual` + `oracle` + `nop` runners, the grader and leakage checker. Prove the pipeline on one toy task: `oracle` passes the gate, `nop` fails it. No real measurement yet.
- **Phase 1 — Claude Code surface (the precise surface).** Add the `claude-code` headless runner + cost JSON capture. Author the real tasks (revert + held-out tests + leakage check). Install + freeze the methodology packs. Build the pairwise grading UI. Run the Anthropic model sweep × methodology bake-off on the proxy repos. Grade.
- **Phase 1.5 — Copilot CLI spike (15 min, personal machine, public repo).** Install Copilot CLI, auth with your own token, run one `copilot -p` task, eyeball behavior vs your VS Code agent-mode experience. Outcome selects the Phase-2 runner: `copilot-cli` if representative + permitted, else `manual`.
- **Phase 2 — Copilot surface.** Add the chosen runner + build the standalone usage calculator. Run the work-model matrix on the proxy repos. Prune cells using Phase-1 results.
- **Phase 3 — Research-driven evolution.** A research investigation (P3.0, saved to `docs/research-eval-frameworks.md`) drove a sequence of upgrades, each a reviewed prompt in `prompts/`:
  - **P3.2** — cost refactor (API-rate pricing table, self-report secondary).
  - **P3.3** — split "setup" into Methodology + Repo-Context (5-axis matrix), then **Part 3** generalizes grading to be axis-general (any axis as comparison target, all ids blinded).
  - **P3.4** — three-tier gate scorecard (compile → visible → hidden).
  - **P3.5** — multi-rep sampling + Bradley-Terry ranking + analyzer flags (axis-general).
  - **P3.6** — task-set quality (target the 30–70% discrimination band, difficulty labels, stronger hidden tests).
  - **P3.7** — README rewrite (last, so it describes the actual final system).
- **Phase 3 (orig.) — Work confirmation (minimal, manual).** On the work machine, run the shortlist on the *real* repos with the *real* instructions, in VS Code, by hand. Read credit deltas via the usage calculator. Confirm the proxy ranking holds.
- **Phase 4 — Decision rollup.** Frontier + stakes-based pick.

---

## 3. Definition of Ready (gate before any *measurement* run)

Green-light Phase 1's measurement (and again before the work-confirmation tier) only when all are true:

- [x] Proxy repos cloned; Cosmos augmentation done and **capped at 1–2 aggregates** (AutoMapper replaced with hand-written mappers + per-pair mapping tests).
- [x] Each task authored: feature reverted cleanly, base commit pinned, run command verified.
- [x] Held-out tests extracted **and strengthened** beyond what the original PR shipped (insufficient tests = false-positive merges).
- [x] Leakage check **green** for every task (no dangling references in tree / recent git log / comments).
- [x] Methodology packs installed in each harness's native form and **frozen** (snapshot committed).
- [x] Repo-contexts authored and **frozen**, each tagged with `task_affinity`; `none` control present.
- [x] Instructions-OFF ablation (`baseline` methodology + `none` repo-context) works. *(real baseline/none haiku trials ran 2026-07-02)*
- [x] **Three-tier gate validated** (compile / visible / hidden) — `oracle` → all-pass, `nop` → fails at the first meaningful tier — on every task. *(all 5 tasks on the reproducibly-rebuilt bases: pyvrp via WSL, cosmos via dotnet 8, 2026-07-02)*
- [x] Runner abstraction validated with `manual` + `claude-code`. *(manual: 4 cosmos-B variant trials through the full pipeline; claude-code: 3 billed haiku trials, 2026-07-02)*
- [x] Cost capture validated: token counts priced from `pricing.toml`; Claude self-reported figure parsed as secondary. *(3 billed trials, $1.23 total, token-priced; Copilot calculator deferred with Phase R)*
- [x] Pairwise UI tested with dummy diffs (anonymization confirmed — the grader cannot tell which **value of the comparison axis** a diff came from; every axis id is blinded). *(J1 done 2026-07-02: demo + real data, blinding asserted on served diffs)*
- [x] Matrix driver scripted; full dry run on one task × all methodologies × repo-contexts completed.

---

## 4. Verbatim Claude Code prompts

The ordered build prompts live as one file each in `prompts/` (P0.1 → P3.7). Paste them
into Claude Code in order; each assumes prior steps are done. See `prompts/README.md`
for the order table, declared dependencies, and live status. Pin your CLI version
first (a known `-p` bug shipped in one 2.1.x release):
`npm install -g @anthropic-ai/claude-code@latest`, then record the version in this
repo's README.

---

## 5. Run protocol per surface

**Claude Code (personal, automated).** `setup-bench run --task all --methodology all --repo-context all --model haiku,sonnet,opus --runner claude-code --reps 3`. Fully automated: cost priced from tokens, gate automatic. `--full-matrix` overrides task-affinity filtering. Stagger across the day if you brush rate limits; the driver is resumable. This is your precise surface — the model sweep and methodology bake-off both live here.

**Copilot CLI (personal, automated — if the spike passed).** Same command with `--runner copilot-cli --model <work models>`, `COPILOT_GITHUB_TOKEN` exported. Diffs and gate are automatic; cost is priced from token counts (joined on trial_id). Prune the grid using Phase-1 Claude results so you don't run cells whose ranking is already obvious.

**Manual (work confirmation, minimal).** `setup-bench run --runner manual` prepares each trial (fresh worktree, repo-context + methodology files placed, instruction printed) and waits. You complete the one task in VS Code exactly as you normally work, press Enter; the tool captures the diff and runs the three-tier gate. Bracket the session and feed the token counts to the usage calculator for the credit/USD figure. Keep this tier to the shortlist only — it exists to confirm the proxy ranking holds on real repos with real instructions, nothing more.

**Grading (all surfaces).** Launch the UI, **choose the comparison axis** (default methodology), pick the fixed values for every other axis (the "cell"), and grade blind pairwise over the hidden-gate passers in that cell — advance with the keyboard. Then `setup-bench report`.

---

## 6. How results become the adoption decision

1. **Gate** — the three-tier scorecard removes anything that doesn't pass the strengthened hidden tests — those are simply out. Compile/visible failures are recorded too (cheap signal on where a trial broke).
2. **Blind pairwise** over hidden-gate passers yields, per cell, a direction (which **value of the chosen comparison axis** you'd merge), with multi-rep sampling feeding every rep into the comparison pool.
3. **Bradley-Terry** collapses the pairwise votes into a global ordering with bootstrap confidence intervals — overlapping CIs mark values that are statistically indistinguishable. This replaces the old win-matrix preponderance read; it's still a decision aid, not a significance claim.
4. **Cost** (priced exactly from tokens even at small n) breaks quality ties and draws the frontier.
5. **Stakes rule** turns the frontier into one pick per tier: high-stakes → the quality winner; routine → the cheapest value indistinguishable from it (overlapping CI or better).
6. **Confirm** that pick survives the manual work-repo tier before adopting. Adopt, stay alert, don't carve it in stone — this is a decision aid sized to your downside (a slightly suboptimal setup), not a published benchmark.

---

## 7. Knobs (settled 2026-06-24)

Set during the sync & recalibration session. Values below govern the
shakedown and measurement runs.

| Knob | Value | Note |
|---|---|---|
| Rep count | **3** | per cell; feeds Bradley-Terry |
| `--max-turns` cap per harness | **60** | moderate cost ceiling per trial |
| `custom` methodology | **in scope** | include in methodology sweeps; freeze/vendor at a pinned commit once stable — do not block on it (may not be ready) |
| Default comparison axis | **none — chosen per experiment** | pick the comparison target at grade time; no fixed default |
| Work models (Copilot grid) | **Deferred — Copilot out of scope for now (2026-07-01)** | R0 spike skipped: no Copilot plan on hand, not worth a paid trial now. Revive with prompts 11–13 if a plan becomes available; the Runner axis is otherwise covered by the `manual` runner |
| Final task set + stakes tiers | **to finalize in Phase G** | PyVRP A/B/C + 2 Cosmos tasks; tag each with a stakes tier and mark the deliberately under-specified one when the golden set is frozen |
