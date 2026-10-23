# G3b — Research a second Cosmos feature (Chat + Research)

**Service:** Claude Chat + Research.
**Goal:** pick a second, more representative Cosmos feature to revert for the
second Cosmos golden task. Output feeds prompt `06`.

---

Paste to Claude Chat (with Research on):

```
I have a C#/.NET 5 reference repo: "Clean Architecture with partitioned
repository pattern using Azure Cosmos DB" (github: the CleanArchitectureCosmosDB
project). I want to choose ONE realistic, cross-layer feature in it to use as a
benchmark task: I'll revert the feature, and an AI coding agent must reimplement
it, judged by held-out tests.

Research the repo's structure and its real commit/PR history, and recommend a
feature that is:
- cross-layer (touches domain/repository/API, not a one-file change),
- testable with hand-written unit/integration tests that don't require a live
  Azure Cosmos DB (or that can be tested against the in-repo abstractions/mocks),
- realistic of day-to-day work (not a toy),
- different in character from "replace AutoMapper with hand-written mappers"
  (which is already my first task), and
- moderate difficulty (a strong agent passes ~50% of the time).

Deliver:
- Top recommendation + 2 alternates, each with: what the feature is, which files
  it touches, why it's representative, and how it can be tested without live
  Azure.
- Any setup caveats (e.g. does the test project need a Cosmos emulator? can we
  avoid it?).
- The specific commit(s) or code area that implements it, if you can identify it.
```

---

**After Research answers:** decide the feature (yours to pick) and carry the
recommendation into prompt `06`. Note any "no live Azure needed" caveat — it
determines whether the held-out tests can run on your machine.
