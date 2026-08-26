---
paths:
- config.yaml
---
# [dec-0004-per-stage-paid-models] Per-stage paid models via OpenRouter

News pipeline uses paid per-stage models (cluster/writer/editor) configured in config.yaml llm.models; prose quality is the product, model choice is still a decision not a bump

Read a stage's model id only from `config.yaml` `llm.models`; swapping a stage's model or adding a stage is a decision to take with Morris, never a routine bump.
