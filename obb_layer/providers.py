"""Provider fallback for EOD fetches (ROADMAP B4 — reliability).

yfinance throttles / 401s often. Where a symbol is portable across providers
(equity, ETF — e.g. AAPL, SPY), we try a configurable provider **chain**
(`settings.eod_provider_chain`) until one returns data, so a single flaky
provider falls back instead of degrading the panel.

Safe by design: it tries each provider, skips failures, and uses the first that
yields rows — so with the default chain (["yfinance"]) behaviour is unchanged, and
adding e.g. "tiingo,yfinance" only *adds* resilience. Crypto/FX/futures keep
yfinance (their symbol formats are provider-specific).

Pure except for the route it's handed, so the chain logic is unit-tested.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from config import get_settings
from obb_layer.normalize import to_records


def eod_with_fallback(
    route: Callable[..., Any],
    symbol: str,
    *,
    start_date: str | None = None,
    interval: str | None = None,
    providers: list[str] | None = None,
) -> list[dict]:
    """Call an OpenBB historical `route` across the provider chain until one
    returns rows. `route` is a bound endpoint, e.g. `get_obb().etf.historical`.

    Raises the last error only if **every** provider failed; returns [] if every
    provider returned empty (no error).
    """
    chain = providers or get_settings().eod_provider_chain
    last_exc: Exception | None = None
    for provider in chain:
        kwargs: dict = {"symbol": symbol, "provider": provider}
        if start_date:
            kwargs["start_date"] = start_date
        if interval:
            kwargs["interval"] = interval
        try:
            rows = to_records(route(**kwargs))
            if rows:
                return rows
        except Exception as exc:  # noqa: BLE001 — try the next provider in the chain
            last_exc = exc
            continue
    if last_exc is not None:
        raise last_exc
    return []
