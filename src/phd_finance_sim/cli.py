from __future__ import annotations

import argparse
import json

from .config import DEFAULT_INITIAL_BALANCE, DEFAULT_MU, DEFAULT_SIGMA, DEFAULT_SIMULATIONS, DEFAULT_WITHDRAWAL
from .history import history_stats_from, load_history_frame
from .simulation import SimulationInputs, simulation_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the PhD finance simulation.")
    parser.add_argument("--initial-balance", type=float, default=DEFAULT_INITIAL_BALANCE)
    parser.add_argument("--apply-taxes", action="store_true")
    parser.add_argument("--withdrawal", type=float, default=DEFAULT_WITHDRAWAL)
    parser.add_argument("--mu", type=float, default=DEFAULT_MU)
    parser.add_argument("--sigma", type=float, default=DEFAULT_SIGMA)
    parser.add_argument("--simulations", type=int, default=DEFAULT_SIMULATIONS)
    parser.add_argument("--seed", type=int, default=42)
    parser.add_argument(
        "--history-start-quarter",
        help="If provided, derive mu and sigma from quarterly S&P 500 total-return log gains from this quarter onward.",
    )
    return parser


def main() -> None:
    args = build_parser().parse_args()

    mu = args.mu
    sigma = args.sigma
    history_meta: dict[str, object] | None = None

    if args.history_start_quarter:
        history = load_history_frame()
        stats = history_stats_from(history, args.history_start_quarter, apply_taxes=False)
        mu = stats.mu
        sigma = stats.sigma
        history_meta = stats.__dict__

    payload = simulation_payload(
        SimulationInputs(
            initial_balance=args.initial_balance,
            apply_taxes=args.apply_taxes,
            withdrawal=args.withdrawal,
            mu=mu,
            sigma=sigma,
            simulations=args.simulations,
            seed=args.seed,
        )
    )
    output = {
        "history_stats": history_meta,
        "simulation": payload,
    }
    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
