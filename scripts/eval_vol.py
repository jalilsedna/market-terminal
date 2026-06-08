"""E5 — validate HAR-RV volatility forecasting on real instruments.

Same evidence-first discipline we held Kronos to, but for volatility: walk-forward
over many windows, and a forecast only earns its keep if it **beats the baselines**
(EWMA and persistence) on forecast error — judged on QLIKE, the standard robust
vol-forecast loss.

Unlike the Kronos eval this is **pure CPU, no torch/GPU/HuggingFace** — it runs in
the terminal's normal venv. The realized-vol proxy is per-bar Garman-Klass vol.

Usage:
    python -m scripts.eval_vol --asset futures --instrument GC --horizon 5
    python -m scripts.eval_vol --asset forex --instrument EURUSD --windows 60
"""

from __future__ import annotations

import argparse

import numpy as np

from scripts._data import load_ohlcv
from vol import (
    daily_vol_series,
    ewma_vol,
    har_rv_forecast,
    log_returns,
    mae,
    persistence_forecast,
    qlike,
    rmse,
    vol_regime,
)


def _score_window(ctx, actual, horizon: int) -> dict:
    """Score HAR vs EWMA vs persistence for one walk-forward window."""
    vol_hist = daily_vol_series(ctx["open"], ctx["high"], ctx["low"], ctx["close"])
    actual_vol = daily_vol_series(
        actual["open"], actual["high"], actual["low"], actual["close"]
    )

    har = har_rv_forecast(vol_hist, horizon=horizon)["forecast"]
    ewma = np.full(horizon, ewma_vol(log_returns(ctx["close"])))
    pers = persistence_forecast(vol_hist, horizon)

    out = {}
    for name, fc in (("har", har), ("ewma", ewma), ("pers", pers)):
        out[f"{name}_qlike"] = qlike(fc, actual_vol)
        out[f"{name}_rmse"] = rmse(fc, actual_vol)
        out[f"{name}_mae"] = mae(fc, actual_vol)
    return out


def main() -> None:
    p = argparse.ArgumentParser(description="Walk-forward eval of HAR-RV vol vs baselines.")
    p.add_argument("--asset", default="futures", choices=["futures", "crypto", "forex"])
    p.add_argument("--instrument", default="GC", help="watchlist code / yf symbol / pair")
    p.add_argument("--interval", default="1d", choices=["1d", "1h"])
    p.add_argument("--horizon", type=int, default=5, help="bars of vol to forecast per window")
    p.add_argument("--context", type=int, default=252, help="history bars fed to HAR (>=30)")
    p.add_argument("--windows", type=int, default=40, help="walk-forward windows")
    p.add_argument("--step", type=int, default=None, help="bars between windows (default: horizon)")
    p.add_argument("--years", type=int, default=8)
    args = p.parse_args()
    step = args.step or args.horizon

    df = load_ohlcv(args.asset, args.instrument, args.years, args.interval)
    context = min(args.context, len(df) - args.horizon - 1)
    if context < 40:
        raise SystemExit(f"not enough history ({len(df)} bars) — need >= ~80")
    anchors = list(range(context, len(df) - args.horizon + 1, step))[-args.windows :]

    print(f"{args.asset}:{args.instrument} @ {args.interval} — {len(df)} bars, "
          f"{len(anchors)} windows · horizon {args.horizon} · context {context}")

    scores: list[dict] = []
    for a in anchors:
        ctx = df.iloc[a - context : a]
        actual = df.iloc[a : a + args.horizon].reset_index(drop=True)
        scores.append(_score_window(ctx, actual, args.horizon))

    def mean(key: str) -> float:
        return float(np.mean([s[key] for s in scores]))

    print("\n── mean forecast loss over windows (lower wins) ───────────────")
    print(f"{'':10}{'QLIKE':>10}{'RMSE':>10}{'MAE':>10}")
    for name, label in (("har", "HAR-RV"), ("ewma", "EWMA"), ("pers", "persistence")):
        print(f"  {label:<8}{mean(f'{name}_qlike'):>10.4f}{mean(f'{name}_rmse'):>10.4f}"
              f"{mean(f'{name}_mae'):>10.4f}")
    print("───────────────────────────────────────────────────────────────")

    har_q, ewma_q, pers_q = mean("har_qlike"), mean("ewma_qlike"), mean("pers_qlike")
    beats = har_q < ewma_q and har_q < pers_q
    print(f"  HAR beats EWMA on QLIKE      : {'YES' if har_q < ewma_q else 'no'}")
    print(f"  HAR beats persistence QLIKE  : {'YES' if har_q < pers_q else 'no'}")
    print("  →", "HAR earns its keep — proceed to wire it in (E3)" if beats
          else "HAR doesn't beat the baselines here — EWMA/persistence may suffice")

    # Bonus: where current vol sits in its own history.
    vol_all = daily_vol_series(df["open"], df["high"], df["low"], df["close"])
    print("\n  current regime:", vol_regime(float(vol_all[-1]), vol_all[:-1]))


if __name__ == "__main__":
    main()
