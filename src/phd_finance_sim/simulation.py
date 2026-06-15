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
    TAX_Q1_WITHDRAWAL,
)

CHART_PERCENTILES = [95, 90, 75, 50, 25, 10, 5]
TWENTILES = list(range(5, 101, 5))
TAX_Q1_WITHDRAWAL_QUARTERS = frozenset(range(0, DEFAULT_QUARTERS, 4))


@dataclass(frozen=True)
class SimulationInputs:
    withdrawal: float
    mu: float
    sigma: float
    initial_balance: float = DEFAULT_INITIAL_BALANCE
    apply_taxes: bool = False
    quarters: int = DEFAULT_QUARTERS
    simulations: int = DEFAULT_SIMULATIONS
    seed: int = DEFAULT_SEED


def withdrawal_for_quarter(quarter_number: int, base_withdrawal: float) -> float:
    if quarter_number < 1:
        return 0.0

    return base_withdrawal + DEFAULT_EXTRA_WITHDRAWALS.get(quarter_number, 0.0)


def withdrawal_schedule(base_withdrawal: float, quarters: int = DEFAULT_QUARTERS) -> list[float]:
    return [withdrawal_for_quarter(quarter, base_withdrawal) for quarter in range(quarters)]


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


def tax_withdrawal_for_quarter(quarter_number: int, apply_taxes: bool) -> float:
    if not apply_taxes:
        return 0.0

    return TAX_Q1_WITHDRAWAL if quarter_number in TAX_Q1_WITHDRAWAL_QUARTERS else 0.0


def effective_initial_balance(initial_balance: float, apply_taxes: bool) -> float:
    return initial_balance


def quarterly_growth_moments(mu: float, sigma: float, apply_taxes: bool) -> tuple[float, float]:
    gross_mean = float(np.exp(mu + (sigma**2) / 2))
    gross_variance = float((np.exp(sigma**2) - 1) * np.exp(2 * mu + sigma**2))
    return gross_mean, gross_variance


def yearly_return_stats_from_quarterly_log_params(mu: float, sigma: float, apply_taxes: bool) -> tuple[float, float]:
    quarter_mean, quarter_variance = quarterly_growth_moments(mu, sigma, apply_taxes)
    second_moment = quarter_variance + quarter_mean**2
    yearly_growth_mean = float(quarter_mean**4)
    yearly_growth_second_moment = float(second_moment**4)
    yearly_growth_variance = max(yearly_growth_second_moment - yearly_growth_mean**2, 0.0)
    return yearly_growth_mean - 1.0, float(np.sqrt(yearly_growth_variance))


def simulate_balances(inputs: SimulationInputs) -> np.ndarray:
    rng = np.random.default_rng(inputs.seed)
    balances = np.full(
        inputs.simulations,
        effective_initial_balance(inputs.initial_balance, inputs.apply_taxes),
        dtype=float,
    )
    all_quarters = np.zeros((inputs.simulations, inputs.quarters + 1), dtype=float)
    all_quarters[:, 0] = balances

    # Store start-of-quarter balances after opening cashflows. Each step
    # advances to the next labelled quarter after the prior period's return and
    # the next quarter's opening withdrawals have been applied.
    for quarter_idx in range(inputs.quarters):
        growth = rng.lognormal(mean=inputs.mu, sigma=inputs.sigma, size=inputs.simulations)
        balances = balances * growth
        withdrawal = withdrawal_for_quarter(quarter_idx, inputs.withdrawal)
        withdrawal += tax_withdrawal_for_quarter(quarter_idx, inputs.apply_taxes)
        balances = np.maximum(balances - withdrawal, 0.0)
        all_quarters[:, quarter_idx + 1] = balances

    return all_quarters


def percentile_table(simulated_balances: np.ndarray, percentiles: list[int]) -> np.ndarray:
    return np.percentile(simulated_balances, percentiles, axis=0)


def percentile_balance_at_index(inputs: SimulationInputs, percentile: int = 5, balance_index: int = -1) -> float:
    simulated = simulate_balances(inputs)
    return float(np.percentile(simulated[:, balance_index], percentile))


def ideal_withdrawal_target_index(inputs: SimulationInputs) -> int:
    return inputs.quarters


