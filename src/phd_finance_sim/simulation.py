from __future__ import annotations

from dataclasses import asdict, dataclass, field

import numpy as np

from .config import (
    DEFAULT_INITIAL_BALANCE,
    DEFAULT_MU,
    DEFAULT_SEED,
    DEFAULT_SIGMA,
    DEFAULT_SIMULATIONS,
    PROJECTION_END_QUARTER,
    PROJECTION_END_YEAR,
    PROJECTION_START_QUARTER,
    PROJECTION_START_YEAR,
)

CHART_PERCENTILES = [95, 90, 75, 50, 25, 10, 5]
TWENTILES = list(range(5, 101, 5))
CADENCES = {"once", "quarterly", "annual"}


@dataclass(frozen=True)
class WithdrawalRule:
    name: str
    amount: float
    start_year: int
    start_quarter: int
    end_year: int
    end_quarter: int
    cadence: str = "quarterly"
    special: str | None = None


@dataclass(frozen=True)
class SimulationInputs:
    mu: float = DEFAULT_MU
    sigma: float = DEFAULT_SIGMA
    initial_balance: float = DEFAULT_INITIAL_BALANCE
    start_year: int = PROJECTION_START_YEAR
    start_quarter: int = PROJECTION_START_QUARTER
    end_year: int = PROJECTION_END_YEAR
    end_quarter: int = PROJECTION_END_QUARTER
    withdrawal_rules: tuple[WithdrawalRule, ...] = field(default_factory=tuple)
    goal_year: int = PROJECTION_END_YEAR
    goal_quarter: int = PROJECTION_END_QUARTER
    goal_balance: float = DEFAULT_INITIAL_BALANCE
    goal_percentile: int = 5
    simulations: int = DEFAULT_SIMULATIONS
    seed: int = DEFAULT_SEED


def quarter_index(year: int, quarter: int) -> int:
    if quarter < 1 or quarter > 4:
        raise ValueError(f"Quarter must be between 1 and 4: {quarter}")
    return year * 4 + quarter - 1


def quarter_from_index(index: int) -> tuple[int, int]:
    year, zero_based_quarter = divmod(index, 4)
    return year, zero_based_quarter + 1


def quarter_label(year: int, quarter: int) -> str:
    return f"Q{quarter} {year}"


def compact_quarter_label(year: int, quarter: int) -> str:
    return f"{year}Q{quarter}"


def projection_quarter_labels(
    start_year: int = PROJECTION_START_YEAR,
    start_quarter: int = PROJECTION_START_QUARTER,
    end_year: int = PROJECTION_END_YEAR,
    end_quarter: int = PROJECTION_END_QUARTER,
) -> list[str]:
    start_index = quarter_index(start_year, start_quarter)
    end_index = quarter_index(end_year, end_quarter)
    if end_index < start_index:
        raise ValueError("End quarter must be on or after start quarter")

    labels = []
    for index in range(start_index, end_index + 1):
        year, quarter = quarter_from_index(index)
        labels.append(quarter_label(year, quarter))
    return labels


def validate_rule(rule: WithdrawalRule) -> None:
    if rule.cadence not in CADENCES:
        raise ValueError(f"Unknown withdrawal cadence: {rule.cadence}")
    if quarter_index(rule.end_year, rule.end_quarter) < quarter_index(rule.start_year, rule.start_quarter):
        raise ValueError("Withdrawal rule end quarter must be on or after its start quarter")


def rule_applies_to_quarter(rule: WithdrawalRule, year: int, quarter: int) -> bool:
    validate_rule(rule)
    target_index = quarter_index(year, quarter)
    start_index = quarter_index(rule.start_year, rule.start_quarter)
    end_index = quarter_index(rule.end_year, rule.end_quarter)
    if target_index < start_index or target_index >= end_index:
        return False
    if rule.cadence == "once":
        return target_index == start_index
    if rule.cadence == "annual":
        return (target_index - start_index) % 4 == 0
    return True


def withdrawal_for_quarter(year: int, quarter: int, rules: tuple[WithdrawalRule, ...]) -> float:
    return sum(rule.amount for rule in rules if rule_applies_to_quarter(rule, year, quarter))


