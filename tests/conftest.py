"""Shared helpers for tests. All tests run offline - network calls are replaced with fakes."""
from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))  # so `import src...` works


def make_prices(spec: dict[str, tuple[float, float, int]], end: str = "2026-11-06") -> pd.DataFrame:
    """Long-format prices. spec = {symbol: (start_price, daily_return, n_days)}; all series end on `end`."""
    rows = []
    for sym, (p0, r, n) in spec.items():
        dates = pd.bdate_range(end=end, periods=n)
        rows.append(pd.DataFrame({
            "date": dates, "symbol": sym,
            "open": np.nan, "high": np.nan, "low": np.nan,
            "close": p0 * (1 + r) ** np.arange(n, dtype=float),
            "volume": 1000.0, "source": "yahoo",
        }))
    return pd.concat(rows, ignore_index=True)
