"""Price data: fetch, merge and store daily OHLCV for the ETF universe.

Primary source: Yahoo Finance (symbol + ".NS"), which gives split-adjusted history.
Fallback for the latest day: the official NSE CM bhavcopy (UDiFF format).
Prices are stored in one long-format CSV: date, symbol, open, high, low, close, volume, source.
"""
from __future__ import annotations

import io
import logging
import time
import zipfile
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import pandas as pd
import requests

log = logging.getLogger(__name__)

COLUMNS = ["date", "symbol", "open", "high", "low", "close", "volume", "source"]

BHAVCOPY_URL = (
    "https://nsearchives.nseindia.com/content/cm/"
    "BhavCopy_NSE_CM_0_0_0_{d:%Y%m%d}_F_0000.csv.zip"
)
NSE_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 "
    "(KHTML, like Gecko) Chrome/124.0 Safari/537.36",
    "Accept": "*/*",
    "Referer": "https://www.nseindia.com/",
}

IST = timezone(timedelta(hours=5, minutes=30))  # India has no DST, so a fixed offset is exact


def today_ist() -> date:
    """Today's date in India, whatever timezone the machine runs in (GitHub runners are UTC)."""
    return datetime.now(IST).date()


# ---------------------------------------------------------------- storage

def load_prices(path: str | Path) -> pd.DataFrame:
    path = Path(path)
    if not path.exists():
        return pd.DataFrame(columns=COLUMNS)
    df = pd.read_csv(path, parse_dates=["date"])
    return df[COLUMNS]


def save_prices(df: pd.DataFrame, path: str | Path) -> None:
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    df = df.sort_values(["symbol", "date"])
    df.to_csv(path, index=False, date_format="%Y-%m-%d", float_format="%.4f")


def merge_prices(old: pd.DataFrame, new: pd.DataFrame) -> pd.DataFrame:
    """Upsert: rows in `new` replace rows in `old` with the same (date, symbol)."""
    if new.empty:
        return old
    if old.empty:
        return new[COLUMNS].copy()
    combined = pd.concat([old, new[COLUMNS]], ignore_index=True)
    combined = combined.drop_duplicates(subset=["date", "symbol"], keep="last")
    return combined.sort_values(["symbol", "date"]).reset_index(drop=True)


# ---------------------------------------------------------------- sources

def fetch_yahoo(symbols: list[str], start: str | date, end: date | None = None) -> pd.DataFrame:
    """Daily OHLCV from Yahoo Finance. Returns long-format frame (may be empty)."""
    import yfinance as yf  # imported lazily so the rest of the code runs without it

    end = end or today_ist() + timedelta(days=1)
    tickers = [f"{s}.NS" for s in symbols]
    raw = yf.download(
        tickers, start=str(start), end=str(end), auto_adjust=False,
        group_by="ticker", progress=False, threads=True,
    )
    frames = []
    for sym, tkr in zip(symbols, tickers):
        try:
            # yfinance >= 0.2.48 returns (ticker, field) columns even for a single ticker
            sub = raw[tkr] if isinstance(raw.columns, pd.MultiIndex) else raw
        except KeyError:
            log.warning("Yahoo: no data for %s", sym)
            continue
        sub = sub.dropna(subset=["Close"])
        if sub.empty:
            log.warning("Yahoo: empty data for %s", sym)
            continue
        frames.append(pd.DataFrame({
            "date": pd.to_datetime(sub.index).tz_localize(None).normalize(),
            "symbol": sym,
            "open": sub["Open"].values,
            "high": sub["High"].values,
            "low": sub["Low"].values,
            "close": sub["Close"].values,
            "volume": sub["Volume"].values,
            "source": "yahoo",
        }))
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)


def fetch_yahoo_retry(symbols: list[str], start: str | date, attempts: int = 3,
                      wait: float = 10) -> pd.DataFrame:
    """fetch_yahoo, re-requesting symbols that came back empty (Yahoo rate-limits cloud IPs)."""
    frames, todo = [], list(symbols)
    for i in range(attempts):
        try:
            df = fetch_yahoo(todo, start)
        except Exception as e:
            log.warning("Yahoo attempt %d failed: %s", i + 1, e)
            df = pd.DataFrame(columns=COLUMNS)
        if not df.empty:
            frames.append(df)
        todo = [s for s in todo if s not in set(df["symbol"])]
        if not todo:
            break
        if i < attempts - 1:
            log.info("Yahoo: retrying %d symbols in %.0fs: %s", len(todo), wait * (i + 1), todo)
            time.sleep(wait * (i + 1))
    if todo:
        log.warning("Yahoo: no data after %d attempts for %s", attempts, todo)
    return pd.concat(frames, ignore_index=True) if frames else pd.DataFrame(columns=COLUMNS)