def withdrawal_schedule(inputs: SimulationInputs) -> list[float]:
    labels = projection_quarter_labels(
        inputs.start_year,
        inputs.start_quarter,
        inputs.end_year,
        inputs.end_quarter,
    )
    schedule = []
    for label in labels[1:]:
        quarter, year = label.split()
        schedule.append(withdrawal_for_quarter(int(year), int(quarter[1]), inputs.withdrawal_rules))
    return schedule


def effective_initial_balance(initial_balance: float) -> float:
    return initial_balance


def quarterly_growth_moments(mu: float, sigma: float) -> tuple[float, float]:
    gross_mean = float(np.exp(mu + (sigma**2) / 2))
    gross_variance = float((np.exp(sigma**2) - 1) * np.exp(2 * mu + sigma**2))
    return gross_mean, gross_variance


def yearly_return_stats_from_quarterly_log_params(mu: float, sigma: float) -> tuple[float, float]:
    quarter_mean, quarter_variance = quarterly_growth_moments(mu, sigma)
    second_moment = quarter_variance + quarter_mean**2
    yearly_growth_mean = float(quarter_mean**4)
    yearly_growth_second_moment = float(second_moment**4)
    yearly_growth_variance = max(yearly_growth_second_moment - yearly_growth_mean**2, 0.0)
    return yearly_growth_mean - 1.0, float(np.sqrt(yearly_growth_variance))


def simulate_balances(inputs: SimulationInputs) -> np.ndarray:
    labels = projection_quarter_labels(
        inputs.start_year,
        inputs.start_quarter,
        inputs.end_year,
        inputs.end_quarter,
    )
    schedule = withdrawal_schedule(inputs)
    rng = np.random.default_rng(inputs.seed)
    balances = np.full(inputs.simulations, effective_initial_balance(inputs.initial_balance), dtype=float)
    all_quarters = np.zeros((inputs.simulations, len(labels)), dtype=float)
    all_quarters[:, 0] = balances

    # The first displayed quarter is the initial value. Later displayed
    # quarters include the prior period's growth and that quarter's opening
    # withdrawal rules.
    for quarter_idx, withdrawal in enumerate(schedule):
        growth = rng.lognormal(mean=inputs.mu, sigma=inputs.sigma, size=inputs.simulations)
        balances = balances * growth
        balances = np.maximum(balances - withdrawal, 0.0)
        all_quarters[:, quarter_idx + 1] = balances

    return all_quarters


def percentile_table(simulated_balances: np.ndarray, percentiles: list[int]) -> np.ndarray:
    return np.percentile(simulated_balances, percentiles, axis=0)


def percentile_balance_at_index(inputs: SimulationInputs, percentile: int = 5, balance_index: int = -1) -> float:
    simulated = simulate_balances(inputs)
    return float(np.percentile(simulated[:, balance_index], percentile))


def goal_index(inputs: SimulationInputs) -> int:
    labels = projection_quarter_labels(
        inputs.start_year,
        inputs.start_quarter,
        inputs.end_year,
        inputs.end_quarter,
    )
    goal_label = quarter_label(inputs.goal_year, inputs.goal_quarter)
    if goal_label not in labels:
        raise ValueError("Goal quarter must be within the projection range")
    return labels.index(goal_label)


def goal_payload(inputs: SimulationInputs, simulated_balances: np.ndarray) -> dict[str, float | int | str | bool]:
    index = goal_index(inputs)
    actual_balance = float(np.percentile(simulated_balances[:, index], inputs.goal_percentile))
    return {
        "quarter": quarter_label(inputs.goal_year, inputs.goal_quarter),
        "balance": inputs.goal_balance,
        "percentile": inputs.goal_percentile,
        "actual_balance": round(actual_balance, 2),
        "gap": round(actual_balance - inputs.goal_balance, 2),
        "met": actual_balance >= inputs.goal_balance,
    }


