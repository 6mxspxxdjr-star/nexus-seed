#!/usr/bin/env python3
"""
Nexus Architecture Optimizer — Training Script

This is the mutable training script that autoresearch-mlx modifies overnight.
It runs a simulation with current parameters and returns a single metric
(prediction accuracy / ROI) that autoresearch uses to guide optimization.

autoresearch will modify the PARAMETERS section below to find optimal values.

Usage:
    python train.py  # Returns a single float metric to stdout
"""

import json
import os
import sys
import time
from pathlib import Path

NEXUS_HOME = Path(os.environ.get("NEXUS_HOME", Path.home() / "nexus"))
sys.path.insert(0, str(NEXUS_HOME / "scripts"))

# ============================================================================
# PARAMETERS — autoresearch modifies this section
# ============================================================================
PARAMS = {
    "num_agents": 100,
    "num_rounds": 30,
    "market": "crypto",
    "lookback_min": 3,
    "lookback_max": 20,
    "threshold_min": 0.01,
    "threshold_max": 0.05,
    "momentum_weight": 0.4,
    "mean_reversion_weight": 0.3,
    "breakout_weight": 0.3,
    "volatility_scaling": True,
    "position_sizing": "equal",  # equal, kelly, risk_parity
}
# ============================================================================


def run_training():
    """Run a training iteration and return the optimization metric."""
    start = time.time()

    from run_simulation import run_builtin_simulation, analyze_results

    # Run simulation with current parameters
    results, prices = run_builtin_simulation(
        num_agents=PARAMS["num_agents"],
        num_rounds=PARAMS["num_rounds"],
        market=PARAMS["market"],
        params={
            "starting_capital": 10000,
            "lookback_min": PARAMS["lookback_min"],
            "lookback_max": PARAMS["lookback_max"],
        },
    )

    analysis = analyze_results(results, prices)
    duration = time.time() - start

    # Composite metric: weighted combination of ROI, Sharpe, and win rate
    # This is what autoresearch optimizes
    metric = (
        analysis["mean_roi_pct"] * 0.4
        + analysis["sharpe_ratio"] * 30  # Scale Sharpe to similar range
        + analysis["win_rate_pct"] * 0.3
    ) / 100  # Normalize to ~0-1 range

    # Log the run
    log_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "params": PARAMS,
        "results": {
            "metric": round(metric, 6),
            "mean_roi_pct": analysis["mean_roi_pct"],
            "sharpe_ratio": analysis["sharpe_ratio"],
            "win_rate_pct": analysis["win_rate_pct"],
        },
        "duration_seconds": round(duration, 1),
    }

    # Append to optimization log
    log_path = NEXUS_HOME / "optimizer" / "optimization_log.jsonl"
    with open(log_path, "a") as f:
        f.write(json.dumps(log_entry) + "\n")

    # Store in memory if significant improvement
    try:
        from memory_system import MemorySystem

        ms = MemorySystem(str(NEXUS_HOME))
        ms.store(
            content=(
                f"Optimization run: metric={metric:.4f}, "
                f"ROI={analysis['mean_roi_pct']}%, "
                f"Sharpe={analysis['sharpe_ratio']}, "
                f"params={json.dumps({k: v for k, v in PARAMS.items() if k not in ('market',)})}"
            ),
            memory_type="strategic",
            tags=["optimization", "autoresearch"],
            source="optimizer",
            importance=0.5,
        )
    except Exception:
        pass

    # Output the single metric (autoresearch reads this)
    print(f"{metric:.6f}")
    return metric


if __name__ == "__main__":
    run_training()
