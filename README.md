# Unemployment Withdrawal Simulator

Small planning app for modeling portfolio balances during an unemployment or non-working period.

Features:

- Configurable initial value, projection start quarter, and projection end quarter
- Arbitrary withdrawal rules with one-off, quarterly, or annual cadence
- Configurable goal defined by quarter, percentile, and target balance
- Monte Carlo simulation using lognormal quarterly growth
- Historical S&P 500 quarterly return series for deriving `mu` and `sigma`
- Browser import/export for `values.json`
- Percentile chart and twentile table
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
