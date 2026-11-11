"""Build the static dashboard from stored data (no fetching).

Run:   python dashboard.py      -> output/dashboard/index.html (open it in a browser)
Backtest section appears if output/backtest/ exists (run `python backtest.py` first).
"""
from __future__ import annotations

import argparse
import logging
import sys
from pathlib import Path

import pandas as pd
import yaml

from src.dashboard import build_html
from src.data import load_prices

ROOT = Path(__file__).parent
logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s: %(message)s")
log = logging.getLogger("dashboard")


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--config", default=ROOT / "config.yaml")
    ap.add_argument("--out", default=ROOT / "output" / "dashboard" / "index.html")
    args = ap.parse_args()

    cfg = yaml.safe_load(Path(args.config).read_text(encoding="utf-8"))
    latest_path = ROOT / cfg["output"]["latest_file"]
    if not latest_path.exists():
        log.error("No signals yet - run pipeline.py first")
        return 1
    prices = load_prices(ROOT / cfg["data"]["prices_file"])
    prices = prices[prices["symbol"].isin(cfg["universe"])]
    signals = pd.read_csv(latest_path, parse_dates=["asof", "last_bar"])
    history = pd.read_csv(ROOT / cfg["output"]["history_file"], parse_dates=["asof"])

    html = build_html(cfg, prices, signals, history, ROOT / cfg["backtest"]["output_dir"])
    out = Path(args.out)
    out.parent.mkdir(parents=True, exist_ok=True)
    out.write_text(html, encoding="utf-8")
    log.info("Dashboard written to %s (%.0f KB)", out, out.stat().st_size / 1024)
    return 0


if __name__ == "__main__":
    sys.exit(main())
