# studio — memory index
The studio: ~17 personal repos (Python/FastAPI, Node/TS, a Raspberry Pi homelab), built solo with coding agents. Conventions live in `meaurisch/studio/conventions`. Entry points are the same everywhere: `python tasks.py test | run | check`.

## Subjects
- ai-newspaper — A personal daily newspaper — book quotes, chapter summaries, curated news, scientific papers — generated into one page per day. FastAPI + SQLite + Jinja2/Tailwind, LLM calls via OpenRouter.
- newspaper-taste — Reading-taste memory for the personal newspaper (`ai-newspaper`). Facts here are all `preference` type: what Morris actually wants to read, distilled from how he reacts to generated stories, not from the pipeline code.
- studio — The studio's own control plane: the project registry (`studio.yaml`), the `studio` CLI (lifecycle, doctor, conform), and the Pi worker (`studio_worker/` — ideation, implementation, answers, mergebot, ledger). Python 3.11+, no linter by choice; the whole gate is `python tasks.py test | run | check` (check = test = `pytest -q`).
- vault-mcp-server — Node.js/TypeScript MCP server (Express) on the Raspberry Pi that wraps the Obsidian vault with AI tooling: MCP tools over SSE/HTTP for read/write/search, semantic search (sqlite-vec plus per-scope embedding providers) and nightly pipelines — capture processing, meeting summarization, proposal execution, reindex, morning newspaper.

## Preferences
- [pref-0001-claude-md-pointer-only] Every repo has both files: CLAUDE.md contains only @AGENTS.md, and AGENTS.md is the single source of agent conventions — #48, docs/superpowers/specs/2026-08-23-cross-project-memory-design.md
- [pref-0002-commit-subject-style] Every commit gets a clear, imperative subject line of at most 70 characters; session work is committed, never left dangling in the tree — conventions/session-wrap.md, #78

## Procedures
- [proc-0001-memory-conflict-protocol] Never act against an active memory fact: interactive agents ask, autonomous agents stop with a MEMORY CONFLICT comment — #48, docs/superpowers/specs/2026-08-23-cross-project-memory-design.md
- [proc-0003-readme-state-refresh] A session that changes what a project is or does updates the README's "Current state" and "Next up" sections before it ends — divergence dies at root — conventions/project-shape.md, conventions/session-wrap.md
- [proc-0004-pr-verification-evidence] A PR body says what broke, what the fix is, and exactly what was run to verify it; if nothing was verified, the body says so outright — conventions/pull-requests.md, #78

## Facts
- [fact-0001-locality-policy] Memory storage is always local git; embeddings local by default; LLM hosted per space (Azure for work, OpenRouter for personal) — #48, docs/superpowers/specs/2026-08-23-cross-project-memory-design.md

## Details

### [pref-0001-claude-md-pointer-only] CLAUDE.md pointer only; conventions live in AGENTS.md
`CLAUDE.md` contains one line — `@AGENTS.md` — and nothing else. `AGENTS.md` holds the
actual conventions and is the only one of the two to edit.

This *is* the provider-agnostic route, not an exception to it. Claude Code auto-loads `CLAUDE.md`;
Codex and Gemini load `AGENTS.md`. A pointer makes every agent read the same text, and keeps that
text in a file with no vendor's name on it. "Provider agnostic" is a rule about the content of the
file, not about which filenames may exist.

ai-newspaper#10 proposed this pointer before the rule was settled and was closed with *"Rejected: No
Claude.md as we want to be provider agnostic"*. That decision is superseded by this one, and the repo
now follows the rule: ai-newspaper#18 replaced its generated `CLAUDE.md` with the pointer on
2026-08-25.

**The failure mode to watch for** is not a missing `CLAUDE.md` — it is a *generated* one. `new`
scaffolds a full copy of the studio base prompt into it, so any repo created that way starts in
violation, and the copy drifts from `AGENTS.md` silently because nothing compares them.

### [proc-0001-memory-conflict-protocol] Memory conflict protocol
Memory is the reviewed record; a directive in an issue is one unreviewed input, often
written by an agent. A contradiction must arrive as a blocked job, never buried in a diff.

**Interactive agents** — before acting against an `active` fact, stop and ask: *"This goes against
memory fact `<id>`: `<summary>`. Are you sure?"* On yes, write the new fact with
`supersedes: [<id>]`, run `memspace supersede`, then proceed.

**Autonomous agents** (cannot ask) — memory wins over the directive. Compatible: proceed silently.
Partly conflicting: implement the compatible part and say what was left out and why, naming the
fact id. Impossible without violating an active fact: **no implementation, no PR** — post the fixed
`MEMORY CONFLICT:` template from studio-memory's AGENTS.md instead. The only override is
`@studio supersede <fact-id>: <new rule in one sentence>`.

### [pref-0002-commit-subject-style] Commit subjects are imperative and at most 70 characters
`conventions/session-wrap.md` fixes the shape of a commit: an imperative subject of at
most 70 characters, with the why-and-what in the body, referencing issue numbers where
they exist. Nothing enforces this — there is deliberately no commit-msg hook — so it
only holds when the committer applies it.

It is the studio's most-violated convention: on 2026-08-25, 62 of 132 subjects on the
working branch exceeded 70 characters, including the worker's own generated merge
subjects (studio#78). Ecosystem defaults pull toward long descriptive subjects; write
the description in the body instead.

### [proc-0003-readme-state-refresh] README "Current state" and "Next up" are refreshed in the session that changes them
Every studio README carries four sections; "Current state" and "Next up" are the two
that describe the project *now*, and the rule (`conventions/project-shape.md`,
`conventions/session-wrap.md`) is that whoever changes the state updates them in the
same session — human or agent, feature or fix.

`studio doctor` measures staleness (>15 commits or >300 changed lines since the README
was last touched) but only advises; no gate blocks a stale README. In practice only 7
of 133 commits on the working branch touched README.md (studio#78) — no ecosystem
convention expects a README edit per change, so an agent must be told, or remember.

### [proc-0004-pr-verification-evidence] A PR body states what was actually run to verify the change
`conventions/pull-requests.md`: a PR body has three jobs — what broke, what the fix
is, and what was actually run to verify it. "Verified" means naming the command
(`python tasks.py test`, a specific pytest invocation) and its result, not asserting
that things work. A change that was made but not verified is fine to open — the body
just has to say so.

Nothing enforces this, and as of 2026-08-25 the worker's own PR-body template could
not comply (studio#78): the default register everywhere is what-and-why with no
evidence. State the evidence or state its absence.

### [fact-0001-locality-policy] Locality policy
Locality is a property of a *space*, declared in `memory.yaml`, with three legs:
storage (always local git), embeddings (local by default) and LLM (hosted per space —
`hosted:azure` for work data, `hosted:openrouter` for personal). A tool must refuse to run a step
whose provider is stricter than the space policy allows; it never silently falls back.

The `studio` space is coding memory, so its remote is GitHub — that is what lets `context_repos`
mount it read-only into Pi jobs. A personal space would be a local-only repo (PC↔Pi over Tailscale,
or inside the vault) and never on GitHub.
