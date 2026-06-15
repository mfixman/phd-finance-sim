from __future__ import annotations

from dataclasses import dataclass

import numpy as np
import pandas as pd

from .config import DATA_FILE
from .simulation import yearly_return_stats_from_quarterly_log_params


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
    apply_taxes: bool


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
    return history["quarter"].tolist()


def history_stats_from(frame: pd.DataFrame, start_quarter: str, apply_taxes: bool = False) -> HistoryStats:
    matches = frame.index[frame["quarter"] == start_quarter]
    if len(matches) == 0:
        raise KeyError(f"Unknown starting quarter: {start_quarter}")

    start_index = int(matches[0])
    growth_factors = frame.loc[start_index:, "growth_factor"].to_numpy(dtype=float)

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
    end_quarter = str(frame.iloc[-1]["quarter"])
    annualized_return = float(np.prod(subset["growth_factor"]) ** (4 / len(subset)) - 1.0)
    yearly_mean, yearly_std = yearly_return_stats_from_quarterly_log_params(mu, sigma, apply_taxes)
    return HistoryStats(
        start_quarter=start_quarter,
        end_quarter=end_quarter,
        observations=int(len(subset)),
        mu=mu,
        sigma=sigma,
        annualized_return=annualized_return,
        yearly_mean=yearly_mean,
        yearly_std=yearly_std,
        apply_taxes=apply_taxes,
    )


def default_history_stats(frame: pd.DataFrame | None = None, apply_taxes: bool = False) -> HistoryStats:
    history = load_history_frame() if frame is None else frame
    return history_stats_from(history, history.iloc[0]["quarter"], apply_taxes=apply_taxes)


def history_payload(frame: pd.DataFrame | None = None, apply_taxes: bool = False) -> dict[str, object]:
    history = load_history_frame() if frame is None else frame
    default_stats = default_history_stats(history, apply_taxes=apply_taxes)
    stats_by_quarter = {
        quarter: history_stats_from(history, quarter, apply_taxes=apply_taxes) for quarter in history["quarter"]
    }
    records = history.assign(
        start_date=lambda df: df["start_date"].dt.strftime("%Y-%m-%d"),
        end_date=lambda df: df["end_date"].dt.strftime("%Y-%m-%d"),
        annualized_return=lambda df: df["quarter"].map(
            lambda quarter: stats_by_quarter[quarter].annualized_return
        ),
    ).to_dict(orient="records")

    return {
        "quarters": history["quarter"].tolist(),
        "records": records,
        "default_stats": default_stats.__dict__,
        "end_quarter": history.iloc[-1]["quarter"],
        "apply_taxes": apply_taxes,
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
