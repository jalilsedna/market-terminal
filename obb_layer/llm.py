"""Anthropic LLM client (ROADMAP H14 — News Pulse analyst).

The ONLY place the terminal talks to the Anthropic API, mirroring the
obb_layer isolation rule: one site to absorb SDK/model churn, key-gate, and
fail soft. Everything here is optional — with no key (or no `anthropic`
package) `analyze_json` returns None and callers fall back to their
deterministic path.

Research synthesis only; never an order or a trade trigger.
"""

from __future__ import annotations

import json
from typing import Any

from config import get_settings


class LlmDisabled(RuntimeError):
    """No Anthropic key configured (or the SDK isn't installed)."""


def enabled() -> bool:
    return get_settings().llm_enabled


def _client():
    settings = get_settings()
    if not settings.anthropic_api_key:
        raise LlmDisabled("ANTHROPIC_API_KEY not set")
    try:
        import anthropic  # noqa: PLC0415 — optional dependency, lazy import
    except ImportError as exc:  # pragma: no cover - only when dep missing
        raise LlmDisabled("anthropic SDK not installed") from exc
    return anthropic.Anthropic(api_key=settings.anthropic_api_key)


def analyze_json(system: str, user: str, *, max_tokens: int = 1024) -> dict[str, Any] | None:
    """Run one analyst-style completion and parse a JSON object from the reply.

    Returns the parsed dict, or None on any failure (no key, SDK missing,
    network/API error, or unparseable output) so callers degrade gracefully.
    The model is asked for strict JSON; we still extract defensively.
    """
    settings = get_settings()
    try:
        client = _client()
    except LlmDisabled:
        return None

    try:
        resp = client.with_options(timeout=30.0, max_retries=1).messages.create(
            model=settings.news_pulse_model,
            max_tokens=max_tokens,
            system=system,
            messages=[{"role": "user", "content": user}],
        )
        text = "".join(b.text for b in resp.content if getattr(b, "type", None) == "text").strip()
    except Exception:  # noqa: BLE001 — LLM is an optional enricher; never sink the caller
        return None

    return _extract_json(text)


def _extract_json(text: str) -> dict[str, Any] | None:
    """Parse the first JSON object out of a model reply (tolerant of fences/prose)."""
    if not text:
        return None
    try:
        return json.loads(text)
    except json.JSONDecodeError:
        pass
    start, end = text.find("{"), text.rfind("}")
    if start != -1 and end > start:
        try:
            obj = json.loads(text[start : end + 1])
            return obj if isinstance(obj, dict) else None
        except json.JSONDecodeError:
            return None
    return None
