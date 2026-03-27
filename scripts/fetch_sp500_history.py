from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import yfinance as yf

PROJECT_ROOT = Path(__file__).resolve().parents[1]
OUTPUT_FILE = PROJECT_ROOT / "data" / "sp500_quarterly_returns.csv"
TOTAL_RETURN_TICKER = "^SP500TR"


def latest_completed_quarter_end() -> str:
    current_date = pd.Timestamp.now(tz="UTC").tz_localize(None)
    return current_date.to_period("Q").start_time.strftime("%Y-%m-%d")


def fetch_quarterly_returns() -> pd.DataFrame:
    history = yf.download(
        TOTAL_RETURN_TICKER,
        start="1980-01-01",
        end=latest_completed_quarter_end(),
        auto_adjust=False,
        progress=False,
        interval="1d",
    )
    if history.empty:
        raise RuntimeError("No S&P 500 total return data returned from Yahoo Finance.")

    if isinstance(history.columns, pd.MultiIndex):
        history.columns = history.columns.get_level_values(0)

    frame = history.reset_index()[["Date", "Close"]].rename(columns={"Date": "date", "Close": "close"})
    frame["quarter"] = frame["date"].dt.to_period("Q").astype(str)

    quarterly = (
        frame.groupby("quarter", as_index=False)
        .agg(
            start_date=("date", "first"),
            end_date=("date", "last"),
            start_close=("close", "first"),
            end_close=("close", "last"),
        )
        .sort_values("quarter")
    )
    quarterly["growth_factor"] = quarterly["end_close"] / quarterly["start_close"]
    quarterly["quarter_return"] = quarterly["growth_factor"] - 1.0
    quarterly["log_gain"] = np.log(quarterly["growth_factor"])
    quarterly["source_ticker"] = TOTAL_RETURN_TICKER
    return quarterly


def main() -> None:
    quarterly = fetch_quarterly_returns()
    OUTPUT_FILE.parent.mkdir(parents=True, exist_ok=True)
    quarterly.to_csv(OUTPUT_FILE, index=False)
    print(f"Wrote {len(quarterly)} quarterly rows to {OUTPUT_FILE}")


if __name__ == "__main__":
    main()
