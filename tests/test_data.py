from datetime import date

import pandas as pd
import pytest

import src.data as data
from conftest import make_prices


def test_merge_prices_new_rows_replace_old():
    old = make_prices({"A": (100, 0, 3)})
    new = old.tail(1).assign(close=999.0)
    out = data.merge_prices(old, new)
    assert len(out) == 3
    assert out["close"].iloc[-1] == 999.0


def test_parse_bhavcopy_keeps_only_universe_eq_rows():
    raw = pd.DataFrame({
        "TradDt": ["2026-11-06"] * 3, "TckrSymb": ["GOLDBEES", "GOLDBEES", "RELIANCE"],
        "SctySrs": ["EQ", "BL", "EQ"], "OpnPric": [1, 2, 3], "HghPric": [1, 2, 3],
        "LwPric": [1, 2, 3], "ClsPric": [1, 2, 3], "TtlTradgVol": [10, 20, 30],
    })
    out = data.parse_bhavcopy(raw, ["GOLDBEES"])
    assert list(out["symbol"]) == ["GOLDBEES"]
    assert out["source"].iloc[0] == "bhavcopy"


def yahoo_frame(tickers):
    """What yf.download returns with group_by='ticker': (ticker, field) columns, even for one ticker."""
    idx = pd.bdate_range("2026-11-02", periods=3)
    fields = ["Open", "High", "Low", "Close", "Adj Close", "Volume"]
    cols = pd.MultiIndex.from_product([tickers, fields])
    return pd.DataFrame(100.0, index=idx, columns=cols)


@pytest.mark.parametrize("symbols", [["GOLDBEES"], ["GOLDBEES", "NIFTYBEES"]])
def test_fetch_yahoo_single_and_multiple_tickers(monkeypatch, symbols):
    import yfinance
    monkeypatch.setattr(yfinance, "download", lambda tickers, **kw: yahoo_frame(tickers))
    out = data.fetch_yahoo(symbols, "2026-11-01")
    assert sorted(out["symbol"].unique()) == sorted(symbols)
    assert len(out) == 3 * len(symbols)


def test_retry_refetches_only_missing_symbols(monkeypatch):
    calls = []

    def flaky(symbols, start, end=None):
        calls.append(list(symbols))
        if len(calls) == 1:
            symbols = [s for s in symbols if s != "B"]   # B fails the first time
        return make_prices({s: (100, 0, 3) for s in symbols})

    monkeypatch.setattr(data, "fetch_yahoo", flaky)
    out = data.fetch_yahoo_retry(["A", "B"], "2026-11-01", wait=0)
    assert calls == [["A", "B"], ["B"]]
    assert set(out["symbol"]) == {"A", "B"}


def test_adjusted_symbols_detects_rewritten_history():
    stored = make_prices({"A": (100, 0, 10), "B": (100, 0, 10)})
    fresh = stored.copy()
    fresh.loc[fresh["symbol"] == "A", "close"] /= 10        # A split 1:10
    assert data.adjusted_symbols(stored, fresh) == ["A"]
    stored["source"] = "bhavcopy"                            # unadjusted source: never compared
    assert data.adjusted_symbols(stored, fresh) == []


class FakeYahoo:
    """Serves slices of a 'true' price history and records what was requested."""

    def __init__(self, truth):
        self.truth, self.requests = truth, []

    def __call__(self, symbols, start, **kw):
        self.requests.append((sorted(symbols), str(start)))
        t = self.truth
        return t[t["symbol"].isin(symbols) & (t["date"] >= pd.Timestamp(start))].copy()


def run_update(monkeypatch, stored, truth, symbols):
    fake = FakeYahoo(truth)
    monkeypatch.setattr(data, "fetch_yahoo_retry", fake)
    monkeypatch.setattr(data, "fetch_bhavcopy", lambda d, s: pd.DataFrame(columns=data.COLUMNS))
    out = data.update_prices(stored, symbols, "2018-01-01", today=date(2026, 11, 6))
    return out, fake.requests


def test_update_backfills_symbol_with_only_recent_rows(monkeypatch):
    truth = make_prices({"A": (100, 0.001, 300), "B": (100, 0.001, 300)})
    stored = pd.concat([truth[truth["symbol"] == "A"], truth[truth["symbol"] == "B"].tail(5)])
    out, requests = run_update(monkeypatch, stored, truth, ["A", "B"])
    assert (["B"], "2018-01-01") in requests
    assert (out["symbol"] == "B").sum() == 300


def test_update_replaces_history_after_split(monkeypatch):
    truth = make_prices({"A": (100, 0.001, 300), "B": (100, 0.001, 300)})
    stored = truth.copy()
    stored.loc[stored["symbol"] == "A", "close"] *= 10      # stored = pre-split prices
    out, requests = run_update(monkeypatch, stored, truth, ["A", "B"])
    assert (["A"], "2018-01-01") in requests
    merged = out.merge(truth, on=["date", "symbol"], suffixes=("", "_true"))
    assert (merged["close"] == merged["close_true"]).all()
