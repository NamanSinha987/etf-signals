"""Static HTML dashboard built from stored data: today's signals with reasons, price vs SMA
charts, signal history, data health and the latest backtest (if `python backtest.py` was run).

Output is one self-contained HTML file (data embedded as JSON, no external libraries),
so it opens locally and can be hosted anywhere static.
"""
from __future__ import annotations

import json
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.data import IST, sanity_check

TEMPLATE = Path(__file__).with_name("dashboard_template.html")


def _num(x, nd: int = 4):
    return None if pd.isna(x) else round(float(x), nd)


def _day(d) -> str | None:
    return None if pd.isna(d) else pd.Timestamp(d).strftime("%Y-%m-%d")


def price_series(prices: pd.DataFrame, sma_window: int) -> dict:
    """Per symbol: dates with a bar, close and the SMA the strategy uses (on forward-filled closes)."""
    close = prices.pivot(index="date", columns="symbol", values="close").sort_index()
    sma = close.ffill().rolling(sma_window).mean()
    out = {}
    for sym in close.columns:
        has_bar = close[sym].notna()
        out[sym] = {
            "dates": [_day(d) for d in close.index[has_bar]],
            "close": [_num(v, 2) for v in close.loc[has_bar, sym]],
            "sma": [_num(v, 2) for v in sma.loc[has_bar, sym]],
        }
    return out


def explain(row: pd.Series, params: dict) -> str:
    """Plain-language reason an ETF is or isn't in the target portfolio."""
    if row["history_days"] < params["min_history"]:
        return f"Only {row['history_days']} days of data (needs {params['min_history']})"
    if not row["trend_ok"]:
        return f"Below its {params['sma_window']}-day average - trend filter fails"
    if row["target_weight"] > 0:
        return f"Rank {int(row['rank'])} of the ETFs in an uptrend - in the top {params['top_n']}"
    return f"In an uptrend but rank {int(row['rank'])} - outside the top {params['top_n']}"


def signal_rows(signals: pd.DataFrame, params: dict) -> list[dict]:
    rows = []
    for _, r in signals.iterrows():
        rows.append({
            "symbol": r["symbol"], "action": r["action"], "weight": _num(r["target_weight"]),
            "rank": None if pd.isna(r["rank"]) else int(r["rank"]),
            "close": _num(r["close"], 2), "sma": _num(r["sma"], 2),
            "sma_dist": _num(r["close"] / r["sma"] - 1) if r["sma"] else None,
            "momentum": _num(r["momentum"]), "trend_ok": bool(r["trend_ok"]),
            "last_bar": _day(r["last_bar"]), "why": explain(r, params),
        })
    return rows


def history_rows(history: pd.DataFrame, limit: int = 120) -> list[dict]:
    rows = []
    for asof, g in history.groupby("asof"):
        held = g[g["target_weight"] > 0].sort_values("rank")
        rows.append({
            "asof": _day(asof),
            "held": held["symbol"].tolist(),
            "buy": g.loc[g["action"] == "BUY", "symbol"].tolist(),
            "sell": g.loc[g["action"] == "SELL", "symbol"].tolist(),
        })
    return rows[::-1][:limit]


def data_health(prices: pd.DataFrame, asof: pd.Timestamp) -> list[dict]:
    rows = []
    for sym, g in prices.groupby("symbol"):
        rows.append({
            "symbol": sym, "first": _day(g["date"].min()), "last": _day(g["date"].max()),
            "rows": len(g), "stale": bool(g["date"].max() < asof),
            "sources": {k: int(v) for k, v in g["source"].value_counts().items()},
        })
    return rows


def backtest_data(out_dir: Path) -> dict | None:
    files = {n: out_dir / f"{n}.csv" for n in ("summary", "yearly", "equity")}
    if not all(f.exists() for f in files.values()):
        return None
    summary = pd.read_csv(files["summary"], index_col=0)
    yearly = pd.read_csv(files["yearly"], index_col=0)
    equity = pd.read_csv(files["equity"], index_col=0, parse_dates=True)
    drawdown = equity / equity.cummax() - 1
    return {
        "run_on": datetime.fromtimestamp(files["equity"].stat().st_mtime, IST).strftime("%d %b %Y"),
        "names": list(equity.columns),
        "summary": {"metrics": list(summary.index),
                    "values": {c: summary[c].tolist() for c in summary.columns}},
        "yearly": {"years": [int(y) for y in yearly.index],
                   "values": {c: [_num(v) for v in yearly[c]] for c in yearly.columns}},
        "dates": [_day(d) for d in equity.index],
        "equity": {c: [_num(v) for v in equity[c]] for c in equity.columns},
        "drawdown": {c: [_num(v) for v in drawdown[c]] for c in drawdown.columns},
    }


def build_html(cfg: dict, prices: pd.DataFrame, signals: pd.DataFrame,
               history: pd.DataFrame, backtest_dir: Path) -> str:
    params = cfg["strategy"]
    asof = pd.Timestamp(signals["asof"].iloc[0])
    data = {
        "generated": datetime.now(IST).strftime("%d %b %Y, %H:%M IST"),
        "asof": _day(asof),
        "params": params,
        "signals": signal_rows(signals, params),
        "warnings": sanity_check(prices),
        "history": history_rows(history),
        "health": data_health(prices, asof),
        "prices": price_series(prices, params["sma_window"]),
        "backtest": backtest_data(backtest_dir),
    }
    payload = json.dumps(data, separators=(",", ":"), allow_nan=False).replace("</", "<\\/")
    return TEMPLATE.read_text(encoding="utf-8").replace("/*__DATA__*/null", payload)
