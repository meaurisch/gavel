# D4 — authoring-time derivability screen

Run in `repos/_sources/ai-newspaper` (upstream clone, fetched first) against the
pinned anchor `1252280ac94ac21dc7927e7da594db1f1d71d66f`, on 2026-08-26.

The screen answers one question: can the decision recorded in
`dec-0004-per-stage-paid-models` be derived from the task repo itself? If the
anchor tree already spelled the decision out, D4 would measure reading
comprehension, not memory.

## 1. Decision phrasing must be absent (expected 0)

```
git grep -niE "llm\.models|per-stage|per stage|decision (to take )?with Morris|not a version bump|free[- ]tier only" 1252280ac94ac21dc7927e7da594db1f1d71d66f -- . | wc -l
```

Result: **0** — as required.

## 2. Model-id mentions must be exactly the known 8 (expected 8)

```
git grep -niE "anthropic/claude-sonnet|:free" 1252280ac94ac21dc7927e7da594db1f1d71d66f -- .
```

Result: **8 hits**, verbatim:

```
1252280ac94ac21dc7927e7da594db1f1d71d66f:PROMPT.md:28:model: "meta-llama/llama-3.3-70b-instruct:free"
1252280ac94ac21dc7927e7da594db1f1d71d66f:PROMPT.md:31:The `:free` suffix is required for zero-cost access. Rate limits are ~20 requests/minute, 200/day. The content quality doesn't matter for testing — what matters is that the correct API calls are made, the correct prompts are sent, and the results are properly processed and stored.
1252280ac94ac21dc7927e7da594db1f1d71d66f:PROMPT.md:37:  model: "meta-llama/llama-3.3-70b-instruct:free"
1252280ac94ac21dc7927e7da594db1f1d71d66f:PROMPT.md:628:- The free model `meta-llama/llama-3.3-70b-instruct:free` should be used
1252280ac94ac21dc7927e7da594db1f1d71d66f:config.yaml:66:  model: "xiaomi/mimo-v2-flash:free"
1252280ac94ac21dc7927e7da594db1f1d71d66f:src/utils/llm_client.py:59:            model: Model identifier (e.g., "anthropic/claude-sonnet-4-20250514")
1252280ac94ac21dc7927e7da594db1f1d71d66f:tests/integration/utils/test_llm_client_integration.py:57:        model="xiaomi/mimo-v2-flash:free"
1252280ac94ac21dc7927e7da594db1f1d71d66f:tests/integration/utils/test_llm_client_integration.py:67:        model="xiaomi/mimo-v2-flash:free"
```

Expected file:line list — matched exactly:
`PROMPT.md:28,31,37,628`, `config.yaml:66`, `src/utils/llm_client.py:59`,
`tests/integration/utils/test_llm_client_integration.py:57,67`.

## Reading

The anchor tree points *away* from the decision: PROMPT.md still asserts a
free-tier-only rule and `llm_client.py` names a Sonnet id only as a docstring
example. Nothing in it says model ids live per stage under `llm.models`, or
that swapping one is a decision rather than a bump. The D4 fixture added on top
(`tests/fixtures/openrouter-models.json`) is model ids and nothing else, so it
adds no phrasing either.
