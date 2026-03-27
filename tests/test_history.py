from __future__ import annotations

import pandas as pd
import pytest

from phd_finance_sim.history import history_stats_from


def test_history_stats_from_selected_quarter() -> None:
    frame = pd.DataFrame(
        {
            "quarter": ["2000Q1", "2000Q2", "2000Q3"],
            "log_gain": [0.1, -0.2, 0.3],
        }
    )
    stats = history_stats_from(frame, "2000Q2")
    assert stats.start_quarter == "2000Q2"
    assert stats.observations == 2
    assert stats.mu == pytest.approx(0.05)
