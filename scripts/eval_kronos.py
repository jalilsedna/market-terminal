"""E1 — rigorous evaluation of Kronos-base on our daily futures (roadmap §E).

Kronos demos on crypto-hourly; this answers whether it forecasts our *daily
futures* with real skill. It improves on a single held-out slice in three ways:

  * deep history  — pulls multi-year OHLCV via obb_layer so the model gets its
    full 512-bar context (yfinance's default ~1y starves it);
  * walk-forward  — scores many non-overlapping windows, not one noisy slice;
  * baselines     — compares against *persistence* (predict last-close-flat) on
    error and against a coin-flip / always-up rate on direction, because a low
    MAPE on a flat series is meaningless on its own.

Needs the forecasting stack (torch + Kronos + a HF download) — run on your
machine, not the CI sandbox. See docs/kronos-integration.md.

Usage:
    python -m scripts.eval_kronos --instrument GC --horizon 10 --windows 12
    python -m scripts.eval_kronos --instrument NQ --context 512 --years 8
"""

from __future__ import annotations

import argparse
from datetime import date, timedelta

import pandas as pd

from kronos_layer import metrics as M
from kronos_layer.forecast import forecast
from kronos_layer.types import OHLCV
from obb_layer.market import futures_history
from obb_layer.symbols import WATCHLIST


def _load_ohlcv(instrument: str, years: int) -> pd.DataFrame:
    if instrument not in WATCHLIST:
        raise SystemExit(f"unknown instrument {instrument!r}; choose from {list(WATCHLIST)}")
    inst = WATCHLIST[instrument]
    start = (date.today() - timedelta(days=365 * years + 10)).isoformat()
    records = futures_history(inst.yf_symbol, start_date=start)
    if not records:
        raise SystemExit(f"no OHLCV for {inst.yf_symbol} (provider down / throttled?)")
    df = pd.DataFrame(records)
    df["date"] = pd.to_datetime(df["date"])
    df = df.sort_values("date").reset_index(drop=True)
    missing = [c for c in OHLCV if c not in df.columns]
    if missing:
        raise SystemExit(f"OHLCV columns missing: {missing}")
    return df[["date", *OHLCV]]


def _data_health(df: pd.DataFrame) -> None:
    """Surface the biggest 1-day move — a roll gap in a continuation series can
    wreck a forecast and would explain a 0% band coverage."""
    chg = df["close"].pct_change().abs()
    i = int(chg.idxmax())
    print(
        f"  bars: {len(df)}  ({df['date'].iloc[0].date()} → {df['date'].iloc[-1].date()})\n"
        f"  largest 1-day move: {chg.iloc[i] * 100:.1f}% on {df['date'].iloc[i].date()} "
        f"(roll-gap check)"
    )


def _score_window(ctx: pd.DataFrame, actual: pd.DataFrame, horizon: int, samples: int) -> dict:
    result = forecast(
        df=ctx[list(OHLCV)],
        x_timestamp=ctx["date"],
        y_timestamp=actual["date"],
        horizon=horizon,
        samples=samples,
    )
    fc = result.close_median()
    act = actual["close"].to_numpy(dtype=float)
    last = float(ctx["close"].iloc[-1])
    q = result.close_quantiles
    return {
        "k_dir": M.directional_hit(fc, act, last),
        "base_up": M.majority_up_rate(act, last),
        "k_mape": M.mape(fc, act),
        "p_mape": M.mape(M.persistence_close(last, horizon), act),
        "k_cover": M.band_coverage(act, q[0.1], q[0.9]),
    }, result


