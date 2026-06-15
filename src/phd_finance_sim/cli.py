from __future__ import annotations

import argparse
import json

from .config import (
    DEFAULT_INITIAL_BALANCE,
    DEFAULT_MU,
    DEFAULT_SIGMA,
    DEFAULT_SIMULATIONS,
    PROJECTION_END_QUARTER,
    PROJECTION_END_YEAR,
    PROJECTION_START_QUARTER,
    PROJECTION_START_YEAR,
)
from .history import history_stats_from, load_history_frame
from .simulation import SimulationInputs, WithdrawalRule, simulation_payload


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="Run the portfolio withdrawal simulation.")
    parser.add_argument("--initial-balance", type=float, default=DEFAULT_INITIAL_BALANCE)
    parser.add_argument("--start-year", type=int, default=PROJECTION_START_YEAR)
    parser.add_argument("--start-quarter", type=int, default=PROJECTION_START_QUARTER)
    parser.add_argument("--end-year", type=int, default=PROJECTION_END_YEAR)
    parser.add_argument("--end-quarter", type=int, default=PROJECTION_END_QUARTER)
    parser.add_argument("--quarterly-withdrawal", type=float, default=0.0)
    parser.add_argument("--goal-year", type=int, default=PROJECTION_END_YEAR)
    parser.add_argument("--goal-quarter", type=int, default=PROJECTION_END_QUARTER)
    parser.add_argument("--goal-balance", type=float, default=DEFAULT_INITIAL_BALANCE)
    parser.add_argument("--goal-percentile", type=int, default=5)
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
        stats = history_stats_from(history, args.history_start_quarter)
        mu = stats.mu
        sigma = stats.sigma
        history_meta = stats.__dict__

    withdrawal_rules = ()
    if args.quarterly_withdrawal > 0:
        withdrawal_rules = (
            WithdrawalRule(
                name="Quarterly withdrawal",
                amount=args.quarterly_withdrawal,
                start_year=args.start_year,
                start_quarter=args.start_quarter,
                end_year=args.end_year,
                end_quarter=args.end_quarter,
                cadence="quarterly",
            ),
        )

    payload = simulation_payload(
        SimulationInputs(
            initial_balance=args.initial_balance,
            start_year=args.start_year,
            start_quarter=args.start_quarter,
            end_year=args.end_year,
            end_quarter=args.end_quarter,
            withdrawal_rules=withdrawal_rules,
            goal_year=args.goal_year,
            goal_quarter=args.goal_quarter,
            goal_balance=args.goal_balance,
            goal_percentile=args.goal_percentile,
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
