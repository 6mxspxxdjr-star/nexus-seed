#!/usr/bin/env python3
"""
Nexus Simulation Runner — Wrapper around MiroFish simulation engine.

Launches multi-agent economic simulations, captures results, and stores
outcomes in the Nexus memory system.

Usage:
    python run_simulation.py --agents 200 --rounds 100 --market crypto
"""

import argparse
import hashlib
import json
import logging
import os
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

logger = logging.getLogger("nexus.simulation")

NEXUS_HOME = Path(os.environ.get("NEXUS_HOME", Path.home() / "nexus"))
SIMULATIONS_DIR = NEXUS_HOME / "simulations"
MIROFISH_DIR = SIMULATIONS_DIR / "MiroFish-Offline"


def check_prerequisites():
    """Verify MiroFish and dependencies are available."""
    issues = []

    if not MIROFISH_DIR.exists():
        issues.append(f"MiroFish not found at {MIROFISH_DIR}")

    # Check Docker for Neo4j
    try:
        result = subprocess.run(
            ["docker", "info"], capture_output=True, timeout=10
        )
        if result.returncode != 0:
            issues.append("Docker is not running")
    except FileNotFoundError:
        issues.append("Docker not installed")

    # Check Ollama
    try:
        import requests
        resp = requests.get("http://localhost:11434/api/tags", timeout=5)
        if resp.status_code != 200:
            issues.append("Ollama not responding")
    except Exception:
        issues.append("Ollama not accessible at localhost:11434")

    return issues


def start_neo4j():
    """Start Neo4j via Docker Compose if not running."""
    compose_file = MIROFISH_DIR / "docker-compose.yml"

    if not compose_file.exists():
        # Create a default docker-compose for Neo4j
        compose_content = {
            "version": "3.8",
            "services": {
                "neo4j": {
                    "image": "neo4j:5-community",
                    "ports": ["7474:7474", "7687:7687"],
                    "environment": {
                        "NEO4J_AUTH": "neo4j/nexus_password",
                        "NEO4J_PLUGINS": '["apoc"]',
                    },
                    "volumes": [
                        f"{SIMULATIONS_DIR}/neo4j-data:/data",
                        f"{SIMULATIONS_DIR}/neo4j-logs:/logs",
                    ],
                }
            },
        }
        import yaml
        compose_file.parent.mkdir(parents=True, exist_ok=True)
        with open(compose_file, "w") as f:
            yaml.dump(compose_content, f, default_flow_style=False)

    # Check if Neo4j is already running
    try:
        import requests
        resp = requests.get("http://localhost:7474", timeout=5)
        if resp.status_code == 200:
            logger.info("Neo4j already running")
            return True
    except Exception:
        pass

    # Start with Docker Compose
    logger.info("Starting Neo4j...")
    result = subprocess.run(
        ["docker", "compose", "-f", str(compose_file), "up", "-d"],
        capture_output=True,
        text=True,
        cwd=str(MIROFISH_DIR),
    )

    if result.returncode != 0:
        logger.error(f"Failed to start Neo4j: {result.stderr}")
        return False

    # Wait for Neo4j to be ready
    for i in range(30):
        try:
            import requests
            resp = requests.get("http://localhost:7474", timeout=5)
            if resp.status_code == 200:
                logger.info("Neo4j is ready")
                return True
        except Exception:
            pass
        time.sleep(2)

    logger.error("Neo4j did not start in time")
    return False


