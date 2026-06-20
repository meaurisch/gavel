# .claude

This directory is intentionally light. Studio's AI enhancement layer lives globally:

- **Skills** at `~/.claude/skills/` — lazy-loaded procedural playbooks
  (`studio-debug`, `studio-ship`, `studio-pi-deploy`, `studio-learn`,
  `studio-session-wrap`)
- **Subagents** at `~/.claude/agents/` — `studio-conductor` (Opus 4.6) and
  `studio-executor` (Sonnet 4.6)

This project is in **agent mode**: route non-trivial requests through `studio-conductor` then `studio-executor`. See `_prompts/agent-mode.md` for routing rules.

To override or add project-specific skills, drop `skills/<name>/SKILL.md` files
in this directory — Claude Code will prefer project-local skills over global ones.

To refresh this file after editing `.studio.json`, run `update-prompts`.
