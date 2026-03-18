#!/usr/bin/env python3
"""
Nexus RL Signal Processing

Python-side signal processing for the OpenClaw-RL plugin:
- Reads JSONL signal files from memory/06_System/rl_signals/
- Aggregates signals into training batches
- Computes agent success rates and user satisfaction metrics
- Extracts OPD (On-Policy Distillation) correction pairs
- Provides metrics for the optimizer/train.py composite score

Usage:
    from rl_signals import RLSignalProcessor
    proc = RLSignalProcessor()
    metrics = proc.compute_metrics()
    pairs = proc.get_correction_pairs()

CLI:
    python rl_signals.py metrics
    python rl_signals.py aggregate
    python rl_signals.py corrections
    python rl_signals.py summary
"""

import json
import logging
import os
import sys
from collections import defaultdict
from datetime import datetime, timezone, timedelta
from pathlib import Path
from typing import Optional

logger = logging.getLogger("nexus.rl")


class RLSignalProcessor:
    """Processes RL signals captured by the openclaw-rl plugin."""

    def __init__(self, nexus_home: Optional[str] = None):
        self.home = Path(nexus_home or os.environ.get("NEXUS_HOME", Path.home() / "nexus"))
        self.signals_dir = self.home / "memory" / "06_System" / "rl_signals"
        self.signals_dir.mkdir(parents=True, exist_ok=True)

    def read_signals(self, days: int = 7) -> list:
        """Read all signals from the last N days."""
        cutoff = datetime.now(timezone.utc) - timedelta(days=days)
        signals = []

        for jsonl_file in sorted(self.signals_dir.glob("signals_*.jsonl")):
            # Check if file is within date range
            try:
                date_str = jsonl_file.stem.replace("signals_", "")
                file_date = datetime.strptime(date_str, "%Y-%m-%d").replace(tzinfo=timezone.utc)
                if file_date < cutoff:
                    continue
            except ValueError:
                continue

            try:
                for line in jsonl_file.read_text(encoding="utf-8").strip().split("\n"):
                    if line.strip():
                        signals.append(json.loads(line))
            except Exception as e:
                logger.warning(f"Failed to read {jsonl_file}: {e}")

        return signals

    def compute_metrics(self, days: int = 7) -> dict:
        """Compute aggregate RL metrics for the optimization pipeline."""
        signals = self.read_signals(days)
        if not signals:
            return {
                "total_signals": 0,
                "agent_success_rate": 0.0,
                "user_satisfaction": 0.0,
                "correction_rate": 0.0,
                "avg_reward": 0.0,
                "by_agent": {},
                "by_signal_type": {},
            }

        # Aggregate by agent
        by_agent = defaultdict(lambda: {"rewards": [], "corrections": 0, "confirmations": 0, "total": 0})
        by_type = defaultdict(int)

        rewards = []
        corrections = 0
        confirmations = 0

        for sig in signals:
            agent = sig.get("agent", "unknown")
            sig_type = sig.get("signal_type", "unknown")
            reward = sig.get("reward")
            by_type[sig_type] += 1
            by_agent[agent]["total"] += 1

            if reward is not None:
                rewards.append(reward)
                by_agent[agent]["rewards"].append(reward)

            if sig_type == "correction":
                corrections += 1
                by_agent[agent]["corrections"] += 1

            if sig.get("metadata", {}).get("is_confirmation"):
                confirmations += 1
                by_agent[agent]["confirmations"] += 1

        # Tool success rate
        tool_signals = [s for s in signals if s.get("signal_type") == "tool_result"]
        tool_successes = sum(1 for s in tool_signals if s.get("result") == "success")
        tool_success_rate = tool_successes / max(len(tool_signals), 1)

        # User satisfaction (confirmations / (confirmations + corrections))
        feedback_total = corrections + confirmations
        user_satisfaction = confirmations / max(feedback_total, 1)

        # Agent summaries
        agent_summaries = {}
        for agent, data in by_agent.items():
            agent_rewards = data["rewards"]
            agent_summaries[agent] = {
                "total_interactions": data["total"],
                "avg_reward": round(sum(agent_rewards) / max(len(agent_rewards), 1), 4),
                "corrections": data["corrections"],
                "confirmations": data["confirmations"],
            }

        return {
            "total_signals": len(signals),
            "agent_success_rate": round(tool_success_rate, 4),
            "user_satisfaction": round(user_satisfaction, 4),
            "correction_rate": round(corrections / max(len(signals), 1), 4),
            "avg_reward": round(sum(rewards) / max(len(rewards), 1), 4),
            "by_agent": agent_summaries,
            "by_signal_type": dict(by_type),
        }

    def get_correction_pairs(self, days: int = 7) -> list:
        """Extract (wrong_action, correct_action) pairs for OPD training."""
        signals = self.read_signals(days)
        pairs = []

        for sig in signals:
            if sig.get("signal_type") == "correction" and sig.get("metadata", {}).get("opd_pair"):
                pairs.append({
                    "timestamp": sig.get("timestamp"),
                    "agent": sig.get("agent"),
                    "wrong_action": sig.get("metadata", {}).get("wrong_action", ""),
                    "correct_action": sig.get("metadata", {}).get("correct_action", ""),
                    "context": sig.get("action", ""),
                })

        return pairs

    def get_training_batch(self, days: int = 1) -> dict:
        """Generate a training batch from recent signals for the Evolution agent."""
        signals = self.read_signals(days)

        # Group by agent
        agent_batches = defaultdict(list)
        for sig in signals:
            agent = sig.get("agent", "unknown")
            reward = sig.get("reward")
            if reward is not None:
                agent_batches[agent].append({
                    "action": sig.get("action", ""),
                    "result": sig.get("result", ""),
                    "reward": reward,
                    "model": sig.get("model_used", ""),
                })

        return {
            "generated_at": datetime.now(timezone.utc).isoformat(),
            "signal_count": len(signals),
            "agents": dict(agent_batches),
            "correction_pairs": self.get_correction_pairs(days),
        }


