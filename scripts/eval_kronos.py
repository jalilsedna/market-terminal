"""E1 — evaluate Kronos-base on our daily futures (roadmap §E, gate before building).

Kronos demos on crypto-hourly; this answers whether it forecasts our *daily
futures* usefully. It pulls real OHLCV through `obb_layer` (so it uses the same
data the terminal does), holds out the last `--horizon` bars, forecasts them
from the prior history, and scores the forecast against what actually happened.

This needs the forecasting stack (torch + Kronos + a model download from
HuggingFace) and so is meant to run on your machine, NOT in the locked-down CI
sandbox. See docs/kronos-integration.md.

Usage:
    python -m scripts.eval_kronos --instrument GC --horizon 30 --samples 30
    python -m scripts.eval_kronos --instrument NQ --context 400 --out nq.png
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd

from kronos_layer.forecast import forecast
from kronos_layer.types import OHLCV
from obb_layer.market import futures_history
from obb_layer.symbols import WATCHLIST


def _load_ohlcv(instrument: str) -> pd.DataFrame:
    """Daily OHLCV for a watchlist instrument, via obb_layer → tidy DataFrame."""
    if instrument not in WATCHLIST:
        raise SystemExit(f"unknown instrument {instrument!r}; choose from {list(WATCHLIST)}")
    inst = WATCHLIST[instrument]
    records = futures_history(inst.yf_symbol)
    if not records:
        raise SystemExit(f"no OHLCV returned for {inst.yf_symbol} (provider down / throttled?)")
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    missing = [c for c in OHLCV if c not in df.columns]
    if missing:
        raise SystemExit(f"OHLCV columns missing from provider data: {missing}")
    return df[["date", *OHLCV]]


def _score(actual_close: np.ndarray, result, last_close: float) -> dict:
    """MAE / MAPE, directional hit-rate, and p10–p90 band coverage."""
    fc = result.close_median()
    mae = float(np.mean(np.abs(fc - actual_close)))
    mape = float(np.mean(np.abs((fc - actual_close) / actual_close)) * 100)

    # Step-to-step direction vs the actual path (prepend the last context close).
    fc_dir = np.sign(np.diff(np.concatenate([[last_close], fc])))
    act_dir = np.sign(np.diff(np.concatenate([[last_close], actual_close])))
    hit_rate = float(np.mean(fc_dir == act_dir) * 100)

    q = result.close_quantiles
    lo, hi = q.get(0.1), q.get(0.9)
    coverage = (
        float(np.mean((actual_close >= lo) & (actual_close <= hi)) * 100)
        if lo is not None and hi is not None
        else float("nan")
    )
    return {"mae": mae, "mape_pct": mape, "dir_hit_pct": hit_rate, "band_cover_pct": coverage}


def _plot(instrument, ctx, actual, result, out_path):
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("(matplotlib not installed — skipping plot)")
        return
    fc = result.close_median()
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(ctx["date"], ctx["close"], color="#9aa", label="history")
    ax.plot(actual["date"], actual["close"], color="#2b2", label="actual (held-out)")
    ax.plot(actual["date"], fc, color="#36f", label="forecast median")
    q = result.close_quantiles
    if 0.1 in q and 0.9 in q:
        ax.fill_between(actual["date"], q[0.1], q[0.9], color="#36f", alpha=0.15, label="p10–p90")
    ax.set_title(f"Kronos-base forecast vs actual — {instrument}")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    print(f"plot → {out_path}")


def main() -> None:
    p = argparse.ArgumentParser(description="Evaluate Kronos-base on daily futures.")
    p.add_argument("--instrument", default="GC", help="watchlist code (GC, NQ, 6E, 6B, YM)")
    p.add_argument("--context", type=int, default=400, help="context bars fed to the model")
    p.add_argument("--horizon", type=int, default=30, help="bars to hold out and forecast")
    p.add_argument("--samples", type=int, default=30, help="sampled paths for the band")
    p.add_argument("--out", default=None, help="plot PNG path (default: kronos_<inst>.png)")
    args = p.parse_args()

    df = _load_ohlcv(args.instrument)
    need = args.context + args.horizon
    if len(df) < need:
        raise SystemExit(f"need ≥{need} bars, got {len(df)} for {args.instrument}")

    window = df.tail(need).reset_index(drop=True)
    ctx = window.iloc[: -args.horizon]
    actual = window.iloc[-args.horizon :].reset_index(drop=True)

    print(
        f"{args.instrument}: {len(ctx)} context bars "
        f"({ctx['date'].iloc[0].date()}→{ctx['date'].iloc[-1].date()}), "
        f"forecasting {args.horizon} bars with Kronos-base ×{args.samples} paths…"
    )
    result = forecast(
        df=ctx[list(OHLCV)],
        x_timestamp=ctx["date"],
        y_timestamp=actual["date"],
        horizon=args.horizon,
        samples=args.samples,
    )

    scores = _score(actual["close"].to_numpy(dtype=float), result, float(ctx["close"].iloc[-1]))
    print("\n── scores ─────────────────────────────")
    print(f"  MAE              : {scores['mae']:.4f}")
    print(f"  MAPE             : {scores['mape_pct']:.2f}%")
    print(f"  Directional hit  : {scores['dir_hit_pct']:.1f}%   (50% = coin flip)")
    print(f"  p10–p90 coverage : {scores['band_cover_pct']:.1f}%  (target ≈ 80%)")
    print("───────────────────────────────────────")
    print(result.disclaimer)

    _plot(args.instrument, ctx, actual, result, args.out or f"kronos_{args.instrument}.png")


if __name__ == "__main__":
    main()
