# AGENTS.md

This repository contains a small finance-planning tool for modeling portfolio withdrawals over configurable quarters.

Follow these repo-specific rules in addition to `/home/mfixman/AGENTS.md`:

- Keep the project as a Python repository with three clear layers:
  - backend simulation/data code in `src/phd_finance_sim/`
  - CLI entry points in `src/phd_finance_sim/cli.py`
  - GUI/web app in `src/phd_finance_sim/api.py` plus `src/phd_finance_sim/static/`
- Treat the historical S&P 500 dataset in `data/` as generated artefacts:
  - commit the CSV that the app reads
  - keep the fetch/transformation logic in `scripts/fetch_sp500_history.py`
- Prefer deterministic tests for the simulation engine. Avoid tests that depend on live network access.
- When you change the web app, run at least the Python tests and a local server start check.
- Bind the dev server to `0.0.0.0` unless the user explicitly asks otherwise.