def aggregate_signals(nexus_home: Optional[str] = None) -> int:
    """Aggregate daily signals into a training batch. Called by nightly_consolidation."""
    proc = RLSignalProcessor(nexus_home)
    batch = proc.get_training_batch(days=1)

    if batch["signal_count"] == 0:
        return 0

    # Write batch file
    batches_dir = proc.signals_dir / "batches"
    batches_dir.mkdir(parents=True, exist_ok=True)
    batch_file = batches_dir / f"batch_{datetime.now().strftime('%Y%m%d')}.json"
    batch_file.write_text(json.dumps(batch, indent=2), encoding="utf-8")

    return batch["signal_count"]


# ============================================================================
# CLI
# ============================================================================

def main():
    import argparse

    parser = argparse.ArgumentParser(description="Nexus RL Signal Processing")
    parser.add_argument("--home", default=None, help="Nexus home directory")
    parser.add_argument("--days", type=int, default=7, help="Days of history to analyze")
    sub = parser.add_subparsers(dest="command")

    sub.add_parser("metrics", help="Compute RL metrics")
    sub.add_parser("aggregate", help="Aggregate signals into training batch")
    sub.add_parser("corrections", help="List correction pairs for OPD")
    sub.add_parser("summary", help="Brief summary of recent signals")

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    proc = RLSignalProcessor(args.home)

    if args.command == "metrics":
        metrics = proc.compute_metrics(args.days)
        print(json.dumps(metrics, indent=2))

    elif args.command == "aggregate":
        count = aggregate_signals(args.home)
        print(json.dumps({"aggregated": count}))

    elif args.command == "corrections":
        pairs = proc.get_correction_pairs(args.days)
        print(json.dumps(pairs, indent=2))

    elif args.command == "summary":
        metrics = proc.compute_metrics(args.days)
        print(f"Signals: {metrics['total_signals']} (last {args.days} days)")
        print(f"Tool success rate: {metrics['agent_success_rate']:.1%}")
        print(f"User satisfaction: {metrics['user_satisfaction']:.1%}")
        print(f"Avg reward: {metrics['avg_reward']:.3f}")
        print(f"Corrections: {metrics['correction_rate']:.1%}")
        if metrics["by_agent"]:
            print("\nPer-agent:")
            for agent, data in metrics["by_agent"].items():
                print(f"  {agent}: {data['total_interactions']} interactions, avg reward {data['avg_reward']:.3f}")


if __name__ == "__main__":
    main()
