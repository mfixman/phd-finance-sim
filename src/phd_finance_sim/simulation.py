from __future__ import annotations

from dataclasses import dataclass
from math import erf, exp, sqrt

import numpy as np

from .config import (
    DEFAULT_EXTRA_WITHDRAWALS,
    DEFAULT_INITIAL_BALANCE,
    DEFAULT_QUARTERS,
    PROJECTION_START_QUARTER,
    PROJECTION_START_YEAR,
    DEFAULT_SEED,
    DEFAULT_SIMULATIONS,
    TAX_GAIN_MULTIPLIER,
    TAX_INITIAL_BALANCE_ADJUSTMENT,
)

CHART_PERCENTILES = [95, 90, 75, 50, 25, 10, 5]
TWENTILES = list(range(5, 101, 5))


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


def tax_adjusted_growth_factor(growth_factor: np.ndarray | float) -> np.ndarray | float:
    adjusted = np.where(
        np.asarray(growth_factor) > 1.0,
        1.0 + (np.asarray(growth_factor) - 1.0) * TAX_GAIN_MULTIPLIER,
        np.asarray(growth_factor),
    )
    if np.isscalar(growth_factor):
        return float(adjusted)
    return adjusted


def effective_initial_balance(initial_balance: float, apply_taxes: bool) -> float:
    if not apply_taxes:
        return initial_balance
    return max(initial_balance - TAX_INITIAL_BALANCE_ADJUSTMENT, 0.0)


def standard_normal_cdf(value: float) -> float:
    return 0.5 * (1.0 + erf(value / sqrt(2.0)))


def quarterly_growth_moments(mu: float, sigma: float, apply_taxes: bool) -> tuple[float, float]:
    if sigma == 0.0:
        gross_growth = exp(mu)
        net_growth = tax_adjusted_growth_factor(gross_growth) if apply_taxes else gross_growth
        return float(net_growth), 0.0

    gross_mean = exp(mu + (sigma**2) / 2)
    gross_second_moment = exp(2 * mu + 2 * sigma**2)

    if not apply_taxes:
        return gross_mean, gross_second_moment - gross_mean**2

    probability_gain = standard_normal_cdf(mu / sigma)
    gain_first_moment = gross_mean * standard_normal_cdf((mu + sigma**2) / sigma)
    gain_second_moment = gross_second_moment * standard_normal_cdf((mu + 2 * sigma**2) / sigma)
    loss_first_moment = gross_mean - gain_first_moment
    loss_second_moment = gross_second_moment - gain_second_moment
    carry = 1.0 - TAX_GAIN_MULTIPLIER

    net_mean = loss_first_moment + TAX_GAIN_MULTIPLIER * gain_first_moment + carry * probability_gain
    net_second_moment = (
        loss_second_moment
        + (TAX_GAIN_MULTIPLIER**2) * gain_second_moment
        + 2 * TAX_GAIN_MULTIPLIER * carry * gain_first_moment
        + (carry**2) * probability_gain
    )
    return float(net_mean), float(max(net_second_moment - net_mean**2, 0.0))


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

    for quarter_idx in range(inputs.quarters):
        quarter_number = quarter_idx + 1
        withdrawal = withdrawal_for_quarter(quarter_number, inputs.withdrawal)
        balances = np.maximum(balances - withdrawal, 0.0)
        growth = rng.lognormal(mean=inputs.mu, sigma=inputs.sigma, size=inputs.simulations)
        if inputs.apply_taxes:
            growth = tax_adjusted_growth_factor(growth)
        balances = balances * growth
        all_quarters[:, quarter_idx + 1] = balances

    return all_quarters


def percentile_table(simulated_balances: np.ndarray, percentiles: list[int]) -> np.ndarray:
    return np.percentile(simulated_balances, percentiles, axis=0)


def final_percentile_balance(inputs: SimulationInputs, percentile: int = 5) -> float:
    simulated = simulate_balances(inputs)
    return float(np.percentile(simulated[:, -1], percentile))


def ideal_withdrawal_search(
    inputs: SimulationInputs,
    target_balance: float = 100_000.0,
    percentile: int = 5,
    step: float = 100.0,
    max_withdrawal: float = 500_000.0,
) -> dict[str, float | int | bool]:
    baseline_balance = final_percentile_balance(inputs, percentile=percentile)
    if baseline_balance <= target_balance:
        recommended = 0.0
        achieved = baseline_balance
        return {
            "recommended_withdrawal": recommended,
            "achieved_balance": achieved,
            "target_balance": target_balance,
            "percentile": percentile,
            "within_tolerance": abs(achieved - target_balance) <= step,
        }

    low = 0.0
    high = max(step, inputs.withdrawal, 1_000.0)
    high_result = final_percentile_balance(
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
        percentile=percentile,
    )

    while high_result > target_balance and high < max_withdrawal:
        low = high
        high = min(high * 2, max_withdrawal)
        high_result = final_percentile_balance(
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
            "within_tolerance": False,
        }

    while high - low > step:
        mid = round(((low + high) / 2) / step) * step
        mid_result = final_percentile_balance(
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
        achieved = final_percentile_balance(
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
