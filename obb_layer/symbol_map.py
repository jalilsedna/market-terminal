"""Per-provider symbol mapping (ROADMAP B-next).

Equity/ETF tickers are portable across providers (AAPL is AAPL everywhere), so
the B4 fallback chain worked for them directly. Crypto and FX are not: the same
pair is written differently per provider, e.g. our canonical `BTC-USD` is
`X:BTCUSD` on Polygon, `btcusd` on Tiingo; `EURUSD` is `C:EURUSD` on Polygon.

This module is the **one explicit place** that translates our canonical symbol
into each provider's format (CLAUDE.md: keep symbol mapping in one map, not
scattered literals), so the fallback chain can be extended to crypto/FX. Pure —
unit-tested in CI.

`map_symbol(asset, symbol, provider)` returns the provider-specific symbol, or
`None` when we don't have a mapping for that provider (the caller then skips it
rather than sending a malformed symbol).
"""

from __future__ import annotations

# Providers we know how to address for crypto/FX. Anything else → skip (None).
_CRYPTO_PROVIDERS = {"yfinance", "polygon", "tiingo", "fmp"}
_FX_PROVIDERS = {"yfinance", "polygon", "tiingo", "fmp"}


def _split_crypto(symbol: str) -> tuple[str, str] | None:
    """'BTC-USD' → ('BTC','USD'). Requires the canonical dash form."""
    s = symbol.upper().strip()
    if "-" not in s:
        return None
    base, _, quote = s.partition("-")
    if not base or not quote:
        return None
    return base, quote


def _split_fx(symbol: str) -> tuple[str, str] | None:
    """'EURUSD' (or 'EUR/USD', 'EURUSD=X') → ('EUR','USD'). Assumes 3+3 majors."""
    s = symbol.upper().strip().replace("=X", "").replace("/", "")
    if len(s) != 6:
        return None
    return s[:3], s[3:]


def map_symbol(asset: str, symbol: str, provider: str) -> str | None:
    """Canonical `symbol` → `provider`'s format for `asset` ('crypto'/'forex').

    Returns None when the provider isn't mapped for that asset (skip it) or the
    symbol can't be parsed. Equity/ETF (portable) pass through unchanged.
    """
    asset = (asset or "").lower()
    provider = (provider or "").lower()

    if asset == "crypto":
        if provider not in _CRYPTO_PROVIDERS:
            return None
        parts = _split_crypto(symbol)
        if not parts:
            return None
        base, quote = parts
        return {
            "yfinance": f"{base}-{quote}",
            "polygon": f"X:{base}{quote}",
            "tiingo": f"{base}{quote}".lower(),
            "fmp": f"{base}{quote}",
        }[provider]

    if asset in ("forex", "fx", "currency"):
        if provider not in _FX_PROVIDERS:
            return None
        parts = _split_fx(symbol)
        if not parts:
            return None
        base, quote = parts
        return {
            "yfinance": f"{base}{quote}",
            "polygon": f"C:{base}{quote}",
            "tiingo": f"{base}{quote}".lower(),
            "fmp": f"{base}{quote}",
        }[provider]

    # Equity / ETF / anything portable: same symbol everywhere.
    return symbol
