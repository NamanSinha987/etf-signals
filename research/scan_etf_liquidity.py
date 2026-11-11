"""Liquidity scan of every NSE-listed ETF, from the local bhavcopy archive + AMFI scheme names.

ETFs are CM rows with an INF... ISIN (mutual fund units) in series EQ. Liquidity = median daily
traded value over the last `--months` months; ETFs missing on >10% of those days are dropped.
Names come from AMFI's daily NAV file (ISIN -> scheme name), downloaded fresh.

Run:   python research/scan_etf_liquidity.py [--archive D:/NotWindows/Quant2.0/data/export]
Writes research/etf_liquidity.csv - input for hand-curating research/universe.csv.
"""
from __future__ import annotations

import argparse
import io
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).parent
AMFI_URL = "https://portal.amfiindia.com/spages/NAVAll.txt"


def amfi_names() -> dict[str, str]:
    text = requests.get(AMFI_URL, timeout=90, headers={"User-Agent": "Mozilla/5.0"}).text
    nav = pd.read_csv(io.StringIO(text), sep=";", dtype=str, on_bad_lines="skip")
    nav = nav[nav["Scheme Code"].str.isdigit().fillna(False)]
    names = {}
    for col in ("ISIN Div Payout/ ISIN Growth", "ISIN Div Reinvestment"):
        for isin, name in zip(nav[col], nav["Scheme Name"]):
            if isinstance(isin, str) and isin.startswith("INF"):
                names[isin] = name
    return names


def scan(archive: Path, months: int = 6) -> pd.DataFrame:
    cols = ["date", "symbol", "series", "isin", "close", "turnover_inr", "trades"]
    cm = pd.concat([pd.read_parquet(f, columns=cols) for f in sorted(archive.glob("cm_*.parquet"))])
    etf = cm[cm["isin"].str.startswith("INF", na=False) & (cm["series"] == "EQ")]
    end = etf["date"].max()
    recent = etf[etf["date"] > end - pd.DateOffset(months=months)]
    out = recent.groupby("symbol").agg(
        median_value_cr=("turnover_inr", lambda s: s.median() / 1e7),
        median_trades=("trades", "median"),
        days=("date", "nunique"),
        close=("close", "last"),
        isin=("isin", "last"),
    )
    out = out[out["days"] >= 0.9 * recent["date"].nunique()]
    out["first_in_archive"] = etf.groupby("symbol")["date"].min()
    out["name"] = out["isin"].map(amfi_names())
    out.attrs["end"] = end
    return out.sort_values("median_value_cr", ascending=False)


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--archive", default=HERE.parents[1] / "data" / "export", type=Path)
    ap.add_argument("--months", default=6, type=int)
    args = ap.parse_args()
    out = scan(args.archive, args.months)
    out.round(2).to_csv(HERE / "etf_liquidity.csv", date_format="%Y-%m-%d")
    print(f"{len(out)} ETFs traded through {out.attrs['end']:%d %b %Y}; "
          f"{(out['median_value_cr'] >= 1).sum()} with median value >= Rs 1 cr/day")


if __name__ == "__main__":
    main()
