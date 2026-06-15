from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import DEFAULT_INITIAL_BALANCE, DEFAULT_MU, DEFAULT_SIGMA, STATIC_DIR
from .history import history_payload, history_stats_from, load_history_frame
from .simulation import (
    SimulationInputs,
    effective_initial_balance,
    ideal_withdrawal_search,
    simulation_payload,
    yearly_return_stats_from_quarterly_log_params,
)

app = FastAPI(title="PhD Finance Simulator")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


@app.middleware("http")
async def no_store_responses(request, call_next):
    response = await call_next(request)
    response.headers["Cache-Control"] = "no-store"
    return response


class SimulationRequest(BaseModel):
    initial_balance: float = Field(default=DEFAULT_INITIAL_BALANCE, ge=0)
    apply_taxes: bool = Field(default=False)
    withdrawal: float = Field(default=10_000.0, ge=0)
    mu: float = Field(default=DEFAULT_MU)
    sigma: float = Field(default=DEFAULT_SIGMA, ge=0)
    simulations: int = Field(default=40_000, ge=1, le=250_000)
    seed: int = Field(default=42, ge=0)


class IdealWithdrawalRequest(BaseModel):
    initial_balance: float = Field(default=DEFAULT_INITIAL_BALANCE, ge=0)
    apply_taxes: bool = Field(default=False)
    mu: float = Field(default=DEFAULT_MU)
    sigma: float = Field(default=DEFAULT_SIGMA, ge=0)
    simulations: int = Field(default=40_000, ge=1, le=250_000)
    seed: int = Field(default=42, ge=0)


class EffectiveStatsRequest(BaseModel):
    initial_balance: float = Field(default=DEFAULT_INITIAL_BALANCE, ge=0)
    apply_taxes: bool = Field(default=False)
    mu: float = Field(default=DEFAULT_MU)
    sigma: float = Field(default=DEFAULT_SIGMA, ge=0)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(Path(STATIC_DIR) / "index.html", headers={"Cache-Control": "no-store"})


@app.get("/api/history")
def get_history(apply_taxes: bool = False) -> dict[str, object]:
    return history_payload(apply_taxes=apply_taxes)


@app.get("/api/history/stats")
def get_history_stats(start_quarter: str, apply_taxes: bool = False) -> dict[str, object]:
    history = load_history_frame()
    try:
        stats = history_stats_from(history, start_quarter, apply_taxes=apply_taxes)
    except KeyError as exc:
        raise HTTPException(status_code=404, detail=str(exc)) from exc

    return stats.__dict__


@app.post("/api/simulate")
def post_simulation(request: SimulationRequest) -> dict[str, object]:
    inputs = SimulationInputs(
        initial_balance=request.initial_balance,
        apply_taxes=request.apply_taxes,
        withdrawal=request.withdrawal,
        mu=request.mu,
        sigma=request.sigma,
        simulations=request.simulations,
        seed=request.seed,
    )
    return simulation_payload(inputs)


@app.post("/api/ideal-withdrawal")
def post_ideal_withdrawal(request: IdealWithdrawalRequest) -> dict[str, object]:
    inputs = SimulationInputs(
        initial_balance=request.initial_balance,
        apply_taxes=request.apply_taxes,
        withdrawal=0.0,
        mu=request.mu,
        sigma=request.sigma,
        simulations=request.simulations,
        seed=request.seed,
    )
    return ideal_withdrawal_search(inputs)


@app.post("/api/effective-stats")
def post_effective_stats(request: EffectiveStatsRequest) -> dict[str, object]:
    yearly_mean, yearly_std = yearly_return_stats_from_quarterly_log_params(
        request.mu, request.sigma, request.apply_taxes
    )
    return {
        "effective_initial_balance": effective_initial_balance(request.initial_balance, request.apply_taxes),
        "yearly_mean": yearly_mean,
        "yearly_std": yearly_std,
        "apply_taxes": request.apply_taxes,
    }
