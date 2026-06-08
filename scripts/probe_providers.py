"""Prove the EOD provider chain actually serves data (ROADMAP B4).

A fallback chain (`EOD_PROVIDERS=tiingo,yfinance`) fails *silently*: if the
Tiingo key is wrong or the provider 401s, the chain just falls through to
yfinance and the panel still renders — so you'd never notice you aren't getting
the reliability you configured. This probe hits each provider in the chain
*individually* for a known-portable symbol (AAPL/SPY) and reports which ones
actually return rows, so you can confirm Tiingo is live and not being skipped.

Runs in the normal venv (needs OpenBB + your `.env`). No network egress in CI,
so this is an operator tool, not a unit test.

Usage:
    python -m scripts.probe_providers
    python -m scripts.probe_providers --symbol SPY --route etf
"""

from __future__ import annotations

import argparse

from config import get_settings
from obb_layer.client import get_obb
from obb_layer.normalize import to_records


def _probe(route, symbol: str, provider: str) -> tuple[bool, str]:
    """Fetch `symbol` from one provider. Returns (ok, detail)."""
    try:
        rows = to_records(route(symbol=symbol, provider=provider, interval="1d"))
    except Exception as exc:  # noqa: BLE001 — report the failure, don't raise
        return False, f"{type(exc).__name__}: {exc}"
    if not rows:
        return False, "returned 0 rows"
    last = rows[-1]
    return True, f"{len(rows)} rows, last {last.get('date')} close={last.get('close')}"


def main() -> None:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--symbol", default="AAPL", help="portable equity/ETF symbol")
    ap.add_argument("--route", choices=["equity", "etf"], default="equity")
    args = ap.parse_args()

    settings = get_settings()
    chain = settings.eod_provider_chain
    obb = get_obb()
    route = obb.equity.price.historical if args.route == "equity" else obb.etf.historical

    print(f"EOD chain: {chain}")
    print(f"Tiingo key configured: {bool(settings.tiingo_api_key)}")
    print(f"Probing {args.route} '{args.symbol}' per provider:\n")

    first_ok: str | None = None
    for provider in chain:
        ok, detail = _probe(route, args.symbol, provider)
        mark = "OK " if ok else "FAIL"
        print(f"  [{mark}] {provider:10s} {detail}")
        if ok and first_ok is None:
            first_ok = provider

    print()
    if first_ok is None:
        print("=> NO provider returned data — the panel would be empty.")
    elif first_ok == chain[0]:
        print(f"=> Chain is serving from '{first_ok}' (the primary). Good.")
    else:
        print(
            f"=> Primary '{chain[0]}' failed; chain fell back to '{first_ok}'. "
            "Check the primary's key if you expected it to serve."
        )


if __name__ == "__main__":
    main()
