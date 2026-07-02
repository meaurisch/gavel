# Design — "Fable finishes setup-bench": an autonomous deliverable run

**Date:** 2026-07-02
**Author:** brainstormed with Claude (Opus 4.8)
**Status:** design approved in session; pending user review of this doc

## 1. Goal

Run **Claude Fable 5** fully autonomously to take `setup-bench` from its current
(mature but unfinished) state to a **polished, community-ready, push-ready**
open-source tool — with minimal manual involvement, and without ever touching
the user's real working copy.

This is **deliverable-first**: the point is a great final product. Observing
Fable's end-to-end autonomy is the means, not the goal. Where the two conflict,
the product wins.

## 2. Decision log (locked in session)

| Decision | Choice | Why |
|---|---|---|
| North star | **Deliverable-first** | A shippable setup-bench is the objective; Fable is the means. |
| Brief curation | **Curated + explicit license to improve** | Aim Fable's autonomy at the *open* problems, not re-deriving the 204-test solved core. |
| Working style | **Fable-led; subagents optional at its discretion** | Truest test of Fable's judgment and usually the best deliverable; override CLAUDE.md's conductor/executor mandate for this run. |
| Environment | **Clean room** (isolated config) **+ curated project facts + browser** | Strip workflow scaffolding (superpowers, studio agents/skills, MCP, conductor mandate) that would fight Fable's autonomy and its documented anti-overplanning design; keep only project knowledge Fable needs. |
| Run scope | **Real sweeps allowed but minimized** | An unproven harness isn't proven; but paid runs draw the same subscription pool that funds Fable. Cheapest model (haiku), fewest runs; free oracle/nop for the rest. |
| Sweep cap | **Soft "minimize", Fable decides the size** | Trust Fable's judgment; it justifies the footprint in its report. |
| Checkpoints | **One plan gate, then hands-off** | Single manual touch buys large drift-risk reduction; deliverable-first. |
| Git handoff | **Fable prepares, user pushes** | "Uploadable immediately" without publishing unreviewed work. |
| Session type | **Interactive TUI** | Watchable, natural plan gate, can eyeball the UI, easy stall recovery. |
| Permissions | **Bypass, inside the isolated clone** | Required for genuine hands-off; safe because it's a throwaway clone with a don't-touch-backup guardrail and no access to global config. |
| Effort | **`high` default, `xhigh` for the planning turn** | Best quality-per-token over a multi-hour run; deep-think the plan once. |
| Plan tier | **Max** (user upgrading) | Removes ~90% of Pro's fragility (5h-window fragmentation + weekly-cap hard stalls + long-alive-session resume-wipe risk). |

## 3. Fable 5 facts that shaped the design

- Anthropic's most capable released model; specific leap in **long-horizon
  autonomy** (multi-day goal-directed runs, strong instruction retention).
- **Effort** is the primary intelligence/latency/cost dial; docs default **high**,
  **xhigh** for the most capability-sensitive work.
- Documented failure mode is **overplanning**: "When you have enough information
  to act, act." → we must NOT bury it under process scaffolding that forces
  planning ritual.
