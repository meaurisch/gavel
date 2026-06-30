from __future__ import annotations

import json
import logging
from dataclasses import field
from typing import Any

from pydantic.dataclasses import dataclass

logger = logging.getLogger(__name__)


@dataclass
class ClaudeUsageResult:
    total_cost_usd: float
    input_tokens: int
    output_tokens: int
    cache_read_tokens: int
    result_text: str
    is_error: bool
    error_message: str = ""
    raw_model_usage: dict[str, Any] = field(default_factory=dict)


class ClaudeUsageParseError(Exception):
    pass


def parse_claude_output(raw: str | dict[str, Any]) -> ClaudeUsageResult:
    if isinstance(raw, str):
        try:
            data = json.loads(raw)
        except (json.JSONDecodeError, ValueError) as e:
            raise ClaudeUsageParseError(f"Invalid JSON: {e}") from e
    else:
        data = raw

    if "total_cost_usd" not in data:
        raise ClaudeUsageParseError("Missing total_cost_usd field")

    total_cost_usd = float(data["total_cost_usd"])

    # Token counts: prefer the per-model `modelUsage` aggregate when it carries
    # real tokens. In a run that delegates to subagents (Task tool), the top-level
    # `usage` reports only the orchestrator's final message (~0 tokens) while the
    # true totals — including every subagent model — live in `modelUsage`. Falling
    # back to `modelUsage` only when `usage` was absent (the old behavior) silently
    # dropped all delegated work, recording 0 tokens and $0 cost.
    #
    # Note the shape differs: top-level `usage` uses snake_case keys, but
    # `modelUsage` entries use camelCase (verified against captured CLI output).
    usage = data.get("usage") or {}
    model_usage = data.get("modelUsage", {})

    mu_input = sum(v.get("inputTokens", 0) for v in model_usage.values())
    mu_output = sum(v.get("outputTokens", 0) for v in model_usage.values())
    mu_cache = sum(v.get("cacheReadInputTokens", 0) for v in model_usage.values())

    if mu_input or mu_output or mu_cache:
        input_tokens = mu_input
        output_tokens = mu_output
        cache_read_tokens = mu_cache
    else:
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cache_read_tokens = usage.get("cache_read_input_tokens", 0)

    result_text = data.get("result") or ""

    # Detect error states
    is_error = bool(data.get("is_error"))
    error_message = ""
    if "error" in data:
        is_error = True
        error_message = str(data["error"])

    # Detect empty-result-with-tokens
    if not result_text and input_tokens > 0 and not is_error:
        is_error = True
        error_message = "Empty result but tokens were billed"

    return ClaudeUsageResult(
        total_cost_usd=total_cost_usd,
        input_tokens=input_tokens,
        output_tokens=output_tokens,
        cache_read_tokens=cache_read_tokens,
        result_text=result_text,
        is_error=is_error,
        error_message=error_message,
        raw_model_usage=model_usage,
    )
