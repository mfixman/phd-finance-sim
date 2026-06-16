from __future__ import annotations

from fastapi.testclient import TestClient

from phd_finance_sim.api import app


client = TestClient(app)


def test_history_endpoint_serves_full_range() -> None:
    response = client.get("/api/history")
    assert response.status_code == 200
    payload = response.json()
    assert payload["quarters"][0] == "1988Q1"
    assert payload["quarters"][-1] == "2025Q3"
    assert "2025Q4" not in payload["quarters"]
    assert payload["end_quarter"] == "2025Q4"


def test_simulate_endpoint_returns_chart_and_twentiles() -> None:
    response = client.post(
        "/api/simulate",
        json={
            "initial_balance": 400000,
            "withdrawal_rules": [
                {
                    "name": "Quarterly",
                    "amount": 10000,
                    "start_year": 2026,
                    "start_quarter": 1,
                    "end_year": 2026,
                    "end_quarter": 4,
                    "cadence": "quarterly",
                }
            ],
            "mu": 0.02,
            "sigma": 0.08,
            "simulations": 500,
            "seed": 42,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["quarters"][0] == "Q4 2025"
    assert payload["quarters"][-1] == "Q4 2029"
    assert payload["chart_percentiles"][3]["values"][0] == 400000.0
    assert len(payload["chart_percentiles"]) == 7
    assert len(payload["twentiles"]) == 20
    assert payload["withdrawal_schedule"][0] == 10000.0


def test_simulate_endpoint_applies_arbitrary_annual_withdrawal() -> None:
    response = client.post(
        "/api/simulate",
        json={
            "initial_balance": 400000,
            "withdrawal_rules": [
                {
                    "name": "Annual fee",
                    "amount": 750,
                    "start_year": 2026,
                    "start_quarter": 1,
                    "end_year": 2027,
                    "end_quarter": 1,
                    "cadence": "annual",
                }
            ],
            "mu": 0.0,
            "sigma": 0.0,
            "simulations": 500,
            "seed": 42,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["effective_initial_balance"] == 400_000.0
    assert payload["chart_percentiles"][3]["values"][0] == 400_000.0
    assert payload["chart_percentiles"][3]["values"][1] == 399_250.0
    assert payload["chart_percentiles"][3]["values"][5] == 399_250.0


def test_simulate_endpoint_defaults_withdrawal_rules_to_quarterly_intervals() -> None:
    response = client.post(
        "/api/simulate",
        json={
            "initial_balance": 400000,
            "end_year": 2026,
            "end_quarter": 3,
            "withdrawal_rules": [
                {
                    "name": "Interval",
                    "amount": 1000,
                    "start_year": 2026,
                    "start_quarter": 1,
                    "end_year": 2026,
                    "end_quarter": 3,
                }
            ],
            "mu": 0.0,
            "sigma": 0.0,
            "simulations": 100,
            "seed": 42,
        },
    )
    assert response.status_code == 200
    assert response.json()["withdrawal_schedule"][:3] == [1000.0, 1000.0, 0]


def test_simulate_endpoint_accepts_negative_withdrawal_as_income() -> None:
    response = client.post(
        "/api/simulate",
        json={
            "initial_balance": 100000,
            "end_year": 2026,
            "end_quarter": 1,
            "withdrawal_rules": [
                {
                    "name": "Salary",
                    "amount": -1000,
                    "start_year": 2026,
                    "start_quarter": 1,
                    "end_year": 2026,
                    "end_quarter": 2,
                }
            ],
            "mu": 0.0,
            "sigma": 0.0,
            "simulations": 100,
            "seed": 42,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["withdrawal_schedule"][0] == -1000.0
    assert payload["chart_percentiles"][3]["values"][1] == 101000.0


def test_simulate_endpoint_uses_projection_end_as_goal_quarter() -> None:
    response = client.post(
        "/api/simulate",
        json={
            "initial_balance": 120000,
            "start_year": 2025,
            "start_quarter": 4,
            "end_year": 2026,
            "end_quarter": 2,
            "goal_year": 2026,
            "goal_quarter": 4,
            "goal_balance": 100000,
            "goal_percentile": 5,
            "mu": 0.0,
            "sigma": 0.0,
            "simulations": 100,
            "seed": 1,
        },
    )
    assert response.status_code == 200
    assert response.json()["goal"]["quarter"] == "Q2 2026"


def test_ideal_withdrawal_endpoint_returns_recommendation() -> None:
    response = client.post(
        "/api/ideal-withdrawal",
        json={
            "initial_balance": 120000,
            "start_year": 2025,
            "start_quarter": 4,
            "end_year": 2026,
            "end_quarter": 4,
            "goal_year": 2026,
            "goal_quarter": 4,
            "goal_balance": 100000,
            "goal_percentile": 5,
            "mu": 0.0,
            "sigma": 0.0,
            "simulations": 100,
            "seed": 1,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["recommended_withdrawal"] == 6700.0
    assert payload["achieved_balance"] == 99900.0
    assert payload["target_quarter"] == "Q4 2026"
    assert payload["target_timing"] == "start"


def test_ideal_withdrawal_endpoint_can_recommend_income() -> None:
    response = client.post(
        "/api/ideal-withdrawal",
        json={
            "initial_balance": 100000,
            "start_year": 2025,
            "start_quarter": 4,
            "end_year": 2026,
            "end_quarter": 4,
            "goal_balance": 120000,
            "goal_percentile": 5,
            "mu": 0.0,
            "sigma": 0.0,
            "simulations": 100,
            "seed": 1,
        },
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["recommended_withdrawal"] == -6700.0
    assert payload["achieved_balance"] == 120100.0
