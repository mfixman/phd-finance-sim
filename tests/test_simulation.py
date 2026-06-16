from __future__ import annotations

import numpy as np

from phd_finance_sim.simulation import (
    SimulationInputs,
    WithdrawalRule,
    ideal_withdrawal_search,
    simulate_balances,
    simulation_payload,
    withdrawal_schedule,
)


def test_withdrawal_schedule_combines_arbitrary_rules() -> None:
    inputs = SimulationInputs(
        withdrawal_rules=(
            WithdrawalRule("Quarterly", 1_200.0, 2026, 2, 2027, 4, "quarterly"),
            WithdrawalRule("Annual", 750.0, 2026, 1, 2027, 1, "annual"),
            WithdrawalRule("One-off", 2_500.0, 2026, 3, 2026, 4, "once"),
        )
    )

    assert withdrawal_schedule(inputs)[:8] == [
        750.0,
        1_200.0,
        3_700.0,
        1_200.0,
        1_200.0,
        1_200.0,
        1_200.0,
        0,
    ]


def test_simulation_is_deterministic_when_sigma_is_zero() -> None:
    inputs = SimulationInputs(
        initial_balance=100.0,
        start_year=2025,
        start_quarter=4,
        end_year=2026,
        end_quarter=4,
        withdrawal_rules=(WithdrawalRule("Quarterly", 10.0, 2026, 1, 2027, 1, "quarterly"),),
        mu=0.0,
        sigma=0.0,
        simulations=3,
        seed=7,
    )
    simulated = simulate_balances(inputs)
    expected = np.array(
        [
            [100.0, 90.0, 80.0, 70.0, 60.0],
            [100.0, 90.0, 80.0, 70.0, 60.0],
            [100.0, 90.0, 80.0, 70.0, 60.0],
        ]
    )
    np.testing.assert_allclose(simulated, expected)


def test_negative_withdrawal_increases_balance() -> None:
    inputs = SimulationInputs(
        initial_balance=100.0,
        start_year=2025,
        start_quarter=4,
        end_year=2026,
        end_quarter=1,
        withdrawal_rules=(WithdrawalRule("Salary", -10.0, 2026, 1, 2026, 2),),
        mu=0.0,
        sigma=0.0,
        simulations=3,
        seed=7,
    )
    simulated = simulate_balances(inputs)
    np.testing.assert_allclose(simulated[:, 1], [110.0, 110.0, 110.0])


def test_payload_contains_twentile_rows_for_each_quarter_and_goal() -> None:
    payload = simulation_payload(
        SimulationInputs(
            initial_balance=400_000.0,
            start_year=2026,
            start_quarter=1,
            end_year=2026,
            end_quarter=4,
            goal_year=2026,
            goal_quarter=4,
            goal_balance=350_000.0,
            goal_percentile=25,
            mu=0.01,
            sigma=0.02,
            simulations=100,
            seed=1,
        )
    )
    assert payload["quarters"] == ["Q1 2026", "Q2 2026", "Q3 2026", "Q4 2026"]
    assert payload["chart_percentiles"][3]["values"][0] == 400000.0
    assert len(payload["chart_percentiles"]) == 7
    assert len(payload["twentiles"]) == 20
    assert payload["twentiles"][0]["percentile"] == 5
    assert len(payload["twentiles"][0]["values"]) == 4
    assert payload["goal"]["quarter"] == "Q4 2026"
    assert payload["goal"]["percentile"] == 25


def test_projection_end_is_final_boundary_for_half_open_range() -> None:
    inputs = SimulationInputs(
        initial_balance=100.0,
        start_year=2025,
        start_quarter=4,
        end_year=2029,
        end_quarter=4,
        withdrawal_rules=(WithdrawalRule("Quarterly", 1.0, 2025, 4, 2029, 4, "quarterly"),),
        goal_year=2029,
        goal_quarter=4,
        mu=0.0,
        sigma=0.0,
        simulations=3,
        seed=1,
    )
    payload = simulation_payload(inputs)
    assert payload["quarters"][0] == "Q4 2025"
    assert payload["quarters"][-1] == "Q4 2029"
    assert len(payload["quarters"]) == 17
    assert len(payload["withdrawal_schedule"]) == 16
    assert payload["withdrawal_schedule"][-1] == 0.0
    assert payload["goal"]["quarter"] == "Q4 2029"


def test_annual_rule_repeats_on_same_quarter_each_year() -> None:
    inputs = SimulationInputs(
        start_year=2025,
        start_quarter=4,
        end_year=2028,
        end_quarter=1,
        withdrawal_rules=(WithdrawalRule("Annual", 750.0, 2026, 1, 2028, 1, "annual"),),
    )
    assert withdrawal_schedule(inputs) == [750.0, 0, 0, 0, 750.0, 0, 0, 0, 0]


def test_ideal_withdrawal_search_uses_configured_goal() -> None:
    result = ideal_withdrawal_search(
        SimulationInputs(
            initial_balance=120_000.0,
            start_year=2025,
            start_quarter=4,
            end_year=2026,
            end_quarter=4,
            goal_year=2026,
            goal_quarter=4,
            goal_balance=100_000.0,
            goal_percentile=5,
            mu=0.0,
            sigma=0.0,
            simulations=10,
            seed=1,
        ),
        step=100.0,
    )
    assert result["recommended_withdrawal"] == 6_700.0
    assert result["achieved_balance"] == 99_900.0
    assert result["target_quarter"] == "Q4 2026"
    assert result["percentile"] == 5


def test_ideal_withdrawal_search_replaces_primary_rule_amount() -> None:
    result = ideal_withdrawal_search(
        SimulationInputs(
            initial_balance=120_000.0,
            start_year=2025,
            start_quarter=4,
            end_year=2026,
            end_quarter=4,
            withdrawal_rules=(
                WithdrawalRule(
                    "Primary quarterly withdrawal",
                    50_000.0,
                    2026,
                    1,
                    2026,
                    4,
                    "quarterly",
                    "primary_quarterly",
                ),
            ),
            goal_year=2026,
            goal_quarter=4,
            goal_balance=100_000.0,
            goal_percentile=5,
            mu=0.0,
            sigma=0.0,
            simulations=10,
            seed=1,
        ),
        step=100.0,
    )
    assert result["recommended_withdrawal"] == 6_700.0
    assert result["achieved_balance"] == 99_900.0


def test_ideal_withdrawal_search_can_recommend_negative_withdrawal() -> None:
    result = ideal_withdrawal_search(
        SimulationInputs(
            initial_balance=100_000.0,
            start_year=2025,
            start_quarter=4,
            end_year=2026,
            end_quarter=4,
            goal_year=2026,
            goal_quarter=4,
            goal_balance=120_000.0,
            goal_percentile=5,
            mu=0.0,
            sigma=0.0,
            simulations=10,
            seed=1,
        ),
        step=100.0,
    )
    assert result["recommended_withdrawal"] == -6_700.0
    assert result["achieved_balance"] == 120_100.0
