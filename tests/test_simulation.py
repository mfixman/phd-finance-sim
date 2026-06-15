from __future__ import annotations

import numpy as np

from phd_finance_sim.simulation import (
    SimulationInputs,
    ideal_withdrawal_search,
    simulate_balances,
    simulation_payload,
    tax_withdrawal_for_quarter,
    withdrawal_schedule,
)


def test_withdrawal_schedule_has_expected_extras() -> None:
    schedule = withdrawal_schedule(10_000.0)
    assert schedule[0] == 0.0
    assert schedule[1] == 0.0
    assert schedule[2] == 0.0
    assert schedule[3] == 20_000.0
    assert schedule[7] == 20_000.0
    assert schedule[4] == 10_000.0


def test_simulation_is_deterministic_when_sigma_is_zero() -> None:
    inputs = SimulationInputs(
        withdrawal=10_000.0,
        mu=0.0,
        sigma=0.0,
        initial_balance=100.0,
        quarters=4,
        simulations=3,
        seed=7,
    )
    simulated = simulate_balances(inputs)
    expected = np.array(
        [
            [100.0, 100.0, 100.0, 100.0, 0.0],
            [100.0, 100.0, 100.0, 100.0, 0.0],
            [100.0, 100.0, 100.0, 100.0, 0.0],
        ]
    )
    np.testing.assert_allclose(simulated, expected)


def test_simulation_stores_start_of_quarter_values() -> None:
    inputs = SimulationInputs(
        withdrawal=0.0,
        mu=0.0,
        sigma=0.0,
        initial_balance=25_000.0,
        quarters=4,
        simulations=1,
        seed=7,
    )
    simulated = simulate_balances(inputs)
    expected = np.array([[25_000.0, 25_000.0, 25_000.0, 25_000.0, 15_000.0]])
    np.testing.assert_allclose(simulated, expected)


def test_payload_contains_twentile_rows_for_each_quarter() -> None:
    payload = simulation_payload(
        SimulationInputs(initial_balance=400_000.0, withdrawal=5_000.0, mu=0.01, sigma=0.02, simulations=100, seed=1)
    )
    assert payload["quarters"][0] == "Q4 2025"
    assert payload["quarters"][-1] == "Q4 2029"
    assert len(payload["quarters"]) == 17
    assert payload["chart_percentiles"][3]["values"][0] == 400000.0
    assert len(payload["chart_percentiles"]) == 7
    assert len(payload["twentiles"]) == 20
    assert payload["twentiles"][0]["percentile"] == 5
    assert len(payload["twentiles"][0]["values"]) == 17


def test_tax_mode_keeps_initial_balance_and_withdraws_before_q1() -> None:
    payload = simulation_payload(
        SimulationInputs(
            initial_balance=400_000.0,
            apply_taxes=True,
            withdrawal=0.0,
            mu=0.0,
            sigma=0.0,
            quarters=2,
            simulations=10,
        )
    )
    assert payload["effective_initial_balance"] == 400_000.0
    assert payload["chart_percentiles"][3]["values"] == [400_000.0, 396_500.0, 396_500.0]


def test_tax_mode_does_not_scale_investment_growth() -> None:
    simulated = simulate_balances(
        SimulationInputs(
            initial_balance=100_000.0,
            apply_taxes=True,
            withdrawal=0.0,
            mu=np.log(1.10),
            sigma=0.0,
            quarters=1,
            simulations=1,
        )
    )
    np.testing.assert_allclose(simulated, [[100_000.0, 106_500.0]])


def test_tax_withdrawals_apply_before_each_q1() -> None:
    assert [tax_withdrawal_for_quarter(quarter, True) for quarter in range(13)] == [
        3_500.0,
        0.0,
        0.0,
        0.0,
        3_500.0,
        0.0,
        0.0,
        0.0,
        3_500.0,
        0.0,
        0.0,
        0.0,
        3_500.0,
    ]
    assert tax_withdrawal_for_quarter(0, False) == 0.0
    assert tax_withdrawal_for_quarter(16, True) == 0.0


def test_ideal_withdrawal_search_hits_target_in_simple_case() -> None:
    result = ideal_withdrawal_search(
        SimulationInputs(initial_balance=260_000.0, withdrawal=0.0, mu=0.0, sigma=0.0, simulations=10, seed=1),
        target_balance=100_000.0,
        step=100.0,
    )
    assert result["recommended_withdrawal"] == 10_800.0
    assert result["achieved_balance"] == 99_600.0
    assert result["target_quarter"] == "Q4 2029"
    assert result["target_timing"] == "start"
