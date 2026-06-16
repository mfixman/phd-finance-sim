from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, ConfigDict, Field

from .config import (
    DEFAULT_INITIAL_BALANCE,
    DEFAULT_MU,
    DEFAULT_SEED,
    DEFAULT_SIGMA,
    DEFAULT_SIMULATIONS,
    PROJECTION_END_QUARTER,
    PROJECTION_END_YEAR,
    PROJECTION_START_QUARTER,
    PROJECTION_START_YEAR,
    STATIC_DIR,
)
from .history import history_payload, history_stats_from, load_history_frame
from .simulation import (
    SimulationInputs,
    WithdrawalRule,
    effective_initial_balance,
    ideal_withdrawal_search,
    simulation_payload,
    yearly_return_stats_from_quarterly_log_params,
)

app = FastAPI(title="Unemployment Withdrawal Simulator")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def no_store_responses(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


class WithdrawalRuleRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    name: str = Field(default="Withdrawal")
    amount: float = Field(default=0.0)
    start_year: int = Field(default=PROJECTION_START_YEAR)
    start_quarter: int = Field(default=PROJECTION_START_QUARTER, ge=1, le=4)
    end_year: int = Field(default=PROJECTION_END_YEAR)
    end_quarter: int = Field(default=PROJECTION_END_QUARTER, ge=1, le=4)
    cadence: str = Field(default="quarterly")
    special: str | None = Field(default=None)


class SimulationRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    initial_balance: float = Field(default=DEFAULT_INITIAL_BALANCE, ge=0)
    start_year: int = Field(default=PROJECTION_START_YEAR)
    start_quarter: int = Field(default=PROJECTION_START_QUARTER, ge=1, le=4)
    end_year: int = Field(default=PROJECTION_END_YEAR)
    end_quarter: int = Field(default=PROJECTION_END_QUARTER, ge=1, le=4)
    withdrawal_rules: list[WithdrawalRuleRequest] = Field(default_factory=list)
    goal_year: int = Field(default=PROJECTION_END_YEAR)
    goal_quarter: int = Field(default=PROJECTION_END_QUARTER, ge=1, le=4)
    goal_balance: float = Field(default=DEFAULT_INITIAL_BALANCE, ge=0)
    goal_percentile: int = Field(default=5, ge=1, le=99)
    mu: float = Field(default=DEFAULT_MU)
    sigma: float = Field(default=DEFAULT_SIGMA, ge=0)
    simulations: int = Field(default=DEFAULT_SIMULATIONS, ge=1, le=250_000)
    seed: int = Field(default=DEFAULT_SEED, ge=0)


class EffectiveStatsRequest(BaseModel):
    model_config = ConfigDict(extra="ignore")

    initial_balance: float = Field(default=DEFAULT_INITIAL_BALANCE, ge=0)
    mu: float = Field(default=DEFAULT_MU)
    sigma: float = Field(default=DEFAULT_SIGMA, ge=0)


def simulation_inputs_from_request(request: SimulationRequest) -> SimulationInputs:
    return SimulationInputs(
        initial_balance=request.initial_balance,
        start_year=request.start_year,
        start_quarter=request.start_quarter,
        end_year=request.end_year,
        end_quarter=request.end_quarter,
        withdrawal_rules=tuple(WithdrawalRule(**rule.model_dump()) for rule in request.withdrawal_rules),
        goal_year=request.end_year,
        goal_quarter=request.end_quarter,
        goal_balance=request.goal_balance,
        goal_percentile=request.goal_percentile,
        mu=request.mu,
        sigma=request.sigma,
        simulations=request.simulations,
        seed=request.seed,
    )


@app.get("/")
def index() -> FileResponse:
    return FileResponse(Path(STATIC_DIR) / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/history")
def get_history() -> dict[str, object]:
    return history_payload()


@app.get("/api/history/stats")
def get_history_stats(start_quarter: str) -> dict[str, object]:
    history = load_history_frame()
    try:
        stats = history_stats_from(history, start_quarter)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return stats.__dict__


@app.post("/api/simulate")
def post_simulation(request: SimulationRequest) -> dict[str, object]:
    inputs = simulation_inputs_from_request(request)
    try:
        return simulation_payload(inputs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/ideal-withdrawal")
def post_ideal_withdrawal(request: SimulationRequest) -> dict[str, object]:
    inputs = simulation_inputs_from_request(request)
    try:
        return ideal_withdrawal_search(inputs)
    except ValueError as exc:
        raise HTTPException(status_code=400, detail=str(exc)) from exc


@app.post("/api/effective-stats")
def post_effective_stats(request: EffectiveStatsRequest) -> dict[str, object]:
    yearly_mean, yearly_std = yearly_return_stats_from_quarterly_log_params(request.mu, request.sigma)
    return {
        "effective_initial_balance": effective_initial_balance(request.initial_balance),
        "yearly_mean": yearly_mean,
        "yearly_std": yearly_std,
    }
