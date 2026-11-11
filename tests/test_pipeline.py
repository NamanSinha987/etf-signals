"""End-to-end runs of pipeline.main() in a temp folder, with data fetching faked."""
import sys
from datetime import date

import pandas as pd
import yaml

import pipeline
from conftest import make_prices

CONFIG = {
    "universe": ["FAST", "SLOW", "DOWN"],
    "data": {"history_start": "2018-01-01", "prices_file": "data/prices.csv"},
    "strategy": {"name": "t", "sma_window": 200, "momentum_window": 126, "top_n": 2, "min_history": 210},
    "output": {"signals_dir": "signals", "latest_file": "signals/latest.csv",
               "history_file": "signals/history.csv"},
}


def setup(tmp_path, monkeypatch, today):
    (tmp_path / "data").mkdir()
    (tmp_path / "config.yaml").write_text(yaml.safe_dump(CONFIG))
    prices = make_prices({"FAST": (100, 0.002, 300), "SLOW": (100, 0.0005, 300),
                          "DOWN": (100, -0.001, 300)}, end="2026-11-06")
    prices.to_csv(tmp_path / "data/prices.csv", index=False)
    monkeypatch.setattr(pipeline, "ROOT", tmp_path)
    monkeypatch.setattr(pipeline, "update_prices", lambda p, *a, **k: p)   # no network
    monkeypatch.setattr(pipeline, "expected_session", lambda: today)
    monkeypatch.setattr(sys, "argv", ["pipeline.py", "--no-notify"])


def test_run_writes_signals(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch, date(2026, 11, 6))
    assert pipeline.main() == 0
    latest = pd.read_csv(tmp_path / "signals/latest.csv")
    assert set(latest.loc[latest["target_weight"] > 0, "symbol"]) == {"FAST", "SLOW"}
    assert "NO NEW PRICES" not in capsys.readouterr().out


def test_rerun_same_day_keeps_actions(tmp_path, monkeypatch):
    setup(tmp_path, monkeypatch, date(2026, 11, 6))
    pipeline.main()
    pipeline.main()   # holiday / re-run: same last bar
    latest = pd.read_csv(tmp_path / "signals/latest.csv")
    assert set(latest.loc[latest["target_weight"] > 0, "action"]) == {"BUY"}   # not flipped to HOLD
    assert len(pd.read_csv(tmp_path / "signals/history.csv")) == 3            # one day, not two


def test_warns_when_no_new_prices(tmp_path, monkeypatch, capsys):
    setup(tmp_path, monkeypatch, date(2026, 11, 9))   # Monday, but last bar is Friday
    pipeline.main()
    assert "NO NEW PRICES for 09 Nov" in capsys.readouterr().out
