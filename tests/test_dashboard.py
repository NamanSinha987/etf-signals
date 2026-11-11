"""Dashboard page builder: reasons per ETF and a complete, parseable page."""
import json

import pandas as pd

from conftest import make_prices
from src.dashboard import build_html, explain
from src.strategy import generate_signals

PARAMS = {"name": "t", "sma_window": 200, "momentum_window": 126, "top_n": 1, "min_history": 210}
CFG = {"strategy": PARAMS}


def _signals():
    prices = make_prices({"FAST": (100, 0.002, 300), "SLOW": (100, 0.0005, 300),
                          "DOWN": (100, -0.001, 300), "NEW": (100, 0.003, 50)})
    return prices, generate_signals(prices, PARAMS)


def test_explain_covers_every_case():
    _, sig = _signals()
    why = dict(zip(sig["symbol"], sig.apply(explain, axis=1, params=PARAMS)))
    assert "top 1" in why["FAST"] and "Rank 1" in why["FAST"]
    assert "outside the top 1" in why["SLOW"]
    assert "trend filter fails" in why["DOWN"]
    assert "Only 50 days" in why["NEW"]


def _payload(html: str) -> dict:
    start = html.index("const D = ") + len("const D = ")
    return json.loads(html[start:html.index(";\n", start)].replace("<\\/", "</"))


def test_build_html_embeds_data(tmp_path):
    prices, sig = _signals()
    html = build_html(CFG, prices, sig, sig, tmp_path)   # no backtest files in tmp_path
    assert "/*__DATA__*/" not in html
    data = _payload(html)
    assert [s["symbol"] for s in data["signals"]][0] == "FAST"
    assert data["backtest"] is None
    assert len(data["prices"]["FAST"]["dates"]) == 300
    assert data["history"][0]["held"] == ["FAST"]


def test_build_html_reads_backtest(tmp_path):
    prices, sig = _signals()
    eq = pd.DataFrame({"Strategy": [1.0, 1.2, 0.9], "Bench": [1.0, 1.1, 1.1]},
                      index=pd.to_datetime(["2024-12-30", "2024-12-31", "2025-01-02"]))
    eq.to_csv(tmp_path / "equity.csv")
    pd.DataFrame({"Strategy": ["10%"], "Bench": ["5%"]}, index=["CAGR"]).to_csv(tmp_path / "summary.csv")
    pd.DataFrame({"Strategy": [0.2, -0.25], "Bench": [0.1, 0.0]}, index=[2024, 2025]).to_csv(tmp_path / "yearly.csv")
    bt = _payload(build_html(CFG, prices, sig, sig, tmp_path))["backtest"]
    assert bt["summary"]["values"]["Strategy"] == ["10%"]
    assert bt["drawdown"]["Strategy"] == [0.0, 0.0, -0.25]