def run_builtin_simulation(num_agents, num_rounds, market, params):
    """
    Run the built-in simulation engine when MiroFish is not available.
    Uses a simple multi-agent market simulation.
    """
    import random

    logger.info(f"Running built-in simulation: {num_agents} agents, {num_rounds} rounds, {market} market")

    # Initialize agents with random strategies
    agents = []
    for i in range(num_agents):
        agents.append({
            "id": i,
            "capital": params.get("starting_capital", 10000),
            "position": 0,
            "strategy": random.choice(["momentum", "mean-reversion", "random", "hold"]),
            "lookback": random.randint(3, 20),
            "threshold": random.uniform(0.01, 0.05),
            "trades": 0,
            "history": [],
        })

    # Generate market data
    price = 100.0
    prices = [price]
    for _ in range(num_rounds):
        # Market dynamics: slight upward drift with volatility
        drift = 0.0002 if market == "crypto" else 0.0001
        vol = 0.04 if market == "crypto" else 0.015
        price *= 1 + random.gauss(drift, vol)
        prices.append(price)

    # Run simulation
    for round_num in range(1, num_rounds + 1):
        current_price = prices[round_num]
        prev_price = prices[round_num - 1]
        ret = (current_price - prev_price) / prev_price

        for agent in agents:
            signal = 0

            if agent["strategy"] == "momentum":
                lookback = min(agent["lookback"], round_num)
                avg_ret = sum(
                    (prices[round_num - j] - prices[round_num - j - 1]) / prices[round_num - j - 1]
                    for j in range(lookback)
                ) / lookback
                signal = 1 if avg_ret > agent["threshold"] else (-1 if avg_ret < -agent["threshold"] else 0)

            elif agent["strategy"] == "mean-reversion":
                lookback = min(agent["lookback"], round_num)
                avg_price = sum(prices[round_num - j] for j in range(lookback)) / lookback
                deviation = (current_price - avg_price) / avg_price
                signal = -1 if deviation > agent["threshold"] else (1 if deviation < -agent["threshold"] else 0)

            elif agent["strategy"] == "random":
                signal = random.choice([-1, 0, 1])

            # else "hold" — signal stays 0

            if signal != agent["position"]:
                agent["position"] = signal
                agent["trades"] += 1

            if agent["position"] != 0:
                agent["capital"] *= 1 + agent["position"] * ret

            agent["history"].append(agent["capital"])

    # Compute results
    results = []
    for agent in agents:
        roi = (agent["capital"] - params.get("starting_capital", 10000)) / params.get("starting_capital", 10000)
        peak = max(agent["history"]) if agent["history"] else agent["capital"]
        trough = min(agent["history"]) if agent["history"] else agent["capital"]
        max_dd = (peak - trough) / peak if peak > 0 else 0

        results.append({
            "agent_id": agent["id"],
            "strategy": agent["strategy"],
            "lookback": agent["lookback"],
            "threshold": agent["threshold"],
            "final_capital": round(agent["capital"], 2),
            "roi": round(roi, 4),
            "trades": agent["trades"],
            "max_drawdown": round(max_dd, 4),
        })

    return results, prices


def run_mirofish_simulation(num_agents, num_rounds, market, params):
    """Run MiroFish simulation if available."""
    config = {
        "num_agents": num_agents,
        "num_rounds": num_rounds,
        "market_type": market,
        "ollama_model": params.get("model", "qwen2.5:14b"),
        "neo4j_uri": "bolt://localhost:7687",
        "neo4j_user": "neo4j",
        "neo4j_password": "nexus_password",
        **params,
    }

    config_path = SIMULATIONS_DIR / "current_config.json"
    with open(config_path, "w") as f:
        json.dump(config, f, indent=2)

    result = subprocess.run(
        [sys.executable, str(MIROFISH_DIR / "run.py"), "--config", str(config_path)],
        capture_output=True,
        text=True,
        timeout=3600,
        cwd=str(MIROFISH_DIR),
    )

    if result.returncode != 0:
        raise RuntimeError(f"MiroFish failed: {result.stderr}")

    return json.loads(result.stdout), None


