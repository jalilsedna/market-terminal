"""Provider fallback for EOD fetches (ROADMAP B4 — reliability).

Where a symbol is portable across providers (equity, ETF, FX, crypto), we try a
configurable provider **chain** (`settings.eod_provider_chain`) until one returns
data. Default chain is FMP-first (`fmp,tiingo,polygon`).

Futures continuation symbols use direct FMP REST (`obb_layer/fmp_market.py`) —
they are not in this chain.

Pure except for the route it's handed, so the chain logic is unit-tested.
"""

from __future__ import annotations

from collections.abc import Callable
from typing import Any

from config import get_settings
from obb_layer.normalize import to_records
from obb_layer.symbol_map import map_symbol


def eod_with_fallback(
    route: Callable[..., Any],
    symbol: str,
    *,
    asset: str | None = None,
    start_date: str | None = None,
    interval: str | None = None,
    providers: list[str] | None = None,
) -> list[dict]:
    """Call an OpenBB historical `route` across the provider chain until one
    returns rows. `route` is a bound endpoint, e.g. `get_obb().etf.historical`.

    When `asset` is given ('crypto'/'forex'), each provider is queried with its
    own symbol format (via `symbol_map`); a provider with no mapping is skipped.
    Equity/ETF leave `asset` None — symbols are portable.

    Raises the last error only if **every** provider failed; returns [] if every
    provider returned empty (no error).
    """
    chain = providers or get_settings().eod_provider_chain
    last_exc: Exception | None = None
    for provider in chain:
        provider_symbol = map_symbol(asset, symbol, provider) if asset else symbol
        if provider_symbol is None:
            continue  # provider has no mapping for this asset → skip it
        kwargs: dict = {"symbol": provider_symbol, "provider": provider}
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
