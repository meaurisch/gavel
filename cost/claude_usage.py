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

    # Extract tokens from usage or fall back to modelUsage
    usage = data.get("usage")
    model_usage = data.get("modelUsage", {})

    if usage:
        input_tokens = usage.get("input_tokens", 0)
        output_tokens = usage.get("output_tokens", 0)
        cache_read_tokens = usage.get("cache_read_input_tokens", 0)
    elif model_usage:
        input_tokens = sum(v.get("input_tokens", 0) for v in model_usage.values())
        output_tokens = sum(v.get("output_tokens", 0) for v in model_usage.values())
        cache_read_tokens = sum(v.get("cache_read_input_tokens", 0) for v in model_usage.values())
    else:
        input_tokens = 0
        output_tokens = 0
        cache_read_tokens = 0

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
