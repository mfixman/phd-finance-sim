from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from phd_finance_sim.history import available_start_quarters, history_payload, history_stats_from


def test_history_stats_from_selected_quarter() -> None:
    frame = pd.DataFrame(
        {
            "quarter": ["2000Q1", "2000Q2", "2000Q3"],
            "growth_factor": [1.105170918, 0.818730753, 1.349858808],
            "log_gain": [0.1, -0.2, 0.3],
        }
    )
    stats = history_stats_from(frame, "2000Q2")
    assert stats.start_quarter == "2000Q2"
    assert stats.end_quarter == "2000Q3"
    assert stats.observations == 2
    assert stats.mu == pytest.approx(0.05)
    assert stats.annualized_return == pytest.approx(0.221402758, rel=1e-6)


def test_history_stats_return_series_is_deterministic() -> None:
    frame = pd.DataFrame(
        {
            "quarter": ["2000Q1", "2000Q2", "2000Q3"],
            "growth_factor": [1.10, 0.80, 1.30],
            "log_gain": [np.log(1.10), np.log(0.80), np.log(1.30)],
        }
    )
    stats = history_stats_from(frame, "2000Q2")
    assert stats.annualized_return == pytest.approx((0.80 * 1.30) ** 2 - 1.0)
    assert stats.mu == pytest.approx(np.mean([np.log(0.80), np.log(1.30)]))
    assert stats.sigma == pytest.approx(np.std([np.log(0.80), np.log(1.30)]))


def test_history_stats_exclude_projection_start_quarter_return() -> None:
    frame = pd.DataFrame(
        {
            "quarter": ["2025Q2", "2025Q3", "2025Q4"],
            "start_date": pd.to_datetime(["2025-04-01", "2025-07-01", "2025-10-01"]),
            "end_date": pd.to_datetime(["2025-06-30", "2025-09-30", "2025-12-31"]),
            "growth_factor": [1.10, 1.20, 9.99],
            "log_gain": [np.log(1.10), np.log(1.20), np.log(9.99)],
        }
    )

    stats = history_stats_from(frame, "2025Q2")
    payload = history_payload(frame)

    assert available_start_quarters(frame) == ["2025Q2", "2025Q3"]
    assert payload["quarters"] == ["2025Q2", "2025Q3"]
    assert payload["end_quarter"] == "2025Q4"
    assert stats.end_quarter == "2025Q4"
    assert stats.observations == 2
    assert stats.mu == pytest.approx(np.mean([np.log(1.10), np.log(1.20)]))
