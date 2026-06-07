"""Phase-0 capability spike / regression probe (SPEC.md §5 step 2, §6).

Calls each SPEC §3 endpoint for our real symbols and records what actually comes
back — success/failure, provider used, row count, columns, and latest date /
date range. This is the "check what OpenBB already provides" step: it tells us
what is real before we build V1/V4/V2 on top of assumptions, and doubles as a
regression check to re-run after every OpenBB upgrade.

It is deliberately read-only and fault-tolerant: one endpoint failing (missing
key, renamed field, empty result) never aborts the whole run — the failure is
recorded and the probe moves on.

Usage:
    python -m obb_layer.probe
"""

from __future__ import annotations

import json
from collections.abc import Callable
from dataclasses import asdict, dataclass, field
from datetime import date, datetime
from pathlib import Path
from typing import Any

from obb_layer.client import get_obb
from obb_layer.symbols import WATCHLIST

# Where the machine-readable probe report is written. `cache/data/` is already
# gitignored (SPEC.md §6), so the report never lands in version control.
REPORT_PATH = Path("cache/data/probe_report.json")


@dataclass
class ProbeResult:
    """What one endpoint call actually returned."""

    label: str
    need: str  # which SPEC §3 need this covers
    ok: bool = False
    provider: str | None = None
    rows: int = 0
    columns: list[str] = field(default_factory=list)
    latest: str | None = None  # most recent date seen in the data
    earliest: str | None = None
    error: str | None = None

    def summary_line(self) -> str:
        if not self.ok:
            return f"  [FAIL] {self.label:<34} {self.error}"
        span = ""
        if self.earliest and self.latest:
            span = f"  {self.earliest}→{self.latest}"
        elif self.latest:
            span = f"  latest {self.latest}"
        cols = ", ".join(self.columns[:6])
        if len(self.columns) > 6:
            cols += ", …"
        return (
            f"  [ OK ] {self.label:<34} provider={self.provider or '?':<16}"
            f" rows={self.rows:<5}{span}\n"
            f"         cols: {cols}"
        )


def _describe(obj: Any) -> tuple[str | None, int, list[str], str | None, str | None]:
    """Pull (provider, rows, columns, earliest, latest) out of an OBBject.

    Tolerant of OpenBB's response shape moving between versions: it prefers the
    DataFrame view, falls back to the raw `.results` list, and never raises.
    """
    provider = getattr(obj, "provider", None)
    results = getattr(obj, "results", obj)

    # Normalise to a list of record-dicts.
    records: list[dict] = []
    try:
        df = obj.to_dataframe()  # type: ignore[union-attr]
        columns = [str(c) for c in df.columns]
        rows = len(df)
        # Surface the index too (OpenBB often puts the date on the index).
        if df.index.name and df.index.name not in columns:
            columns = [str(df.index.name), *columns]
        records = df.reset_index().to_dict("records")
    except Exception:  # noqa: BLE001 — discovery probe must not crash on shape
        if isinstance(results, list):
            records = [_to_dict(r) for r in results]
        elif results is not None:
            records = [_to_dict(results)]
        rows = len(records)
        columns = list(records[0].keys()) if records else []

    earliest, latest = _date_span(records)
    return provider, rows, columns, earliest, latest


def _to_dict(item: Any) -> dict:
    """Best-effort conversion of a pydantic result row to a plain dict."""
    for attr in ("model_dump", "dict"):
        fn = getattr(item, attr, None)
        if callable(fn):
            try:
                return fn()
            except Exception:  # noqa: BLE001
                pass
    return dict(item) if isinstance(item, dict) else {"value": item}


def _date_span(records: list[dict]) -> tuple[str | None, str | None]:
    """Find the earliest/latest date-like value across records, if any."""
    dates: list[date] = []
    for rec in records:
        for key in ("date", "Date", "datetime", "timestamp"):
            val = rec.get(key) if isinstance(rec, dict) else None
            if val is None:
                continue
            if isinstance(val, (datetime, date)):
                dates.append(val.date() if isinstance(val, datetime) else val)
            else:
                try:
                    dates.append(datetime.fromisoformat(str(val)[:10]).date())
                except ValueError:
                    pass
            break
    if not dates:
        return None, None
    return min(dates).isoformat(), max(dates).isoformat()