def ideal_withdrawal_search(
    inputs: SimulationInputs,
    target_balance: float = 100_000.0,
    percentile: int = 5,
    step: float = 100.0,
    max_withdrawal: float = 500_000.0,
) -> dict[str, float | int | bool | str]:
    target_index = ideal_withdrawal_target_index(inputs)
    target_quarter = projection_quarter_labels(inputs.quarters)[-1]
    baseline_balance = percentile_balance_at_index(inputs, percentile=percentile, balance_index=target_index)
    if baseline_balance <= target_balance:
        recommended = 0.0
        achieved = baseline_balance
        return {
            "recommended_withdrawal": recommended,
            "achieved_balance": achieved,
            "target_balance": target_balance,
            "percentile": percentile,
            "target_quarter": target_quarter,
            "target_timing": "start",
            "within_tolerance": abs(achieved - target_balance) <= step,
        }

    low = 0.0
    high = max(step, inputs.withdrawal, 1_000.0)
    high_result = percentile_balance_at_index(
        SimulationInputs(
            initial_balance=inputs.initial_balance,
            apply_taxes=inputs.apply_taxes,
            withdrawal=high,
            mu=inputs.mu,
            sigma=inputs.sigma,
            quarters=inputs.quarters,
            simulations=inputs.simulations,
            seed=inputs.seed,
        ),
        balance_index=target_index,
        percentile=percentile,
    )

    while high_result > target_balance and high < max_withdrawal:
        low = high
        high = min(high * 2, max_withdrawal)
        high_result = percentile_balance_at_index(
            SimulationInputs(
                initial_balance=inputs.initial_balance,
                apply_taxes=inputs.apply_taxes,
                withdrawal=high,
                mu=inputs.mu,
                sigma=inputs.sigma,
                quarters=inputs.quarters,
                simulations=inputs.simulations,
                seed=inputs.seed,
            ),
            balance_index=target_index,
            percentile=percentile,
        )

    if high_result > target_balance:
        recommended = high
        achieved = high_result
        return {
            "recommended_withdrawal": recommended,
            "achieved_balance": achieved,
            "target_balance": target_balance,
            "percentile": percentile,
            "target_quarter": target_quarter,
            "target_timing": "start",
            "within_tolerance": False,
        }

    while high - low > step:
        mid = round(((low + high) / 2) / step) * step
        mid_result = percentile_balance_at_index(
            SimulationInputs(
                initial_balance=inputs.initial_balance,
                apply_taxes=inputs.apply_taxes,
                withdrawal=mid,
                mu=inputs.mu,
                sigma=inputs.sigma,
                quarters=inputs.quarters,
                simulations=inputs.simulations,
                seed=inputs.seed,
            ),
            balance_index=target_index,
            percentile=percentile,
        )
        if mid_result > target_balance:
            low = mid
        else:
            high = mid

    candidates = sorted({round(value / step) * step for value in (low, high, max(0.0, low - step), high + step)})
    best_withdrawal = 0.0
    best_balance = baseline_balance
    best_distance = abs(baseline_balance - target_balance)
    for candidate in candidates:
        if candidate < 0 or candidate > max_withdrawal:
            continue
        achieved = percentile_balance_at_index(
            SimulationInputs(
                initial_balance=inputs.initial_balance,
                apply_taxes=inputs.apply_taxes,
                withdrawal=candidate,
                mu=inputs.mu,
                sigma=inputs.sigma,
                quarters=inputs.quarters,
                simulations=inputs.simulations,
                seed=inputs.seed,
            ),
            balance_index=target_index,
            percentile=percentile,
        )
        distance = abs(achieved - target_balance)
        if distance < best_distance or (distance == best_distance and candidate < best_withdrawal):
            best_withdrawal = candidate
            best_balance = achieved
            best_distance = distance

    return {
        "recommended_withdrawal": float(best_withdrawal),
        "achieved_balance": float(best_balance),
        "target_balance": target_balance,
        "percentile": percentile,
        "target_quarter": target_quarter,
        "target_timing": "start",
        "within_tolerance": abs(best_balance - target_balance) <= step,
    }


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
        "effective_initial_balance": effective_initial_balance(inputs.initial_balance, inputs.apply_taxes),
        "withdrawal_schedule": withdrawal_schedule(inputs.withdrawal, inputs.quarters),
        "quarters": quarters,
        "chart_percentiles": chart_series,
        "twentiles": twentile_rows,
    }
