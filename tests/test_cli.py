from __future__ import annotations

import json
import subprocess
import sys
from pathlib import Path


def test_cli_outputs_json() -> None:
    root = Path(__file__).resolve().parents[1]
    result = subprocess.run(
        [
            sys.executable,
            "-m",
            "phd_finance_sim.cli",
            "--initial-balance",
            "400000",
            "--mu",
            "0",
            "--sigma",
            "0",
            "--simulations",
            "5",
        ],
        cwd=root,
        capture_output=True,
        text=True,
        check=True,
    )
    payload = json.loads(result.stdout)
    assert payload["history_stats"] is None
    assert payload["simulation"]["quarters"][0] == "Q4 2025"
    assert payload["simulation"]["quarters"][-1] == "Q4 2029"
    assert payload["simulation"]["chart_percentiles"][3]["values"][0] == 400000.0
