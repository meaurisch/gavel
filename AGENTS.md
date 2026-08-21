# Agent guide — gavel

Conventions for ANY coding agent (vendor-neutral). Full standards:
https://github.com/meaurisch/studio/tree/master/conventions

- Entry points: `python tasks.py test | run | check` — never invent others.
- Update README "Current state" / "Next up" when your session changes them.
- If an open issue labeled `runbook` exists here, check whether your work
  affects its steps; tick/edit them in the same session (conventions/runbooks.md).
- Never commit secrets; `.env` is generated, never edited or committed.
- Proposals for this repo follow conventions/proposal-schema.md.
