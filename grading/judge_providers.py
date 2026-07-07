"""Judge providers — the LLM backends the judge orchestration can call.

Each provider turns one prompt into one completion plus usage numbers. The
seam is deliberately tiny (``complete`` + ``availability``) so new backends
(an Anthropic API key provider, an Ollama provider, ...) stay one class each.

Billing classes drive the UI's spend messaging:
- ``subscription`` — zero marginal dollars, but burns the plan's quota
  (claude CLI under a Pro/Max login).
- ``metered``      — may bill real money or count against a paid org tier
  (GitHub Models).
- ``free``         — no external calls at all (the deterministic mock).
"""

from __future__ import annotations

import hashlib
import json
import logging
import os
import re
import shutil
import subprocess
import time
import urllib.error
import urllib.request
from dataclasses import dataclass, field
from pathlib import Path

logger = logging.getLogger(__name__)


@dataclass
class ProviderResult:
    text: str
    input_tokens: int = 0
    output_tokens: int = 0
    usd_equiv: float | None = None
    wall_seconds: float = 0.0


class JudgeProviderError(Exception):
    """The provider failed to produce a completion (transport/auth/timeout)."""


# ---------------------------------------------------------------------------
# mock — deterministic, zero spend, powers tests / demo / Playwright
# ---------------------------------------------------------------------------

# The mock reads the two diff sections straight out of the judge prompt; these
# markers are the contract with grading.judge.build_prompt.
SIDE_A_RE = re.compile(r"=== SOLUTION A DIFF ===\n(.*?)\n=== END SOLUTION A ===", re.DOTALL)
SIDE_B_RE = re.compile(r"=== SOLUTION B DIFF ===\n(.*?)\n=== END SOLUTION B ===", re.DOTALL)


class MockJudgeProvider:
    """Deterministic content-based verdict, no network, no spend.

    The winner is chosen by comparing digests of the two diffs, so the same
    pair of solutions always gets the same winner regardless of which side is
    labeled A — which makes double-pass runs position-consistent, exactly the
    behavior the progress UI's consistency stat should show on demo data.
    """

    id = "mock"
    label = "Mock judge (deterministic, zero spend)"
    billing = "free"

    # Plan-estimate constants (see plan_judge): the mock answers with a
    # fixed ~80-token verdict and wraps the prompt in nothing.
    EST_OUTPUT_TOKENS_PER_CALL = 80
    EST_PROMPT_OVERHEAD_TOKENS = 0

    def models(self) -> list[str]:
        return ["mock-judge"]

    def default_model(self) -> str:
        return "mock-judge"

    def availability(self) -> tuple[bool, str | None]:
        return True, None

    def complete(self, prompt: str, model: str) -> ProviderResult:
        a = SIDE_A_RE.search(prompt)
        b = SIDE_B_RE.search(prompt)
        if a and b:
            da = hashlib.sha256(a.group(1).strip().encode()).hexdigest()
            db = hashlib.sha256(b.group(1).strip().encode()).hexdigest()
            if da == db:
                choice = "tie"
            else:
                choice = "A" if da < db else "B"
        else:
            choice = "tie"
        verdict = {
            "rubric": {
                "correctness": choice,
                "minimality": "tie",
                "readability": choice,
                "overengineering": "tie",
            },
            "choice": choice,
            "confidence": 0.5 if choice == "tie" else 0.75,
            "rationale": (
                "[mock judge] Deterministic verdict for pipeline testing — "
                "derived from a content digest of the two anonymized diffs, "
                "not from real code understanding."
            ),
        }
        return ProviderResult(
            text=json.dumps(verdict),
            input_tokens=len(prompt) // 4,
            output_tokens=80,
            usd_equiv=0.0,
        )


# ---------------------------------------------------------------------------
# claude-cli — the user's Claude subscription via the installed claude CLI
# ---------------------------------------------------------------------------

