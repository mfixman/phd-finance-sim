from __future__ import annotations

from fastapi.testclient import TestClient

from phd_finance_sim.api import app


client = TestClient(app)


def test_history_endpoint_serves_full_range() -> None:
    response = client.get("/api/history")
    assert response.status_code == 200
    payload = response.json()
    assert payload["quarters"][0] == "1988Q1"
    assert payload["quarters"][-1] == "2025Q4"
    assert payload["end_quarter"] == "2025Q4"


def test_simulate_endpoint_returns_chart_and_twentiles() -> None:
    response = client.post(
        "/api/simulate",
        json={"initial_balance": 400000, "withdrawal": 10000, "mu": 0.02, "sigma": 0.08, "simulations": 500, "seed": 42},
    )
    assert response.status_code == 200
    payload = response.json()
    assert payload["quarters"][0] == "Q4 2026"
    assert payload["quarters"][-1] == "Q4 2029"
    assert payload["chart_percentiles"][3]["values"][0] == 400000.0
    assert len(payload["chart_percentiles"]) == 7
    assert len(payload["twentiles"]) == 20
