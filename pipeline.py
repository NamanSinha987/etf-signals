"""Daily pipeline: update prices -> generate signals -> save -> notify.

Run locally:   python pipeline.py
Skip fetching (use stored data only):   python pipeline.py --no-fetch
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
import yaml

from src.data import expected_session, load_prices, sanity_check, save_prices, update_prices
from src.notify import format_message, send_telegram
from src.strategy import generate_signals

ROOT = Path(__file__).parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("pipeline")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=ROOT / "config.yaml")
    ap.add_argument("--no-fetch", action="store_true", help="use stored prices only")
    ap.add_argument("--no-notify", action="store_true")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text())
    symbols = cfg["universe"]
    prices_path = ROOT / cfg["data"]["prices_file"]

    # 1. Data
    prices = load_prices(prices_path)
    if not args.no_fetch:
        prices = update_prices(prices, symbols, cfg["data"]["history_start"])
        save_prices(prices, prices_path)
    prices = prices[prices["symbol"].isin(symbols)]
    if prices.empty:
        log.error("No price data available - aborting")
        return 1
    log.info("Prices: %d rows, %d symbols, last date %s",
             len(prices), prices["symbol"].nunique(), prices["date"].max().date())

    # 2. Signals
    latest_path = ROOT / cfg["output"]["latest_file"]
    history_path = ROOT / cfg["output"]["history_file"]
    previous = pd.read_csv(latest_path) if latest_path.exists() else None
    signals = generate_signals(prices, cfg["strategy"], previous)

    # Don't re-issue signals for a date we already processed (holidays, re-runs)
    asof = signals["asof"].iloc[0]
    if previous is not None and pd.Timestamp(previous["asof"].iloc[0]) == asof:
        log.info("Signals for %s already generated; recomputing without changing actions", asof.date())
        signals = generate_signals(prices, cfg["strategy"], _prior_day(history_path, asof))

    warnings = sanity_check(prices)
    stale = signals[pd.to_datetime(signals["last_bar"]) < asof]["symbol"].tolist()
    if stale:
        warnings.append(f"Stale data (no bar on {asof.date()}): {', '.join(stale)}")
    session = expected_session()
    if not args.no_fetch and asof.date() < session:
        warnings.insert(0, f"NO NEW PRICES for {session:%d %b} - market holiday or data source "
                           f"failure. These signals are from {asof:%d %b}.")

    # 3. Save
    latest_path.parent.mkdir(parents=True, exist_ok=True)
    signals.to_csv(latest_path, index=False, date_format="%Y-%m-%d", float_format="%.4f")
    _append_history(signals, history_path)

    # 4. Notify
    msg = format_message(signals, warnings)
    print("\n" + msg + "\n")
    if not args.no_notify:
        send_telegram(msg, link=cfg.get("dashboard", {}).get("url"))
    return 0


def _prior_day(history_path: Path, asof: pd.Timestamp) -> pd.DataFrame | None:
    if not history_path.exists():
        return None
    hist = pd.read_csv(history_path, parse_dates=["asof"])
    prior = hist[hist["asof"] < asof]
    return prior[prior["asof"] == prior["asof"].max()] if not prior.empty else None


def _append_history(signals: pd.DataFrame, path: Path) -> None:
    if path.exists():
        hist = pd.read_csv(path, parse_dates=["asof"])
        hist = hist[hist["asof"] != signals["asof"].iloc[0]]
        hist = pd.concat([hist, signals], ignore_index=True) if not hist.empty else signals
    else:
        hist = signals
    hist.to_csv(path, index=False, date_format="%Y-%m-%d", float_format="%.4f")


if __name__ == "__main__":
    sys.exit(main())
