"""Research-symbol → IBKR contract map (ROADMAP A10).

market-terminal researches canonical symbols (``EURUSD``, ``XAUUSD``, ``GC=F``);
OpenAlice executes on IBKR, which names contracts differently (``EUR.USD`` on
IDEALPRO, spot ``XAU.USD``, ``GC`` front future). This is the ONE explicit place
that translates a research symbol into its IBKR contract + venue, so
``decision_brief`` can name BOTH and Alice routes unambiguously.

This is a naming aid only. Execution lives in OpenAlice — nothing here places,
routes, or holds an order; no broker keys touch this repo (CLAUDE.md hard rules).
Alice still resolves the exact tradable contract on its side; this just removes
the guesswork in the trade card.
"""

from __future__ import annotations

# Explicit CME/COMEX futures root → IBKR contract + native venue. For the FX
# futures (6E/6B/…) IBKR's cleaner route is spot FX on IDEALPRO, which is also
# what the forex book trades — so we map them to the dotted spot pair.
_FUTURES_IBKR: dict[str, tuple[str, str]] = {
    "GC": ("GC", "COMEX"),
    "SI": ("SI", "COMEX"),
    "HG": ("HG", "COMEX"),
    "CL": ("CL", "NYMEX"),
    "NG": ("NG", "NYMEX"),
    "ES": ("ES", "CME"),
    "NQ": ("NQ", "CME"),
    "RTY": ("RTY", "CME"),
    "YM": ("YM", "CBOT"),
    "6E": ("EUR.USD", "IDEALPRO"),
    "6B": ("GBP.USD", "IDEALPRO"),
    "6A": ("AUD.USD", "IDEALPRO"),
    "6C": ("USD.CAD", "IDEALPRO"),
    "6J": ("USD.JPY", "IDEALPRO"),
    "6S": ("USD.CHF", "IDEALPRO"),
    "6N": ("NZD.USD", "IDEALPRO"),
}

# Metal bases: research XAUUSD/XAGUSD → IBKR spot metal in USD on IDEALPRO.
_METALS = {"XAU", "XAG", "XPT", "XPD"}


def ibkr_contract(symbol: str, asset: str | None = None) -> dict | None:
    """Canonical research symbol → ``{contract, venue, sec_type, research_symbol}``
    for IBKR, or ``None`` when there is no natural IBKR mapping (crypto routes via
    Paxos with a limited set — leave that to Alice).
    """
    s = (symbol or "").upper().strip()
    a = (asset or "").lower().strip()
    if not s:
        return None

    # Futures continuation (GC=F) or bare root.
    if s.endswith("=F"):
        root = s[:-2]
        hit = _FUTURES_IBKR.get(root)
        if hit:
            contract, venue = hit
            sec = "CASH" if venue == "IDEALPRO" else "FUT"
            return {"contract": contract, "venue": venue, "sec_type": sec, "research_symbol": s}
        return {"contract": root, "venue": "GLOBEX", "sec_type": "FUT", "research_symbol": s}

    # Crypto: IBKR routes via Paxos (limited). Leave contract resolution to Alice.
    if a == "crypto" or "-" in s:
        return None

    # Spot FX / metals: 6-char EURUSD / XAUUSD → EUR.USD / XAU.USD on IDEALPRO.
    if a in ("forex", "fx", "currency") or (len(s) == 6 and s.isalpha()):
        base, quote = s[:3], s[3:]
        sec = "CMDTY" if base in _METALS else "CASH"
        return {"contract": f"{base}.{quote}", "venue": "IDEALPRO", "sec_type": sec, "research_symbol": s}

    # Equity / ETF: IBKR uses the plain ticker under SMART routing.
    return {"contract": s, "venue": "SMART", "sec_type": "STK", "research_symbol": s}
