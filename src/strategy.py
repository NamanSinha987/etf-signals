"""Trend-filtered momentum rotation.

Rules (evaluated on the latest close):
  1. Trend filter: an ETF is eligible only if close > its N-day SMA.
  2. Rank eligible ETFs by M-day total return.
  3. Target portfolio = top_n eligible ETFs, equal weight. Unused slots stay in cash.

Deliberately simple - Phase 1 is about proving the pipeline, not the alpha.
"""
from __future__ import annotations

import pandas as pd


def compute_features(prices: pd.DataFrame, sma_window: int, momentum_window: int) -> pd.DataFrame:
    """Wide close matrix -> latest-day feature table, one row per symbol."""
    raw = prices.pivot(index="date", columns="symbol", values="close").sort_index()
    # Take last_bar / counts before ffill, otherwise every symbol looks up to date
    last_bars = raw.apply(lambda s: s.last_valid_index())
    counts = raw.notna().sum()
    close = raw.ffill()
    sma = close.rolling(sma_window).mean()
    mom = close / close.shift(momentum_window) - 1

    last = close.index[-1]
    feats = pd.DataFrame({
        "close": close.loc[last],
        "sma": sma.loc[last],
        "momentum": mom.loc[last],
        "history_days": counts,
        "last_bar": last_bars,
    })
    feats.index.name = "symbol"
    return feats.reset_index()


def generate_signals(prices: pd.DataFrame, params: dict, previous: pd.DataFrame | None = None) -> pd.DataFrame:
    feats = compute_features(prices, params["sma_window"], params["momentum_window"])
    asof = prices["date"].max()

    feats["enough_history"] = feats["history_days"] >= params["min_history"]
    feats["trend_ok"] = feats["enough_history"] & (feats["close"] > feats["sma"])

    eligible = feats[feats["trend_ok"]].sort_values("momentum", ascending=False)
    feats["rank"] = feats["symbol"].map({s: i + 1 for i, s in enumerate(eligible["symbol"])})
    selected = set(eligible["symbol"].head(params["top_n"]))
    feats["target_weight"] = feats["symbol"].apply(
        lambda s: round(1 / params["top_n"], 4) if s in selected else 0.0
    )

    prev_held = set()
    if previous is not None and not previous.empty:
        prev_held = set(previous.loc[previous["target_weight"] > 0, "symbol"])

    def action(s: str) -> str:
        if s in selected and s not in prev_held:
            return "BUY"
        if s in selected:
            return "HOLD"
        if s in prev_held:
            return "SELL"
        return "-"

    feats["action"] = feats["symbol"].apply(action)
    feats.insert(0, "asof", asof)
    cols = ["asof", "symbol", "action", "target_weight", "rank", "close", "sma",
            "momentum", "trend_ok", "history_days", "last_bar"]
    return feats[cols].sort_values(["target_weight", "rank"], ascending=[False, True],
                                   na_position="last").reset_index(drop=True)
