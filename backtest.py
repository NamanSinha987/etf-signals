"""Backtest the live strategy (src/strategy.py) on stored prices, using the backtester library.

The same generate_signals() the daily pipeline uses is called once per historical day with
only the data known on that day; trades happen at the next day's open, with costs.

Run:   python backtest.py        (needs: pip install -r requirements-research.txt)
Writes output/backtest/: summary.csv, yearly.csv, equity.csv, trades.csv, equity.png
"""
from __future__ import annotations

import argparse
import logging
import sys
import time
from pathlib import Path

import pandas as pd
import yaml
from backtester import buy_and_hold, run_backtest, walk_forward

from src.data import load_prices
from src.strategy import generate_signals

ROOT = Path(__file__).parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("backtest")


def strategy_weights(prices: pd.DataFrame, params: dict, start=None) -> pd.DataFrame:
    """Target weights from the live strategy code, as the Telegram signals would be traded:
    act only when the set of held ETFs changes (BUY/SELL), then rebalance to equal weights.
    HOLD days return None, so positions drift with prices and nothing is traded."""
    held: set = set()

    def decide(history: pd.DataFrame) -> pd.Series | None:
        nonlocal held
        w = generate_signals(history, params).set_index("symbol")["target_weight"]
        picked = set(w.index[w > 0])
        if picked == held:
            return None
        held = picked
        return w
    return walk_forward(prices, decide, date_col="date", start=start)


def yearly_returns(equity: pd.Series) -> pd.Series:
    ends = equity.groupby(equity.index.year).last()
    starts = ends.shift(1)
    starts.iloc[0] = equity.iloc[0]
    return ends / starts - 1


def summary_table(results: dict) -> pd.DataFrame:
    rows = {
        "Period": lambda m: f"{m['start']} -> {m['end']}",
        "CAGR": lambda m: f"{m['cagr']:.1%}",
        "Volatility": lambda m: f"{m['volatility']:.1%}",
        "Sharpe (rf=0)": lambda m: f"{m['sharpe']:.2f}",
        "Max drawdown": lambda m: f"{m['max_drawdown']:.1%}",
        "Calmar": lambda m: f"{m['calmar']:.2f}",
        "Turnover / year": lambda m: f"{m['turnover_per_year']:.1f}x",
        "Trades": lambda m: f"{m['n_trades']}",
        "Costs (of start)": lambda m: f"{m['costs_pct_of_start']:.1%}",
        "Avg invested": lambda m: f"{m['avg_exposure']:.0%}",
    }
    return pd.DataFrame({name: {k: f(r.metrics) for k, f in rows.items()} for name, r in results.items()})


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=ROOT / "config.yaml")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    bt = cfg["backtest"]
    prices = load_prices(ROOT / cfg["data"]["prices_file"])
    prices = prices[prices["symbol"].isin(cfg["universe"])]
    close = prices.pivot(index="date", columns="symbol", values="close")
    open_ = prices.pivot(index="date", columns="symbol", values="open")

    log.info("Replaying %d days of the live strategy (~2 min)...", prices["date"].nunique())
    t0 = time.time()
    weights = strategy_weights(prices, cfg["strategy"], start=bt["start"])
    log.info("Weights done in %.0fs", time.time() - t0)

    strat = run_backtest(close, weights, open_=open_, cost_bps=bt["cost_bps"])
    bench = buy_and_hold(close, bt["benchmark"], open_=open_, cost_bps=bt["cost_bps"],
                         start=strat.equity.index[0])
    results = {"Strategy": strat, f"{bt['benchmark']} buy & hold": bench}

    out = ROOT / bt["output_dir"]
    out.mkdir(parents=True, exist_ok=True)
    table = summary_table(results)
    yearly = pd.DataFrame({k: yearly_returns(r.equity) for k, r in results.items()})
    table.to_csv(out / "summary.csv")
    yearly.to_csv(out / "yearly.csv", float_format="%.4f")
    pd.DataFrame({k: r.equity for k, r in results.items()}).to_csv(out / "equity.csv", float_format="%.6f")
    strat.trades.to_csv(out / "trades.csv", index=False, float_format="%.4f")
    held = (strat.weights > 0.01).mean().sort_values(ascending=False)

    print("\n" + table.to_string())
    print("\nCalendar-year returns:\n" + yearly.map(lambda x: f"{x:+.1%}").to_string())
    print("\nShare of days each ETF was held:\n" + held[held > 0].map(lambda x: f"{x:.0%}").to_string())

    try:
        fig = strat.plot(benchmark=bench, title=f"Strategy vs {bt['benchmark']} (costs {bt['cost_bps']} bps/side)")
        fig.savefig(out / "equity.png", dpi=110)
        log.info("Chart saved to %s", out / "equity.png")
    except ImportError:
        log.info("matplotlib not installed - skipping chart")
    return 0


if __name__ == "__main__":
    sys.exit(main())
