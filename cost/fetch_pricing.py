from __future__ import annotations

import logging

from cost.pricing import ModelPricing

logger = logging.getLogger(__name__)

LITELLM_URL = (
    "https://raw.githubusercontent.com/BerriAI/litellm"
    "/main/model_prices_and_context_window.json"
)

_DEFAULT_VENDORS = {"anthropic", "openai"}


def fetch_litellm_pricing(
    vendors: set[str] = _DEFAULT_VENDORS,
) -> dict[str, ModelPricing]:
    import httpx2

    logger.info("Fetching pricing from %s", LITELLM_URL)
    resp = httpx2.get(LITELLM_URL, timeout=30)
    resp.raise_for_status()
    data: dict = resp.json()

    models: dict[str, ModelPricing] = {}
    for key, entry in data.items():
        if "/" in key:
            continue
        if key.startswith("ft:"):
            continue
        if entry.get("mode") != "chat":
            continue

        provider = entry.get("litellm_provider", "")
        if provider not in vendors:
            continue

        input_cost = entry.get("input_cost_per_token")
        output_cost = entry.get("output_cost_per_token")
        if input_cost is None or output_cost is None:
            continue

        cache_read = entry.get("cache_read_input_token_cost")
        if cache_read is None:
            cache_read = input_cost * 0.1

        models[key] = ModelPricing(
            vendor=provider,
            input_per_mtok=round(input_cost * 1_000_000, 6),
            output_per_mtok=round(output_cost * 1_000_000, 6),
            cache_read_per_mtok=round(cache_read * 1_000_000, 6),
        )

    logger.info("Fetched %d models from LiteLLM (%s)", len(models), ", ".join(vendors))
    return models
