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
    ewma_vol,
    har_rv_forecast,
    log_returns,
    mae,
    qlike,
    realized_vol_series,
    rmse,
    vol_regime,
)

VOL_WINDOW = 21  # trailing window for the (smooth, non-zero) realized-vol target


def _score_window(ctx, actual, horizon: int) -> dict:
    """Score HAR vs EWMA vs persistence for one walk-forward window.

    Target = the realized vol *actually observed over the next `horizon` bars*
    (close-to-close), a single smooth, strictly-positive number — not a noisy
    per-bar estimate (which made QLIKE blow up). Each model predicts one number.
    """
    vol_hist = realized_vol_series(ctx["close"].to_numpy(), window=VOL_WINDOW)
    # actual realized vol of the next `horizon` bars (incl. the jump from the last
    # context close into the horizon).
    horizon_close = np.concatenate([[ctx["close"].iloc[-1]], actual["close"].to_numpy()])
    actual_vol = float(np.std(log_returns(horizon_close), ddof=1) * np.sqrt(252))

    har_fc = float(np.mean(har_rv_forecast(vol_hist, horizon=horizon)["forecast"]))
    ewma_fc = ewma_vol(log_returns(ctx["close"].to_numpy()))
    pers_fc = float(vol_hist[-1])

    out = {}
    for name, fc in (("har", har_fc), ("ewma", ewma_fc), ("pers", pers_fc)):
        out[f"{name}_qlike"] = qlike([fc], [actual_vol])
        out[f"{name}_rmse"] = rmse([fc], [actual_vol])
        out[f"{name}_mae"] = mae([fc], [actual_vol])
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
    if context < VOL_WINDOW + 35:  # HAR needs >= ~30 windowed-vol points
        raise SystemExit(f"not enough history ({len(df)} bars) — need a deeper series")
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

    # Bonus: where current vol sits in its own history (smooth rolling series).
    vol_all = realized_vol_series(df["close"].to_numpy(), window=VOL_WINDOW)
    print("\n  current regime:", vol_regime(float(vol_all[-1]), vol_all[:-1]))


if __name__ == "__main__":
    main()
