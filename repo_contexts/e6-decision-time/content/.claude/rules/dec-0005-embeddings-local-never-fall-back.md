---
paths:
- src/embeddings.ts
- src/semantic-search.ts
---
# [dec-0005-embeddings-local-never-fall-back] A scope's embedding provider is fixed by policy and never falls back

Embedding providers are fixed per scope by policy; a scope configured for a local provider fails loudly when that provider is unavailable and never silently falls back to a hosted one

On embedding-provider failure, fail loudly for that scope and never substitute another provider.

If ignored: Note text silently flows to a provider the scope's privacy policy forbids..