class ClaudeCliJudgeProvider:
    """Judge via ``claude -p`` — inherits whatever login the user's CLI has
    (a Pro/Max subscription needs no API key). The prompt goes on stdin for
    the same reason the runner does it: the Windows claude.CMD shim truncates
    multi-line argv. Judging is a pure text task, so the CLI runs in an empty
    scratch directory with no repo to read.
    """

    id = "claude-cli"
    label = "Claude (your claude CLI login / subscription)"
    billing = "subscription"

    # Judge calls are single completions; 10 minutes is generous.
    TIMEOUT_SECONDS = 600

    # Plan-estimate constants, measured on the real cosmos-B judge run +
    # a probe call (2026-07-07): the CLI wraps every call in ~24k
    # prompt-side tokens of its own (system prompt; mostly cache-priced),
    # and verdicts run ~2.7k output tokens because thinking counts as
    # output. The old generic 400-token guess understated spend >6x.
    EST_OUTPUT_TOKENS_PER_CALL = 2_700
    EST_PROMPT_OVERHEAD_TOKENS = 24_000

    def __init__(self, workdir: Path | None = None) -> None:
        self._workdir = workdir

    def models(self) -> list[str]:
        # Priced Claude models from the project's own pricing table, so the
        # picker and the cost estimate can never disagree.
        try:
            from cost.pricing import load_pricing
            table, _aliases = load_pricing()
            claude = sorted(m for m in table if m.startswith("claude-"))
            if claude:
                return claude
        except Exception:  # pragma: no cover - pricing table optional
            pass
        return ["claude-haiku-4-5", "claude-sonnet-4-6", "claude-opus-4-8"]

    def default_model(self) -> str:
        models = self.models()
        for preferred in ("claude-sonnet-4-6", "claude-haiku-4-5"):
            if preferred in models:
                return preferred
        return models[0]

    def availability(self) -> tuple[bool, str | None]:
        if shutil.which("claude") is None:
            return False, "claude CLI not found on PATH"
        return True, None

    def _scratch_dir(self) -> Path:
        if self._workdir is not None:
            self._workdir.mkdir(parents=True, exist_ok=True)
            return self._workdir
        import tempfile
        d = Path(tempfile.gettempdir()) / "gavel-judge"
        d.mkdir(parents=True, exist_ok=True)
        return d

    def complete(self, prompt: str, model: str) -> ProviderResult:
        claude_bin = shutil.which("claude")
        if claude_bin is None:
            raise JudgeProviderError("claude CLI not found on PATH")

        cmd = [
            claude_bin,
            "-p",
            "--output-format", "json",
            "--model", model,
            "--max-turns", "1",
        ]
        start = time.monotonic()
        try:
            proc = subprocess.run(
                cmd,
                cwd=str(self._scratch_dir()),
                input=prompt,
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="ignore",
                timeout=self.TIMEOUT_SECONDS,
            )
        except subprocess.TimeoutExpired as exc:
            raise JudgeProviderError(
                f"claude CLI timed out after {self.TIMEOUT_SECONDS}s"
            ) from exc
        wall = time.monotonic() - start

        from cost.claude_usage import ClaudeUsageParseError, parse_claude_output
        try:
            usage = parse_claude_output(proc.stdout)
        except ClaudeUsageParseError as exc:
            raise JudgeProviderError(
                f"could not parse claude CLI output (exit={proc.returncode}): "
                f"{exc}; stderr={proc.stderr[:300]!r}"
            ) from exc

        if usage.is_error:
            raise JudgeProviderError(
                f"claude CLI reported an error: {usage.error_message or 'unknown'}"
            )

        # The CLI's own cost figure knows the cache-write premia; recomputing
        # from tokens under-reported the real cosmos-B run (measured
        # 2026-07-07). Recompute only when the CLI gives no number.
        usd = usage.total_cost_usd or None
        if usd is None:
            try:
                from cost.pricing import compute_api_rate_usd
                usd = compute_api_rate_usd(
                    model, usage.input_tokens, usage.output_tokens, usage.cache_read_tokens
                ) or None
            except Exception:  # pragma: no cover - pricing optional
                pass

        return ProviderResult(
            text=usage.result_text or "",
            # A one-shot `claude -p` call parks the prompt in cache_creation
            # (+ CLI system prompt in cache_read): input_tokens alone reads
            # ~10 for a 30k-char prompt. Report the whole prompt side.
            input_tokens=(usage.input_tokens + usage.cache_read_tokens
                          + usage.cache_creation_tokens),
            output_tokens=usage.output_tokens,
            usd_equiv=usd,
            wall_seconds=wall,
        )


# ---------------------------------------------------------------------------
# gh-models — GitHub Models inference (free tier + org/enterprise paid tier)
# ---------------------------------------------------------------------------

GH_MODELS_URL = "https://models.github.ai/inference/chat/completions"

# A small curated set; the endpoint accepts any catalog id the account can use.
GH_DEFAULT_MODELS = [
    "openai/gpt-4o-mini",
    "openai/gpt-4o",
    "openai/gpt-4.1-mini",
    "meta/llama-3.3-70b-instruct",
]


