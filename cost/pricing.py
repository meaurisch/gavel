from __future__ import annotations

import logging
import tomllib
from dataclasses import dataclass
from pathlib import Path

logger = logging.getLogger(__name__)

_TOML_PATH = Path(__file__).parent / "pricing.toml"


@dataclass
class ModelPricing:
    vendor: str
    input_per_mtok: float
    output_per_mtok: float
    cache_read_per_mtok: float


def load_pricing(
    path: Path = _TOML_PATH,
) -> tuple[dict[str, ModelPricing], dict[str, str]]:
    with open(path, "rb") as f:
        data = tomllib.load(f)

    models: dict[str, ModelPricing] = {}
    for model_id, vals in data.get("models", {}).items():
        models[model_id] = ModelPricing(
            vendor=vals["vendor"],
            input_per_mtok=vals["input_per_mtok"],
            output_per_mtok=vals["output_per_mtok"],
            cache_read_per_mtok=vals.get("cache_read_per_mtok", vals["input_per_mtok"] * 0.1),
        )

    aliases: dict[str, str] = data.get("aliases", {})
    return models, aliases


def save_pricing(
    models: dict[str, ModelPricing],
    aliases: dict[str, str],
    path: Path = _TOML_PATH,
) -> None:
    import tomli_w

    data: dict = {"models": {}, "aliases": aliases}
    for model_id, p in sorted(models.items()):
        data["models"][model_id] = {
            "vendor": p.vendor,
            "input_per_mtok": p.input_per_mtok,
            "output_per_mtok": p.output_per_mtok,
            "cache_read_per_mtok": p.cache_read_per_mtok,
        }

    with open(path, "wb") as f:
        tomli_w.dump(data, f)


_PRICING: dict[str, ModelPricing] | None = None
_ALIASES: dict[str, str] | None = None


def _ensure_loaded() -> tuple[dict[str, ModelPricing], dict[str, str]]:
    global _PRICING, _ALIASES
    if _PRICING is None:
        _PRICING, _ALIASES = load_pricing()
    return _PRICING, _ALIASES


def compute_api_rate_usd(
    model: str,
    input_tokens: int,
    output_tokens: int,
    cache_read_tokens: int,
) -> float | None:
    pricing, aliases = _ensure_loaded()

    p = pricing.get(model)
    if p is None:
        resolved = aliases.get(model)
        if resolved:
            p = pricing.get(resolved)

    if p is None:
        logger.warning("No pricing entry for model %r — falling back to self-reported cost", model)
        return None

    return (
        input_tokens * p.input_per_mtok
        + output_tokens * p.output_per_mtok
        + cache_read_tokens * p.cache_read_per_mtok
    ) / 1_000_000
