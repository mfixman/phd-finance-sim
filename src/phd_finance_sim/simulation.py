from __future__ import annotations

from dataclasses import dataclass

import numpy as np

from .config import (
    DEFAULT_EXTRA_WITHDRAWALS,
    DEFAULT_INITIAL_BALANCE,
    DEFAULT_QUARTERS,
    PROJECTION_START_QUARTER,
    PROJECTION_START_YEAR,
    DEFAULT_SEED,
    DEFAULT_SIMULATIONS,
)

CHART_PERCENTILES = [95, 90, 75, 50, 25, 10, 5]
TWENTILES = list(range(5, 101, 5))


@dataclass(frozen=True)
class SimulationInputs:
    withdrawal: float
    mu: float
    sigma: float
    initial_balance: float = DEFAULT_INITIAL_BALANCE
    quarters: int = DEFAULT_QUARTERS
    simulations: int = DEFAULT_SIMULATIONS
    seed: int = DEFAULT_SEED


def withdrawal_for_quarter(quarter_number: int, base_withdrawal: float) -> float:
    if quarter_number < 3:
        return 0.0

    return base_withdrawal + DEFAULT_EXTRA_WITHDRAWALS.get(quarter_number, 0.0)


def withdrawal_schedule(base_withdrawal: float, quarters: int = DEFAULT_QUARTERS) -> list[float]:
    return [withdrawal_for_quarter(quarter, base_withdrawal) for quarter in range(1, quarters + 1)]


def projection_quarter_labels(
    quarters: int,
    start_year: int = PROJECTION_START_YEAR,
    start_quarter: int = PROJECTION_START_QUARTER,
) -> list[str]:
    labels = []
    year = start_year
    quarter = start_quarter

    for _ in range(quarters + 1):
        labels.append(f"Q{quarter} {year}")
        quarter += 1
        if quarter == 5:
            quarter = 1
            year += 1

    return labels


def simulate_balances(inputs: SimulationInputs) -> np.ndarray:
    rng = np.random.default_rng(inputs.seed)
    balances = np.full(inputs.simulations, inputs.initial_balance, dtype=float)
    all_quarters = np.zeros((inputs.simulations, inputs.quarters + 1), dtype=float)
    all_quarters[:, 0] = balances

    for quarter_idx in range(inputs.quarters):
        quarter_number = quarter_idx + 1
        withdrawal = withdrawal_for_quarter(quarter_number, inputs.withdrawal)
        balances = np.maximum(balances - withdrawal, 0.0)
        growth = rng.lognormal(mean=inputs.mu, sigma=inputs.sigma, size=inputs.simulations)
        balances = balances * growth
        all_quarters[:, quarter_idx + 1] = balances

    return all_quarters


def percentile_table(simulated_balances: np.ndarray, percentiles: list[int]) -> np.ndarray:
    return np.percentile(simulated_balances, percentiles, axis=0)


def simulation_payload(inputs: SimulationInputs) -> dict[str, object]:
    simulated = simulate_balances(inputs)
    chart_values = percentile_table(simulated, CHART_PERCENTILES)
    twentile_values = percentile_table(simulated, TWENTILES)
    quarters = projection_quarter_labels(inputs.quarters)

    chart_series = []
    for index, percentile in enumerate(CHART_PERCENTILES):
        chart_series.append(
            {
                "percentile": percentile,
                "quarter_labels": quarters,
                "values": chart_values[index].round(2).tolist(),
            }
        )

    twentile_rows = []
    for index, percentile in enumerate(TWENTILES):
        twentile_rows.append(
            {
                "percentile": percentile,
                "values": twentile_values[index].round(2).tolist(),
            }
        )

    return {
        "inputs": inputs.__dict__,
        "withdrawal_schedule": withdrawal_schedule(inputs.withdrawal, inputs.quarters),
        "quarters": quarters,
        "chart_percentiles": chart_series,
        "twentiles": twentile_rows,
    }