class GhModelsJudgeProvider:
    """Judge via the GitHub Models REST API (OpenAI-compatible).

    Auth is any GitHub token: ``GITHUB_TOKEN``/``GH_TOKEN`` env vars, else
    ``gh auth token``. The free tier works on any GitHub account;
    organizations and enterprises can enable the paid tier for higher limits
    — same endpoint, same code path, which is what makes gavel extensible to
    a GitHub (enterprise) subscription.
    """

    id = "gh-models"
    label = "GitHub Models (GitHub account / org / enterprise)"
    billing = "metered"

    TIMEOUT_SECONDS = 180

    # Plan-estimate constants: a bare chat-completions call has no wrapper
    # overhead, and non-thinking replies stay near the asked-for verdict.
    EST_OUTPUT_TOKENS_PER_CALL = 400
    EST_PROMPT_OVERHEAD_TOKENS = 0

    # `gh auth token` is a subprocess; availability() runs on every provider
    # listing and plan refresh, so cache the lookup briefly (class-level: the
    # provider is re-instantiated per request).
    _TOKEN_TTL_SECONDS = 300
    _token_cache: tuple[float, str | None] | None = None

    def models(self) -> list[str]:
        return list(GH_DEFAULT_MODELS)

    def default_model(self) -> str:
        return GH_DEFAULT_MODELS[0]

    def _token(self) -> str | None:
        for var in ("GITHUB_TOKEN", "GH_TOKEN"):
            if os.environ.get(var):
                return os.environ[var]
        cached = GhModelsJudgeProvider._token_cache
        if cached is not None and time.monotonic() - cached[0] < self._TOKEN_TTL_SECONDS:
            return cached[1]
        token: str | None = None
        gh = shutil.which("gh")
        if gh:
            try:
                proc = subprocess.run(
                    [gh, "auth", "token"], capture_output=True, text=True, timeout=15
                )
                if proc.returncode == 0 and proc.stdout.strip():
                    token = proc.stdout.strip()
            except Exception:  # pragma: no cover - defensive
                pass
        GhModelsJudgeProvider._token_cache = (time.monotonic(), token)
        return token

    def availability(self) -> tuple[bool, str | None]:
        if self._token() is None:
            return False, ("no GitHub token: set GITHUB_TOKEN/GH_TOKEN or log in "
                           "with `gh auth login`")
        return True, None

    def complete(self, prompt: str, model: str) -> ProviderResult:
        token = self._token()
        if token is None:
            raise JudgeProviderError("no GitHub token available")

        body = json.dumps({
            "model": model,
            "messages": [{"role": "user", "content": prompt}],
            "temperature": 0,
        }).encode("utf-8")
        req = urllib.request.Request(
            GH_MODELS_URL,
            data=body,
            method="POST",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
                "Accept": "application/vnd.github+json",
                "X-GitHub-Api-Version": "2022-11-28",
            },
        )
        start = time.monotonic()
        try:
            with urllib.request.urlopen(req, timeout=self.TIMEOUT_SECONDS) as resp:
                payload = json.loads(resp.read().decode("utf-8"))
        except urllib.error.HTTPError as exc:
            detail = ""
            try:
                detail = exc.read().decode("utf-8")[:300]
            except Exception:
                pass
            raise JudgeProviderError(
                f"GitHub Models returned HTTP {exc.code}: {detail}"
            ) from exc
        except (urllib.error.URLError, TimeoutError, json.JSONDecodeError) as exc:
            raise JudgeProviderError(f"GitHub Models request failed: {exc}") from exc
        wall = time.monotonic() - start

        try:
            text = payload["choices"][0]["message"]["content"]
        except (KeyError, IndexError, TypeError) as exc:
            raise JudgeProviderError(
                f"unexpected GitHub Models response shape: {str(payload)[:300]}"
            ) from exc
        usage = payload.get("usage") or {}
        return ProviderResult(
            text=text or "",
            input_tokens=int(usage.get("prompt_tokens") or 0),
            output_tokens=int(usage.get("completion_tokens") or 0),
            usd_equiv=None,  # billed by GitHub against the account's tier
            wall_seconds=wall,
        )


# ---------------------------------------------------------------------------
# registry
# ---------------------------------------------------------------------------

_PROVIDERS = {
    "claude-cli": ClaudeCliJudgeProvider,
    "gh-models": GhModelsJudgeProvider,
    "mock": MockJudgeProvider,
}


def list_providers():
    """Instantiate every registered provider, claude-cli first (the default)."""
    return [_PROVIDERS[pid]() for pid in ("claude-cli", "gh-models", "mock")]


def get_provider(provider_id: str):
    cls = _PROVIDERS.get(provider_id)
    if cls is None:
        raise KeyError(f"unknown judge provider {provider_id!r}; valid: {sorted(_PROVIDERS)}")
    return cls()
