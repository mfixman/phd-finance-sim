from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import DATA_FILE, PROJECTION_START_QUARTER, PROJECTION_START_YEAR
from .simulation import yearly_return_stats_from_quarterly_log_params

HISTORY_ENDPOINT_QUARTER = f"{PROJECTION_START_YEAR}Q{PROJECTION_START_QUARTER}"


@dataclass(frozen=True)
class HistoryStats:
    start_quarter: str
    end_quarter: str
    observations: int
    mu: float
    sigma: float
    annualized_return: float
    yearly_mean: float
    yearly_std: float


def load_history_frame() -> pd.DataFrame:
    if not DATA_FILE.exists():
        raise FileNotFoundError(
            f"Missing historical dataset at {DATA_FILE}. Run scripts/fetch_sp500_history.py."
        )

    frame = pd.read_csv(DATA_FILE, parse_dates=["start_date", "end_date"])
    required = {
        "quarter",
        "start_date",
        "end_date",
        "start_close",
        "end_close",
        "growth_factor",
        "quarter_return",
        "log_gain",
    }
    missing = required.difference(frame.columns)
    if missing:
        missing_list = ", ".join(sorted(missing))
        raise ValueError(f"Historical dataset is missing required columns: {missing_list}")

    return frame.sort_values("quarter").reset_index(drop=True)


def available_start_quarters(frame: pd.DataFrame | None = None) -> list[str]:
    history = load_history_frame() if frame is None else frame
    analysis_history, _ = historical_return_frame(history)
    return analysis_history["quarter"].tolist()


def historical_return_frame(frame: pd.DataFrame) -> tuple[pd.DataFrame, str]:
    endpoint_matches = frame.index[frame["quarter"] == HISTORY_ENDPOINT_QUARTER]
    if len(endpoint_matches) == 0:
        return frame, str(frame.iloc[-1]["quarter"])

    endpoint_index = int(endpoint_matches[0])
    analysis_history = frame.iloc[:endpoint_index]
    if analysis_history.empty:
        raise ValueError(f"No historical observations available before {HISTORY_ENDPOINT_QUARTER}")
    return analysis_history, HISTORY_ENDPOINT_QUARTER


def history_stats_from(frame: pd.DataFrame, start_quarter: str) -> HistoryStats:
    analysis_history, end_quarter = historical_return_frame(frame)
    matches = analysis_history.index[analysis_history["quarter"] == start_quarter]
    if len(matches) == 0:
        raise KeyError(f"Unknown starting quarter: {start_quarter}")

    start_index = int(matches[0])
    growth_factors = analysis_history.loc[start_index:, "growth_factor"].to_numpy(dtype=float)

    subset = pd.DataFrame(
        {
            "growth_factor": growth_factors,
            "log_gain": np.log(growth_factors),
        }
    )
    if subset.empty:
        raise ValueError(f"No observations available from starting quarter {start_quarter}")

    mu = float(subset["log_gain"].mean())
    sigma = float(subset["log_gain"].std(ddof=0))
    annualized_return = float(np.prod(subset["growth_factor"]) ** (4 / len(subset)) - 1.0)
    yearly_mean, yearly_std = yearly_return_stats_from_quarterly_log_params(mu, sigma)
    return HistoryStats(
        start_quarter=start_quarter,
        end_quarter=end_quarter,
        observations=int(len(subset)),
        mu=mu,
        sigma=sigma,
        annualized_return=annualized_return,
        yearly_mean=yearly_mean,
        yearly_std=yearly_std,
    )


def default_history_stats(frame: pd.DataFrame | None = None) -> HistoryStats:
    history = load_history_frame() if frame is None else frame
    analysis_history, _ = historical_return_frame(history)
    return history_stats_from(history, analysis_history.iloc[0]["quarter"])


def history_payload(frame: pd.DataFrame | None = None) -> dict[str, object]:
    history = load_history_frame() if frame is None else frame
    analysis_history, end_quarter = historical_return_frame(history)
    default_stats = default_history_stats(history)
    stats_by_quarter = {
        quarter: history_stats_from(history, quarter) for quarter in analysis_history["quarter"]
    }
    records = analysis_history.assign(
        start_date=lambda df: df["start_date"].dt.strftime("%Y-%m-%d"),
        end_date=lambda df: df["end_date"].dt.strftime("%Y-%m-%d"),
        annualized_return=lambda df: df["quarter"].map(
            lambda quarter: stats_by_quarter[quarter].annualized_return
        ),
    ).to_dict(orient="records")

    return {
        "quarters": analysis_history["quarter"].tolist(),
        "records": records,
        "default_stats": default_stats.__dict__,
        "end_quarter": end_quarter,
    }


def log_gain_summary(frame: pd.DataFrame | None = None) -> dict[str, float]:
    history = load_history_frame() if frame is None else frame
    log_gains = history["log_gain"].to_numpy()
    return {
        "min": float(np.min(log_gains)),
        "max": float(np.max(log_gains)),
        "mean": float(np.mean(log_gains)),
        "sigma": float(np.std(log_gains, ddof=0)),
    }