- Individual requests can run many minutes; autonomous runs, hours.
- Sources: [Anthropic launch](https://www.anthropic.com/news/claude-fable-5-mythos-5),
  [Prompting Fable 5](https://platform.claude.com/docs/en/build-with-claude/prompt-engineering/prompting-claude-fable-5),
  [Models overview](https://platform.claude.com/docs/en/about-claude/models/overview).

## 4. Architecture: isolation & clean room

### 4.1 Backup (user's code untouchable by construction)
- Commit/stash the working tree, then **annotated tag** on `main`:
  `fable-baseline-2026-07-02`.
- Fable works in a **separate full clone** at a sibling path
  (`C:\Users\norri\studio\setup-bench-fable`), branch `fable-run`. A clone (not a
  worktree) shares no state with the original.
- **Remove the clone's `origin` remote** so nothing can ever be pushed back into
  the real repo.
- The original `setup-bench\` dir stays closed during the run. Two independent
  backups: the untouched dir + the tag.

### 4.2 Clean room (Fable, not the scaffolding)
- Launch with **`CLAUDE_CONFIG_DIR` = a fresh dir** (`C:\Users\norri\.claude-fable`).
  Fresh config ⇒ no superpowers plugin, no studio agents/skills, no hooks, no
  MCP servers load. Nothing leaks in from or out to the real `~/.claude`.
  - First launch there triggers one-time onboarding: workspace-trust prompt,
    theme, and **OAuth login with the Max account**. Expected, ~1 min.
  - `--bare` would also strip scaffolding but forces API-key auth (no OAuth), so
    it is **incompatible** with subscription login — do not use it.
- In the clone, **neutralize workflow scaffolding**: replace root `CLAUDE.md`
  with a lean, facts-only brief (below); check for any repo-level `.claude/` that
  would auto-inject agents and move it aside for the run. Keep copies; Fable
  finalizes docs at the end.
- **Browser (added back on purpose):** the brief authorizes Fable to install and
  drive **Playwright (Python)** to open the grading UI and capture screenshots
  (self-contained, no extension setup). `--chrome` is an optional turnkey
  alternative if the user already has the Chrome integration configured.

### 4.3 Lean `CLAUDE.md` for the clone (facts only, no scaffolding)
```markdown
# setup-bench — project facts

- Local-first decision-support tool comparing agentic coding setups across five
  axes (task × methodology × repo-context × model × runner), with a three-tier
  gate, blind pairwise grading, and Bradley-Terry ranking. See README.md and
  IMPLEMENTATION_PLAN.md for the full design — they are the MINIMUM spec.
- Windows + PowerShell primary. `tasks.ps1` is the interface (Run, Watch, ...).
- Python venv at `.venv`; tests via `pytest`.
- PyVRP tasks build/test under WSL (Ubuntu); .NET/cosmos tasks need the dotnet
  SDK. The gate auto-dispatches PyVRP into WSL.
- You are in an isolated clone on branch `fable-run`. There is no git remote;
  do not add one and do not push. Commit locally, early and often.
```

## 5. The brief Fable receives (verbatim, paste-ready)

> You are Fable 5, working fully autonomously to finish and elevate this project
> — **setup-bench** — into a polished, community-ready open-source tool. You are
> the sole driver. You may spawn subagents at your own discretion for parallel or
> grunt work, but you own the outcome.
>
> **CONTEXT**
> - setup-bench is a local-first decision-support tool for comparing agentic
>   coding setups (task × methodology × repo-context × model × runner), with a
>   three-tier gate, blind pairwise grading, and Bradley-Terry ranking. Read
>   `README.md` and `IMPLEMENTATION_PLAN.md` first — they, with `docs/` and
>   `recalibration_prompts/`, define the MINIMUM requirements, not the ceiling.
> - The pipeline is already built and largely tested (~204 tests). This is a
>   finishing-and-elevating job, **not a rewrite**. Do not rewrite subsystems
>   that already work and pass their tests without a concrete, tested reason.
>
> **ENVIRONMENT & FACTS**
> - Windows + PowerShell primary. `tasks.ps1` is the interface.
> - PyVRP tasks require WSL (Ubuntu); .NET/cosmos tasks require the dotnet SDK.
>   The gate auto-dispatches PyVRP builds into WSL. You may use these for real
>   runs — but see BUDGET.
> - Python venv at `.venv`; tests via `pytest`.
> - You are in an isolated clone on branch `fable-run`. The user's real repo is
>   untouched elsewhere and off-limits. There is NO git remote; do NOT add one
>   and do NOT push. Commit locally, early and often.
>
> **YOUR MANDATE (deliverable-first)**
> 1. **Meet the floor:** everything the README/IMPLEMENTATION_PLAN/docs specify as
>    intended must actually work.
> 2. **Close the known gaps** (verify against the current repo; this is a floor):
>    - The `report` command is a stub — build it for real (surface the analyzer's
>      quality/cost/Pareto story).
>    - No Pareto frontier visualization (quality vs. cost) — add it.
>    - The grading UI shakedown is blocked on gradeable data — unblock it and
>      exercise the pairwise UI end-to-end.
>    - Fix the `cli.py` run-summary cost under-reporting bug for errored-but-billed
>      trials (see `recalibration_prompts/27-*.md`) and sweep for sibling bugs.
>    - Broaden the task suite where it strengthens the product.
> 3. **Elevate it:** you are explicitly authorized and encouraged to find the
>    project's real weaknesses and fix them — UX, performance, docs, developer
>    experience, missing features — to the standard of a tool that would genuinely
>    be a hit in the community for its usefulness and user-friendliness. Use
>    judgment; avoid gold-plating that doesn't serve a real user.
>
> **BUDGET & REAL RUNS (important)**
> - Running real trials spends the user's Claude subscription usage — the SAME
>   pool that funds you. Every token spent on a sweep is a token you can't spend
>   building. So **minimize paid runs.** Use the FREE `oracle`/`nop` runners and
>   synthetic/fixture data to validate the pipeline and to populate the grading UI
>   wherever real hidden-gate passers are scarce. When you need authenticity, run
>   the SMALLEST real sweep that genuinely proves the runner→gate→grade→rank path,
>   using the CHEAPEST sufficient model (**haiku**). You decide the exact size;
>   keep it minimal and justify it briefly in your report.
>
> **VERIFICATION — prove it works three ways**
> - **Programmatically:** full test suite green, plus new tests for everything you
>   add or fix. `tasks.ps1 Run`/`Watch` work.
> - **Functionally:** the CLI runs end-to-end; at least one minimal real haiku
>   sweep completes through the whole pipeline; the grading UI launches and is
>   usable.
> - **Visually:** actually launch the grading UI and LOOK at it — you are
>   authorized to install and drive **Playwright (Python)** to open it and capture
>   screenshots; inspect them and fix what looks broken or unpolished. Save
>   screenshots into the repo (e.g. `docs/screenshots/`) as evidence.
>
> **WORKING STYLE**
> - When you have enough information to act, act. Do not overplan.
> - Commit early and often with clear messages; clean, readable history is part of
>   the deliverable.
> - Keep the README's required sections accurate (What it is / How to run it /
>   Current state / Next up) and update all docs to the true final state.
>
> **PHASE 1 — PLAN, THEN STOP (single checkpoint)**
> Before building, produce and COMMIT a concise plan doc (e.g. `docs/fable-plan.md`)
> with: (a) your gap analysis of the current repo, (b) the concrete, ordered work
> you intend to do, (c) your acceptance criteria / definition of done, (d) your
> intended real-sweep size and why. Then STOP and wait for my approval. Do not
> start implementing until I reply "approved" (I may request changes first).
>
> **PHASE 2 — BUILD TO DONE (hands-off)**
> On "approved," execute your plan to completion autonomously. Do not stop for
> check-ins unless you hit something genuinely blocking, irreversible, or
> ambiguous in a way that risks the deliverable — then stop and ask. Otherwise,
> run to done.
>
> **DEFINITION OF DONE**
> - All acceptance criteria met and self-verified (tests green, functional proof,
>   visual proof).
> - Repo clean and PUSH-READY: polished README/quickstart, no dead stubs, no
>   secrets, sensible history. Do NOT push — leave it for me.
> - End with a short report: what you changed and why, what you deliberately left
>   out, what you'd do next, and the real-sweep footprint you used.
>
> **GUARDRAILS**
> - Work only in this clone. Never touch anything outside it. Never add a git
>   remote or push. Never modify global Claude config. Never commit secrets or
>   `.env`. If blocked, stop and report rather than thrashing.

## 6. Exact run procedure (paste-and-run)

**Step 0 — from the real repo, snapshot the baseline** (PowerShell):
```powershell
cd C:\Users\norri\studio\setup-bench
git add -A
git commit -m "session: checkpoint before Fable run"   # if the tree is dirty
git tag -a fable-baseline-2026-07-02 -m "Baseline before autonomous Fable run"
```

**Step 1 — clone to a sibling dir, cut the branch, sever the remote:**
```powershell
git clone C:\Users\norri\studio\setup-bench C:\Users\norri\studio\setup-bench-fable
cd C:\Users\norri\studio\setup-bench-fable
git checkout -b fable-run
git remote remove origin
```

**Step 2 — install the lean CLAUDE.md into the clone** (replace root `CLAUDE.md`
with the §4.3 content; keep the original as `CLAUDE.studio.md` for reference).
Check for a repo-root `.claude/` agents dir and move it aside if present.

**Step 3 — launch Fable in the clean room** (same shell keeps the env var):
```powershell
$env:CLAUDE_CONFIG_DIR = "C:\Users\norri\.claude-fable"
cd C:\Users\norri\studio\setup-bench-fable
claude --model claude-fable-5 --effort xhigh --dangerously-skip-permissions --name "fable-setup-bench"
```
- First launch: accept workspace trust, pick a theme, log in with the Max account.
- `--effort xhigh` for the planning turn; after approving the plan, drop to
  `high` in-session (via the effort control / `/model`) for the long build.
- Optional browser: add `--chrome` if the Chrome integration is already set up;
  otherwise Fable self-installs Playwright per the brief.

**Step 4 — paste the §5 brief** as the first message.

**Step 5 — plan gate:** Fable commits `docs/fable-plan.md` and stops. Review it.
Reply `approved` (or request changes first). Then set effort to `high`.

**Step 6 — hands-off:** let it run. On Max, babysitting should be rare; if a
usage limit hits, keep the TUI alive and type `continue` after reset.

**Step 7 — final review & push:** review the result and Fable's report, then push
yourself when satisfied.

## 7. Acceptance criteria (definition of done)

- Full test suite green + new tests for new/changed code; `tasks.ps1 Run`/`Watch`
  work.
- Known gaps closed: real `report` command, Pareto viz, grading UI exercised on
  real+oracle data, prompt-27 cost-summary bug fixed.
- Functional proof: CLI runs end-to-end; ≥1 minimal real haiku sweep completes
  the whole pipeline; grading UI launches and is usable.
- Visual proof: grading UI screenshotted via Playwright, inspected, polished;
  screenshots committed.
- README/docs reflect the true final state; repo clean, push-ready,
  community-quality (clear quickstart, no dead stubs, no secrets).
- Fable's closing report: what changed & why, deliberate omissions, next steps,
  real-sweep footprint.

## 8. Risks & mitigations

| Risk | Mitigation |
|---|---|
| Resume-wipe if a long-alive session dies | Max (fewer/shorter stalls) + brief mandates commit early/often; work is recoverable from git. |
| Fable rewrites working subsystems (scope drift) | Brief: "finishing, not a rewrite; don't rewrite passing subsystems without a tested reason"; plan gate catches it early. |
| Paid sweeps drain the shared pool | Brief frames sweep tokens as build tokens; haiku only; free oracle/nop for UI data; Fable justifies footprint. |
| Scaffolding forces overplanning | Clean room strips superpowers/hooks; brief says act when you have enough info. |
| Accidental push into real repo | `git remote remove origin` in the clone + guardrail. |
| Global config contamination | Isolated `CLAUDE_CONFIG_DIR`; nothing reads/writes real `~/.claude`. |

## 9. Notes / open items

- `--max-budget-usd` is `--print`-only, so no hard dollar cap in interactive mode;
  rely on subscription limits + the soft-minimize brief.
- Exact in-session effort-switch command may vary by Claude Code version
  (2.1.185); if `/effort` isn't present, set it via `/model`.
- The clone's final `CLAUDE.md` is studio-specific; Fable may rewrite it for a
  community audience as part of doc polish (acceptable).
```
