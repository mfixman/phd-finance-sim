from __future__ import annotations

import numpy as np

from phd_finance_sim.simulation import (
    SimulationInputs,
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
        SimulationInputs(withdrawal=5_000.0, mu=0.01, sigma=0.02, simulations=100, seed=1)
    )
    assert payload["quarters"][0] == "Q4 2026"
    assert payload["quarters"][-1] == "Q4 2029"
    assert len(payload["quarters"]) == 13
    assert len(payload["chart_percentiles"]) == 7
    assert len(payload["twentiles"]) == 20
    assert payload["twentiles"][0]["percentile"] == 5
    assert len(payload["twentiles"][0]["values"]) == 13