def analyze_results(results, prices=None):
    """Compute aggregate statistics from simulation results."""
    import statistics

    rois = [r["roi"] for r in results]
    strategies = {}
    for r in results:
        s = r.get("strategy", "unknown")
        if s not in strategies:
            strategies[s] = []
        strategies[s].append(r["roi"])

    mean_roi = statistics.mean(rois)
    std_roi = statistics.stdev(rois) if len(rois) > 1 else 0
    sharpe = (mean_roi / std_roi) * (252 ** 0.5) if std_roi > 0 else 0

    strategy_summary = {}
    for s, s_rois in strategies.items():
        strategy_summary[s] = {
            "count": len(s_rois),
            "mean_roi": round(statistics.mean(s_rois) * 100, 2),
            "win_rate": round(sum(1 for r in s_rois if r > 0) / len(s_rois) * 100, 1),
        }

    best = max(results, key=lambda r: r["roi"])
    worst = min(results, key=lambda r: r["roi"])

    return {
        "total_agents": len(results),
        "mean_roi_pct": round(mean_roi * 100, 2),
        "std_roi_pct": round(std_roi * 100, 2),
        "sharpe_ratio": round(sharpe, 3),
        "win_rate_pct": round(sum(1 for r in rois if r > 0) / len(rois) * 100, 1),
        "best_agent": {
            "id": best["agent_id"],
            "roi_pct": round(best["roi"] * 100, 2),
            "strategy": best.get("strategy"),
            "params": {k: v for k, v in best.items() if k in ("lookback", "threshold")},
        },
        "worst_agent": {
            "id": worst["agent_id"],
            "roi_pct": round(worst["roi"] * 100, 2),
        },
        "strategy_breakdown": strategy_summary,
    }


def main():
    parser = argparse.ArgumentParser(description="Nexus Simulation Runner")
    parser.add_argument("--agents", type=int, default=100, help="Number of agents")
    parser.add_argument("--rounds", type=int, default=50, help="Number of rounds")
    parser.add_argument("--market", default="crypto", help="Market type")
    parser.add_argument("--strategy", default=None, help="Strategy file path")
    parser.add_argument("--params", default="{}", help="JSON params string")
    args = parser.parse_args()

    params = json.loads(args.params)
    if args.strategy:
        params["strategy_file"] = args.strategy

    sim_id = hashlib.md5(f"{args.agents}{args.rounds}{args.market}{time.time()}".encode()).hexdigest()[:12]
    start_time = time.time()

    print(f"[simulation] Starting run {sim_id}: {args.agents} agents, {args.rounds} rounds, {args.market} market")

    # Try MiroFish first, fall back to built-in
    use_mirofish = MIROFISH_DIR.exists()
    if use_mirofish:
        issues = check_prerequisites()
        if issues:
            logger.warning(f"MiroFish prerequisites not met: {issues}")
            use_mirofish = False

    if use_mirofish:
        neo4j_ok = start_neo4j()
        if not neo4j_ok:
            logger.warning("Neo4j failed to start, using built-in simulation")
            use_mirofish = False

    try:
        if use_mirofish:
            results, prices = run_mirofish_simulation(args.agents, args.rounds, args.market, params)
        else:
            results, prices = run_builtin_simulation(args.agents, args.rounds, args.market, params)
    except Exception as e:
        print(json.dumps({"error": str(e), "simulation_id": sim_id}))
        sys.exit(1)

    duration = round(time.time() - start_time, 1)
    analysis = analyze_results(results, prices)

    output = {
        "simulation_id": sim_id,
        "engine": "mirofish" if use_mirofish else "builtin",
        "config": {
            "agents": args.agents,
            "rounds": args.rounds,
            "market": args.market,
        },
        "duration_seconds": duration,
        "summary": analysis,
        "timestamp": datetime.now(timezone.utc).isoformat(),
    }

    # Store in memory
    try:
        sys.path.insert(0, str(NEXUS_HOME / "scripts"))
        from memory_system import MemorySystem

        ms = MemorySystem(str(NEXUS_HOME))
        ms.store(
            content=(
                f"Simulation {sim_id}: {args.agents} agents, {args.rounds} rounds, {args.market} market. "
                f"Mean ROI: {analysis['mean_roi_pct']}%, Sharpe: {analysis['sharpe_ratio']}, "
                f"Win rate: {analysis['win_rate_pct']}%. Best strategy: {analysis['best_agent']['strategy']}"
            ),
            memory_type="strategic",
            tags=["simulation", args.market, f"agents-{args.agents}"],
            source="simulation-runner",
            importance=0.7,
        )
    except Exception as e:
        logger.warning(f"Could not store simulation results in memory: {e}")

    print(json.dumps(output, indent=2))


if __name__ == "__main__":
    main()