def _run(results: list[ProbeResult], label: str, need: str, call: Callable[[], Any]) -> None:
    """Execute one probe call and append a recorded result."""
    res = ProbeResult(label=label, need=need)
    try:
        obj = call()
        provider, rows, columns, earliest, latest = _describe(obj)
        res.ok = rows > 0 or provider is not None
        res.provider = provider
        res.rows = rows
        res.columns = columns
        res.earliest = earliest
        res.latest = latest
        if rows == 0:
            res.error = "no rows returned"
            res.ok = False
    except Exception as exc:  # noqa: BLE001 — record, never abort the run
        res.error = f"{type(exc).__name__}: {exc}".replace("\n", " ")[:200]
    results.append(res)
    print(res.summary_line())


def build_probes(obb: Any) -> list[tuple[str, str, Callable[[], Any]]]:
    """The (label, SPEC-need, call) specs to probe. Free providers preferred."""
    probes: list[tuple[str, str, Callable[[], Any]]] = []

    # --- Futures EOD (SPEC §3: futures price) ---
    for _code, inst in WATCHLIST.items():
        probes.append((
            f"futures.historical {inst.yf_symbol}",
            "futures price (EOD)",
            lambda s=inst.yf_symbol: obb.derivatives.futures.historical(
                symbol=s, provider="yfinance"
            ),
        ))

    # --- Spot/cash proxies (SPEC §3: FX + indices) ---
    probes.append((
        "currency.historical EURUSD",
        "FX spot proxy (6E)",
        lambda: obb.currency.price.historical(symbol="EURUSD", provider="yfinance"),
    ))
    probes.append((
        "currency.historical GBPUSD",
        "FX spot proxy (6B)",
        lambda: obb.currency.price.historical(symbol="GBPUSD", provider="yfinance"),
    ))
    probes.append((
        "index.historical ^NDX",
        "index cash proxy (NQ)",
        lambda: obb.index.price.historical(symbol="^NDX", provider="yfinance"),
    ))
    probes.append((
        "index.historical ^DJI",
        "index cash proxy (YM)",
        lambda: obb.index.price.historical(symbol="^DJI", provider="yfinance"),
    ))

    # --- COT / positioning (SPEC §3 / V4). Top-level `cftc` router in OpenBB
    # 4.4.1 (not under `regulators`); `code` is the CFTC contract code. 088691 =
    # gold futures — cot_search maps human queries → codes. ---
    probes.append((
        "cftc.cot_search 'gold'",
        "COT search",
        lambda: obb.cftc.cot_search(query="gold"),
    ))
    probes.append((
        "cftc.cot gold (088691)",
        "COT positioning",
        lambda: obb.cftc.cot(code="088691", provider="cftc"),
    ))

    # --- Macro calendar (SPEC §3 / V1). Let OpenBB pick its default provider
    # (fmp/fred/tradingeconomics — all keyed); the probe records which is live. ---
    probes.append((
        "economy.calendar",
        "macro calendar",
        lambda: obb.economy.calendar(),
    ))

    # --- FRED series — exercises the FRED key (SPEC §3 / V1) ---
    probes.append((
        "economy.fred_series DGS10",
        "macro series (10y yield)",
        lambda: obb.economy.fred_series(symbol="DGS10", provider="fred"),
    ))
    probes.append((
        "economy.fred_series DTWEXBGS",
        "macro series (broad USD)",
        lambda: obb.economy.fred_series(symbol="DTWEXBGS", provider="fred"),
    ))

    # --- Yield curve (SPEC §3 / V1) ---
    probes.append((
        "fixedincome.yield_curve",
        "yield curve",
        lambda: obb.fixedincome.government.yield_curve(provider="federal_reserve"),
    ))

    return probes


def main() -> None:
    obb = get_obb()
    print("OpenBB loaded. Watchlist:", ", ".join(WATCHLIST))
    print("Probing SPEC §3 endpoints (read-only)…\n")

    results: list[ProbeResult] = []
    for label, need, call in build_probes(obb):
        _run(results, label, need, call)

    ok = sum(1 for r in results if r.ok)
    print(f"\nSummary: {ok}/{len(results)} endpoints returned data.")
    failed = [r.label for r in results if not r.ok]
    if failed:
        print("Needs attention:", ", ".join(failed))

    REPORT_PATH.parent.mkdir(parents=True, exist_ok=True)
    REPORT_PATH.write_text(
        json.dumps(
            {
                "generated_at": datetime.now().isoformat(timespec="seconds"),
                "results": [asdict(r) for r in results],
            },
            indent=2,
            default=str,
        ),
        encoding="utf-8",
    )
    print(f"Wrote machine-readable report → {REPORT_PATH}")


if __name__ == "__main__":
    main()
