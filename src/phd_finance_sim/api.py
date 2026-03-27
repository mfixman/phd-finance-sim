from __future__ import annotations

from pathlib import Path

from fastapi import FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from pydantic import BaseModel, Field

from .config import DEFAULT_INITIAL_BALANCE, DEFAULT_MU, DEFAULT_SIGMA, STATIC_DIR
from .history import history_payload, history_stats_from, load_history_frame
from .simulation import SimulationInputs, simulation_payload

app = FastAPI(title="PhD Finance Simulator")
app.mount("/static", StaticFiles(directory=STATIC_DIR), name="static")


class SimulationRequest(BaseModel):
    initial_balance: float = Field(default=DEFAULT_INITIAL_BALANCE, ge=0)
    withdrawal: float = Field(default=10_000.0, ge=0)
    mu: float = Field(default=DEFAULT_MU)
    sigma: float = Field(default=DEFAULT_SIGMA, ge=0)
    simulations: int = Field(default=40_000, ge=1, le=250_000)
    seed: int = Field(default=42, ge=0)


@app.get("/")
def index() -> FileResponse:
    return FileResponse(Path(STATIC_DIR) / "index.html")


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
    inputs = SimulationInputs(
        initial_balance=request.initial_balance,
        withdrawal=request.withdrawal,
        mu=request.mu,
        sigma=request.sigma,
        simulations=request.simulations,
        seed=request.seed,
    )
    return simulation_payload(inputs)