def fetch_bhavcopy(d: date, symbols: list[str]) -> pd.DataFrame:
    """One day's prices from the NSE CM bhavcopy. Empty frame on holidays / failures."""
    url = BHAVCOPY_URL.format(d=d)
    try:
        r = requests.get(url, headers=NSE_HEADERS, timeout=30)
        if r.status_code != 200:
            log.warning("Bhavcopy %s: HTTP %s", d, r.status_code)
            return pd.DataFrame(columns=COLUMNS)
        with zipfile.ZipFile(io.BytesIO(r.content)) as z:
            df = pd.read_csv(z.open(z.namelist()[0]))
    except Exception as e:  # network errors, bad zip, blocked IP...
        log.warning("Bhavcopy %s failed: %s", d, e)
        return pd.DataFrame(columns=COLUMNS)
    return parse_bhavcopy(df, symbols)


def parse_bhavcopy(df: pd.DataFrame, symbols: list[str]) -> pd.DataFrame:
    df = df[df["TckrSymb"].isin(symbols) & (df["SctySrs"] == "EQ")]
    return pd.DataFrame({
        "date": pd.to_datetime(df["TradDt"]),
        "symbol": df["TckrSymb"],
        "open": df["OpnPric"],
        "high": df["HghPric"],
        "low": df["LwPric"],
        "close": df["ClsPric"],
        "volume": df["TtlTradgVol"],
        "source": "bhavcopy",
    }).reset_index(drop=True)


# ---------------------------------------------------------------- update

def update_prices(prices: pd.DataFrame, symbols: list[str], history_start: str,
                  today: date | None = None) -> pd.DataFrame:
    """Backfill new symbols, refresh the last ~10 days, fall back to bhavcopy if needed."""
    today = today or today_ist()
    # Backfill symbols with no data, or only the recent-refresh window (a failed earlier backfill)
    first = prices.groupby("symbol")["date"].min() if not prices.empty else pd.Series(dtype="datetime64[ns]")
    cutoff = pd.Timestamp(today - timedelta(days=15))
    missing = [s for s in symbols if s not in first or first[s] > cutoff]

    if missing:
        log.info("Backfilling %d symbols from %s: %s", len(missing), history_start, missing)
        prices = merge_prices(prices, fetch_yahoo_retry(missing, history_start))

    recent_start = today - timedelta(days=10)
    recent = fetch_yahoo_retry(symbols, recent_start)

    # Split/bonus: Yahoo re-adjusts all past prices, so stored history must be replaced, not patched
    resync = adjusted_symbols(prices, recent)
    if resync:
        log.warning("Yahoo re-adjusted past prices for %s (split/bonus?) - re-downloading history", resync)
        full = fetch_yahoo_retry(resync, history_start)
        prices = merge_prices(prices[~prices["symbol"].isin(set(full["symbol"]))], full)
    prices = merge_prices(prices, recent)

    # Fallback: symbols whose latest bar is older than today -> try today's bhavcopy
    if today.weekday() < 5:
        latest = prices.groupby("symbol")["date"].max() if not prices.empty else pd.Series(dtype="datetime64[ns]")
        stale = [s for s in symbols if s not in latest or latest[s].date() < today]
        if stale:
            log.info("Trying bhavcopy for %d stale symbols", len(stale))
            prices = merge_prices(prices, fetch_bhavcopy(today, stale))
    return prices


def adjusted_symbols(old: pd.DataFrame, new: pd.DataFrame, tol: float = 0.02) -> list[str]:
    """Symbols whose new Yahoo closes differ from stored Yahoo closes on the same dates."""
    if old.empty or new.empty:
        return []
    m = old.merge(new, on=["date", "symbol"], suffixes=("_old", "_new"))
    m = m[m["source_old"] == "yahoo"]  # bhavcopy closes are unadjusted, don't compare those
    diff = (m["close_new"] / m["close_old"] - 1).abs()
    return sorted(m.loc[diff > tol, "symbol"].unique())


def sanity_check(prices: pd.DataFrame, max_move: float = 0.25) -> list[str]:
    """Flag suspicious one-day moves (possible bad data or unadjusted split)."""
    warnings = []
    for sym, g in prices.sort_values("date").groupby("symbol"):
        ret = g["close"].pct_change().iloc[-1:] if len(g) > 1 else pd.Series(dtype=float)
        if not ret.empty and abs(ret.iloc[0]) > max_move:
            warnings.append(f"{sym}: last-day move {ret.iloc[0]:+.1%} - check data")
    return warnings
