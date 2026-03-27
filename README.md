# PhD Finance Simulator

Small planning app for modeling quarterly withdrawals from an S&P 500 investment during a non-working PhD period.

Assumption:

- The request refers to S&P 500 "revenue". This app interprets that as quarterly market gain/return derived from adjusted index closes.

Features:

- Quarterly withdrawal schedule over Q1 to Q16
- Extra withdrawals at Q3 and Q7
- Monte Carlo simulation using lognormal quarterly growth
- Historical S&P 500 quarterly return series from 1980Q1 through 2025Q3
- Start-quarter picker that derives `mu` and `sigma` from historical log gains
- Percentile chart for 5th, 10th, 25th, 50th, 75th, 90th, and 95th percentiles
- 20 x 16 twentile table
- CLI and browser UI powered by the same backend code

## Setup

```bash
python3 -m venv .venv
source .venv/bin/activate
pip install -e .
python scripts/fetch_sp500_history.py
```

## Run

Web app:

```bash
source .venv/bin/activate
uvicorn phd_finance_sim.api:app --host 0.0.0.0 --port 8000
```

CLI:

```bash
source .venv/bin/activate
python -m phd_finance_sim.cli --history-start-quarter 2000Q1
```

## Test

```bash
source .venv/bin/activate
pytest
```