def main() -> None:
    p = argparse.ArgumentParser(description="Walk-forward eval of Kronos-base on daily futures.")
    p.add_argument("--instrument", default="GC", help="watchlist code (GC, NQ, 6E, 6B, YM)")
    p.add_argument("--horizon", type=int, default=10, help="bars to forecast per window")
    p.add_argument("--context", type=int, default=512, help="context bars (Kronos-base trained @512)")
    p.add_argument("--windows", type=int, default=12, help="walk-forward windows to score")
    p.add_argument("--step", type=int, default=None, help="bars between windows (default: horizon)")
    p.add_argument("--samples", type=int, default=20, help="sampled paths per forecast")
    p.add_argument("--years", type=int, default=8, help="years of history to request")
    p.add_argument("--out", default=None, help="plot PNG (default: kronos_<inst>.png)")
    args = p.parse_args()
    step = args.step or args.horizon

    df = _load_ohlcv(args.instrument, args.years)
    print(f"{args.instrument}:")
    _data_health(df)

    # Pick the most recent `windows` non-overlapping anchors that fit the context.
    context = min(args.context, len(df) - args.horizon - 1)
    if context < 64:
        raise SystemExit(f"not enough history ({len(df)} bars) for a useful context")
    anchors = list(range(context, len(df) - args.horizon + 1, step))[-args.windows :]
    if not anchors:
        raise SystemExit("no valid walk-forward windows — reduce --context/--horizon")

    print(
        f"  walk-forward: {len(anchors)} windows · horizon {args.horizon} · "
        f"context {context} · {args.samples} paths/forecast (this is slow on CPU)…"
    )
    scores: list[dict] = []
    last_result = last_ctx = last_actual = None
    for n, a in enumerate(anchors, 1):
        ctx = df.iloc[a - context : a]
        actual = df.iloc[a : a + args.horizon].reset_index(drop=True)
        s, result = _score_window(ctx, actual, args.horizon, args.samples)
        scores.append(s)
        last_result, last_ctx, last_actual = result, ctx, actual
        print(f"    [{n}/{len(anchors)}] {ctx['date'].iloc[-1].date()}  dir={s['k_dir']:.0f}%")

    agg = M.aggregate(scores)
    print("\n── walk-forward results (mean ± std over windows) ──────────────")
    print(f"  Directional hit : Kronos {agg['k_dir']['mean']:.1f} ± {agg['k_dir']['std']:.1f}%"
          f"   | always-up baseline {agg['base_up']['mean']:.1f}%   (coin = 50%)")
    print(f"  MAPE            : Kronos {agg['k_mape']['mean']:.2f}%"
          f"   | persistence {agg['p_mape']['mean']:.2f}%  (lower wins)")
    print(f"  p10–p90 cover   : Kronos {agg['k_cover']['mean']:.1f} ± {agg['k_cover']['std']:.1f}%"
          f"   (target ≈ 80%)")
    print("───────────────────────────────────────────────────────────────")

    # Verdict — the three questions that decide the gate.
    beats_dir = agg["k_dir"]["mean"] > max(50.0, agg["base_up"]["mean"])
    beats_lvl = agg["k_mape"]["mean"] < agg["p_mape"]["mean"]
    calibrated = abs(agg["k_cover"]["mean"] - 80.0) <= 15.0
    print(f"  beats coin/always-up on direction : {'YES' if beats_dir else 'no'}")
    print(f"  beats persistence on error        : {'YES' if beats_lvl else 'no'}")
    print(f"  band roughly calibrated (~80%)     : {'YES' if calibrated else 'no'}")
    print("  →", "promising — proceed to E2/E3" if (beats_dir and beats_lvl)
          else "no clear edge yet — see notes")
    print(last_result.disclaimer)

    _plot(args.instrument, last_ctx, last_actual, last_result, args.out or f"kronos_{args.instrument}.png")


def _plot(instrument, ctx, actual, result, out_path):
    try:
        import matplotlib

        matplotlib.use("Agg")
        import matplotlib.pyplot as plt
    except ImportError:
        print("(matplotlib not installed — skipping plot)")
        return
    tail = ctx.tail(120)
    fc = result.close_median()
    q = result.close_quantiles
    fig, ax = plt.subplots(figsize=(11, 5))
    ax.plot(tail["date"], tail["close"], color="#9aa", label="history")
    ax.plot(actual["date"], actual["close"], color="#2b2", label="actual (held-out)")
    ax.plot(actual["date"], fc, color="#36f", label="forecast median")
    ax.fill_between(actual["date"], q[0.1], q[0.9], color="#36f", alpha=0.15, label="p10–p90")
    ax.set_title(f"Kronos-base — {instrument} (latest walk-forward window)")
    ax.legend()
    fig.tight_layout()
    fig.savefig(out_path, dpi=120)
    print(f"plot → {out_path}")


if __name__ == "__main__":
    main()
