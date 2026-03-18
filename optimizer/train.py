#!/usr/bin/env python3
"""
Nexus Architecture Optimizer — Training Script

This is the mutable training script that autoresearch-mlx modifies overnight.
It runs a simulation with current parameters and returns a single metric
(prediction accuracy / ROI) that autoresearch uses to guide optimization.

The composite score now includes:
- Simulation performance (ROI, Sharpe, win rate)
- Agent success rate (from RL signals)
- User satisfaction (from RL corrections/confirmations)

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
    # Simulation
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

    # Model routing
    "routing_confidence_threshold": 0.6,
    "routing_cloud_escalation_threshold": "high",

    # Memory system
    "memory_decay_lambda": 0.05,
    "memory_search_top_k": 5,
    "memory_rrf_k": 60,

    # RL judge
    "rl_reward_threshold": 0.5,
    "rl_signal_window_days": 7,
}
# ============================================================================


def get_rl_metrics() -> dict:
    """Load RL metrics if available. Returns zeros if no signals exist."""
    defaults = {"agent_success_rate": 0.0, "user_satisfaction": 0.0, "avg_reward": 0.0}
    try:
        from rl_signals import RLSignalProcessor
        proc = RLSignalProcessor(str(NEXUS_HOME))
        metrics = proc.compute_metrics(days=PARAMS.get("rl_signal_window_days", 7))
        return {
            "agent_success_rate": metrics.get("agent_success_rate", 0.0),
            "user_satisfaction": metrics.get("user_satisfaction", 0.0),
            "avg_reward": metrics.get("avg_reward", 0.0),
        }
    except ImportError:
        return defaults
    except Exception:
        return defaults


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

    # Get RL metrics
    rl = get_rl_metrics()

    # Composite metric: weighted combination of simulation + RL signals
    # Simulation performance (60% weight)
    sim_score = (
        analysis["mean_roi_pct"] * 0.4
        + analysis["sharpe_ratio"] * 30
        + analysis["win_rate_pct"] * 0.3
    ) / 100

    # RL feedback (40% weight when available, otherwise simulation-only)
    rl_score = (
        rl["agent_success_rate"] * 0.4
        + rl["user_satisfaction"] * 0.4
        + rl["avg_reward"] * 0.2
    )

    has_rl_data = rl["agent_success_rate"] > 0 or rl["user_satisfaction"] > 0
    if has_rl_data:
        metric = sim_score * 0.6 + rl_score * 0.4
    else:
        metric = sim_score

    # Log the run
    log_entry = {
        "timestamp": time.strftime("%Y-%m-%dT%H:%M:%SZ", time.gmtime()),
        "params": PARAMS,
        "results": {
            "metric": round(metric, 6),
            "sim_score": round(sim_score, 6),
            "rl_score": round(rl_score, 6),
            "has_rl_data": has_rl_data,
            "mean_roi_pct": analysis["mean_roi_pct"],
            "sharpe_ratio": analysis["sharpe_ratio"],
            "win_rate_pct": analysis["win_rate_pct"],
            "agent_success_rate": rl["agent_success_rate"],
            "user_satisfaction": rl["user_satisfaction"],
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
                f"Optimization run: metric={metric:.4f} (sim={sim_score:.4f}, rl={rl_score:.4f}), "
                f"ROI={analysis['mean_roi_pct']}%, "
                f"Sharpe={analysis['sharpe_ratio']}, "
                f"agent_success={rl['agent_success_rate']:.2f}, "
                f"user_satisfaction={rl['user_satisfaction']:.2f}"
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
