from __future__ import annotations

import numpy as np
import pandas as pd
import pytest

from phd_finance_sim.history import history_stats_from


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


def test_history_stats_apply_taxes_keeps_return_series_unchanged() -> None:
    frame = pd.DataFrame(
        {
            "quarter": ["2000Q1", "2000Q2", "2000Q3"],
            "growth_factor": [1.10, 0.80, 1.30],
            "log_gain": [np.log(1.10), np.log(0.80), np.log(1.30)],
        }
    )
    untaxed = history_stats_from(frame, "2000Q2", apply_taxes=False)
    taxed = history_stats_from(frame, "2000Q2", apply_taxes=True)
    assert taxed.annualized_return == pytest.approx(untaxed.annualized_return)
    assert taxed.mu == pytest.approx(untaxed.mu)
    assert taxed.sigma == pytest.approx(untaxed.sigma)
    assert taxed.apply_taxes is True
