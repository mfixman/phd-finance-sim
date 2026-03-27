from __future__ import annotations

import numpy as np

from phd_finance_sim.simulation import (
    SimulationInputs,
    ideal_withdrawal_search,
    simulate_balances,
    simulation_payload,
    withdrawal_schedule,
)


def test_withdrawal_schedule_has_expected_extras() -> None:
    schedule = withdrawal_schedule(10_000.0)
    assert schedule[0] == 0.0
    assert schedule[1] == 0.0
    assert schedule[2] == 20_000.0
    assert schedule[6] == 20_000.0
    assert schedule[3] == 10_000.0


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
            [100.0, 100.0, 100.0, 0.0, 0.0],
            [100.0, 100.0, 100.0, 0.0, 0.0],
            [100.0, 100.0, 100.0, 0.0, 0.0],
        ]
    )
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


def test_tax_mode_reduces_effective_initial_balance() -> None:
    payload = simulation_payload(
        SimulationInputs(initial_balance=400_000.0, apply_taxes=True, withdrawal=0.0, mu=0.0, sigma=0.0, simulations=10)
    )
    assert payload["effective_initial_balance"] == 385710.0
    assert payload["chart_percentiles"][3]["values"][0] == 385710.0


def test_ideal_withdrawal_search_hits_target_in_simple_case() -> None:
    result = ideal_withdrawal_search(
        SimulationInputs(initial_balance=260_000.0, withdrawal=0.0, mu=0.0, sigma=0.0, simulations=10, seed=1),
        target_balance=100_000.0,
        step=100.0,
    )
    assert result["recommended_withdrawal"] == 10_800.0
    assert result["achieved_balance"] == 99_600.0
    assert result["target_quarter"] == "Q4 2029"
    assert result["target_timing"] == "beginning"
