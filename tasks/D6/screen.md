# D6 — authoring-time derivability screen

Run in `repos/_sources/vault-mcp-server` (upstream clone, fetched first) against
the pinned anchor `b934395a0840fba59bac6767a297cd99a62c48ef`, on 2026-08-26.

The screen answers one question: can the decision D6 measures — hand Claude Code
the *same* guide via a pointer, rather than a second copy — be derived from the
task repo itself? If the anchor tree already spelled the pointer convention out,
D6 would measure reading comprehension, not memory.

## 1. Pointer phrasing must be absent (expected 0)

```
git grep -niE "@AGENTS\.md|pointer[- ]only|CLAUDE\.md.{0,40}one line" b934395a0840fba59bac6767a297cd99a62c48ef -- .
```

Result: **0 hits** (git grep exited 1) — as required.

## 2. `CLAUDE.md rule N` mentions must be exactly 1 (expected 1)

```
git grep -niE "CLAUDE\.md rule [0-9]" b934395a0840fba59bac6767a297cd99a62c48ef -- .
```

Result: **1 hit**, verbatim:

```
b934395a0840fba59bac6767a297cd99a62c48ef:src/vault.ts:291:   * Refuses to touch approved/executed proposals (CLAUDE.md rule 7).
```

Expected file:line — `src/vault.ts:291` — matched exactly.

## 3. `rule N` mentions must be exactly 4 (expected 4)

```
git grep -niE "[Rr]ule [0-9]" b934395a0840fba59bac6767a297cd99a62c48ef -- .
```

Result: **4 hits**, verbatim:

```
b934395a0840fba59bac6767a297cd99a62c48ef:prompts/process-capture.md:53:12. If a working note has an @tag that does not fuzzy-match ANY project in the roster, you MUST treat it as a new project candidate — never route its content to a different existing project. Evaluate it under Rule 3 (substantial content threshold) and place it in `new_projects` if it passes, or `manual_routing` if it does not.
b934395a0840fba59bac6767a297cd99a62c48ef:src/vault.ts:291:   * Refuses to touch approved/executed proposals (CLAUDE.md rule 7).
b934395a0840fba59bac6767a297cd99a62c48ef:src/vault.ts:377:   *  - honors rule 7: never moves a proposal whose status is approved/executed
b934395a0840fba59bac6767a297cd99a62c48ef:src/vault.ts:407:    // Rule 7: never move/clobber an approved or executed proposal.
```

Expected file:line list — `src/vault.ts:291,377,407` and
`prompts/process-capture.md:53` — matched exactly.

## Reading

The anchor tree points *away* from the pointer convention, and does so in a way
that actively tempts the copy route. `src/vault.ts` cites "CLAUDE.md rule 7"
three times over, so the code asserts a CLAUDE.md with numbered rules exists —
but no CLAUDE.md is in the tree, and the numbered rules it names are nowhere
either (the only other `rule N` in the repo is Rule 3 of an unrelated
process-capture prompt). An agent reading only this repo is therefore invited to
*author* a rules file, i.e. a second guide that drifts from AGENTS.md. Nothing
in the tree says CLAUDE.md should instead be a one-line include of AGENTS.md, or
that duplicating the guide is the failure mode to avoid.
