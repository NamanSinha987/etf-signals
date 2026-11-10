import pandas as pd

from conftest import make_prices
from src.strategy import compute_features, generate_signals

PARAMS = {"sma_window": 200, "momentum_window": 126, "top_n": 2, "min_history": 210}


def universe():
    return make_prices({
        "FAST": (100, 0.002, 300),     # strong uptrend
        "SLOW": (100, 0.0005, 300),    # mild uptrend
        "DOWN": (100, -0.001, 300),    # below its SMA -> not eligible
        "NEW": (100, 0.005, 100),      # strongest, but too little history
    })


def test_picks_top_n_trending_with_enough_history():
    sig = generate_signals(universe(), PARAMS).set_index("symbol")
    assert set(sig.index[sig["target_weight"] > 0]) == {"FAST", "SLOW"}
    assert sig.loc["FAST", "rank"] == 1
    assert not sig.loc["DOWN", "trend_ok"]
    assert not sig.loc["NEW", "trend_ok"]


def test_actions_relative_to_previous_day():
    previous = pd.DataFrame({"symbol": ["FAST", "DOWN"], "target_weight": [0.5, 0.5]})
    sig = generate_signals(universe(), PARAMS, previous).set_index("symbol")
    assert sig.loc["FAST", "action"] == "HOLD"
    assert sig.loc["SLOW", "action"] == "BUY"
    assert sig.loc["DOWN", "action"] == "SELL"
    assert sig.loc["NEW", "action"] == "-"


def test_all_cash_when_nothing_trends():
    sig = generate_signals(make_prices({"A": (100, -0.001, 300)}), PARAMS)
    assert sig["target_weight"].sum() == 0


def test_last_bar_is_real_not_forward_filled():
    prices = make_prices({"A": (100, 0.001, 300), "B": (100, 0.001, 300)})
    last = prices["date"].max()
    prices = prices[~((prices["symbol"] == "B") & (prices["date"] >= last - pd.Timedelta(days=2)))]
    feats = compute_features(prices, 200, 126).set_index("symbol")
    assert feats.loc["A", "last_bar"] == last
    assert feats.loc["B", "last_bar"] < last
