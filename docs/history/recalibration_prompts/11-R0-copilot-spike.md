# R0 — Copilot CLI spike (HUMAN action + Claude Code prep)

**Service:** Claude Code preps; **YOU** run the spike and make the call.
**Goal:** the Phase-1.5 decision gate — is the Copilot CLI surface representative
of your real VS Code agent-mode workflow, and permitted? This decides whether we
build P2.1/P2.2 at all and which work models go in the grid.

---

### Step 1 — Claude Code prepares a throwaway worktree. Paste to Claude Code:

```
Prepare a one-off Copilot spike. Create a fresh git worktree of repos/cosmos at
the cosmos-A base commit (reuse core/worktree.py logic or just `git worktree
add`), lay down the baseline methodology + none repo-context (i.e. nothing), and
print: (a) the absolute worktree path, (b) the exact cosmos-A instruction text,
(c) the exact command I should run, filled in:
   copilot -p "<cosmos-A instruction>" -s --no-ask-user --model <work_model> --allow-tool='write, shell'
Do not run copilot yourself. Leave the worktree in place and tell me how to
remove it afterward.
```

### Step 2 — YOU run the spike (needs `COPILOT_GITHUB_TOKEN` in `.env`)

In a terminal, `cd` into the printed worktree path and run the printed `copilot`
command (pick a real work model, e.g. a GPT-5.x / Codex model you have access
to). Watch how it behaves.

### Step 3 — YOU judge (the decision)

Compare to how Copilot behaves inside VS Code agent-mode for the same kind of
task. Decide:
- **Representative?** Does headless `copilot -p` produce work comparable to your
  real agent-mode experience?
- **Permitted?** Are you allowed to use it this way (token/account terms)?
- **Which work models** are available and worth putting in the grid?

### Step 4 — Record the outcome. Paste to Claude Code:

```
Copilot spike outcome: <PASS or FAIL>.
- Representative: <yes/no + one line>
- Permitted: <yes/no>
- Work models to use: <list, or n/a>

If PASS: record the work models into IMPLEMENTATION_PLAN.md §7 (work-models row)
and proceed to prompt 12 (build P2.1/P2.2). If FAIL: update §7 to note Copilot
is out of scope; the `manual` runner covers that surface. Either way, remove the
spike worktree and tick R0 in docs/superpowers/recalibration-checklist.md.
```

---

**Branch:** if PASS → continue to `12-R1-build-copilot.md`. If FAIL → skip 12 &
13; the Runner axis is exercised with the `manual` runner instead (note it and
go to Phase J, prompt `14`).