def ideal_withdrawal_search(
    inputs: SimulationInputs,
    target_balance: float | None = None,
    percentile: int | None = None,
    step: float = 100.0,
    max_withdrawal: float = 500_000.0,
) -> dict[str, float | int | bool | str]:
    target_balance = inputs.goal_balance if target_balance is None else target_balance
    percentile = inputs.goal_percentile if percentile is None else percentile
    target_index = goal_index(inputs)
    target_quarter = quarter_label(inputs.goal_year, inputs.goal_quarter)
    primary_template = next(
        (rule for rule in inputs.withdrawal_rules if rule.special == "primary_quarterly"),
        None,
    )
    base_rules = tuple(rule for rule in inputs.withdrawal_rules if rule.special != "primary_quarterly")
    base_inputs = SimulationInputs(
        initial_balance=inputs.initial_balance,
        start_year=inputs.start_year,
        start_quarter=inputs.start_quarter,
        end_year=inputs.end_year,
        end_quarter=inputs.end_quarter,
        withdrawal_rules=base_rules,
        goal_year=inputs.goal_year,
        goal_quarter=inputs.goal_quarter,
        goal_balance=inputs.goal_balance,
        goal_percentile=inputs.goal_percentile,
        mu=inputs.mu,
        sigma=inputs.sigma,
        simulations=inputs.simulations,
        seed=inputs.seed,
    )

    def with_quarterly_rule(amount: float) -> SimulationInputs:
        template = primary_template or WithdrawalRule(
            name="Search withdrawal",
            amount=0.0,
            start_year=inputs.start_year,
            start_quarter=inputs.start_quarter,
            end_year=inputs.end_year,
            end_quarter=inputs.end_quarter,
            cadence="quarterly",
            special="primary_quarterly",
        )
        rule = WithdrawalRule(
            name=template.name,
            amount=amount,
            start_year=template.start_year,
            start_quarter=template.start_quarter,
            end_year=template.end_year,
            end_quarter=template.end_quarter,
            cadence="quarterly",
            special="primary_quarterly",
        )
        return SimulationInputs(
            initial_balance=inputs.initial_balance,
            start_year=inputs.start_year,
            start_quarter=inputs.start_quarter,
            end_year=inputs.end_year,
            end_quarter=inputs.end_quarter,
            withdrawal_rules=base_rules + (rule,),
            goal_year=inputs.goal_year,
            goal_quarter=inputs.goal_quarter,
            goal_balance=inputs.goal_balance,
            goal_percentile=inputs.goal_percentile,
            mu=inputs.mu,
            sigma=inputs.sigma,
            simulations=inputs.simulations,
            seed=inputs.seed,
        )

    low = -max_withdrawal
    high = max_withdrawal
    low_result = percentile_balance_at_index(with_quarterly_rule(low), balance_index=target_index, percentile=percentile)
    high_result = percentile_balance_at_index(with_quarterly_rule(high), balance_index=target_index, percentile=percentile)

    if target_balance >= low_result:
        low = high = -max_withdrawal
    elif target_balance <= high_result:
        low = high = max_withdrawal

    while high - low > step:
        mid = round(((low + high) / 2) / step) * step
        mid_result = percentile_balance_at_index(
            with_quarterly_rule(mid), balance_index=target_index, percentile=percentile
        )
        if mid_result > target_balance:
            low = mid
        else:
            high = mid

    candidates = sorted(
        {
            min(max_withdrawal, max(-max_withdrawal, round(value / step) * step))
            for value in (low, high, low - step, high + step, 0.0)
        }
    )
    best_withdrawal = candidates[0]
    best_balance = percentile_balance_at_index(
        with_quarterly_rule(best_withdrawal), balance_index=target_index, percentile=percentile
    )
    best_distance = abs(best_balance - target_balance)
    for candidate in candidates:
        if candidate < -max_withdrawal or candidate > max_withdrawal:
            continue
        achieved = percentile_balance_at_index(
            with_quarterly_rule(candidate), balance_index=target_index, percentile=percentile
        )
        distance = abs(achieved - target_balance)
        if distance < best_distance or (distance == best_distance and abs(candidate) < abs(best_withdrawal)):
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
    quarters = projection_quarter_labels(
        inputs.start_year,
        inputs.start_quarter,
        inputs.end_year,
        inputs.end_quarter,
    )

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
        "inputs": {
            **asdict(inputs),
            "withdrawal_rules": [asdict(rule) for rule in inputs.withdrawal_rules],
        },
        "effective_initial_balance": effective_initial_balance(inputs.initial_balance),
        "withdrawal_schedule": withdrawal_schedule(inputs),
        "quarters": quarters,
        "chart_percentiles": chart_series,
        "twentiles": twentile_rows,
        "goal": goal_payload(inputs, simulated),
    }
