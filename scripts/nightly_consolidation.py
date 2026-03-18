#!/usr/bin/env python3
"""
Nexus Nightly Memory Consolidation

Runs as a scheduled job (launchd on macOS, systemd on Linux) to:
1. Consolidate old, low-importance memories into summaries
2. Apply time decay to activation scores
3. Rebuild wikilink graph
4. Update vector indices
5. Aggregate RL signals into training batches
6. Generate daily memory statistics report
7. Clean up orphaned files

Usage:
    python nightly_consolidation.py [--days 7] [--min-importance 0.3] [--dry-run]
"""

import argparse
import json
import logging
import os
import sys
from datetime import datetime, timezone
from pathlib import Path

NEXUS_HOME = Path(os.environ.get("NEXUS_HOME", Path.home() / "nexus"))
sys.path.insert(0, str(NEXUS_HOME / "scripts"))

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(message)s",
    handlers=[
        logging.StreamHandler(),
        logging.FileHandler(NEXUS_HOME / "memory" / ".system" / "consolidation.log"),
    ],
)
logger = logging.getLogger("nexus.consolidation")


def run_consolidation(days_old: int = 7, min_importance: float = 0.3, dry_run: bool = False):
    """Run the full nightly consolidation pipeline."""
    from memory_system import MemorySystem

    ms = MemorySystem(str(NEXUS_HOME))
    report = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "dry_run": dry_run,
        "steps": [],
    }

    # Step 1: Get current stats
    stats_before = ms.stats()
    report["stats_before"] = stats_before
    logger.info(f"Before: {stats_before['total_vectors']} vectors, {stats_before['total_markdown_files']} files")

    # Step 2: Consolidate old memories (includes time decay)
    if not dry_run:
        result = ms.consolidate(days_old=days_old, min_importance=min_importance)
        report["steps"].append({
            "name": "consolidation",
            "consolidated": result["consolidated_count"],
            "archived": result["archived_count"],
            "summary_id": result["summary_id"],
            "decayed": result.get("decayed_count", 0),
        })
        logger.info(
            f"Consolidated {result['consolidated_count']} memories, "
            f"archived {result['archived_count']} files, "
            f"decayed {result.get('decayed_count', 0)} scores"
        )
    else:
        logger.info("[DRY RUN] Would consolidate old memories")

    # Step 3: Rebuild wikilink graph
    if not dry_run:
        link_count = ms.rebuild_link_graph()
        report["steps"].append({"name": "link_graph", "links_rebuilt": link_count})
        logger.info(f"Rebuilt link graph: {link_count} links")
    else:
        logger.info("[DRY RUN] Would rebuild link graph")

    # Step 4: Re-index any unindexed markdown files
    reindexed = 0
    memory_dir = NEXUS_HOME / "memory"
    for md_file in memory_dir.rglob("*.md"):
        if ".system" in str(md_file) or md_file.name.startswith("."):
            continue
        try:
            text = md_file.read_text(encoding="utf-8")
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    import yaml
                    meta = yaml.safe_load(parts[1]) or {}
                    mem_id = meta.get("id")
                    if mem_id and ms._collection:
                        existing = ms._collection.get(ids=[mem_id])
                        if not existing["ids"]:
                            content = parts[2].strip()
                            if not dry_run:
                                ms._index_in_chroma(
                                    memory_id=mem_id,
                                    content=content,
                                    memory_type=meta.get("type", "semantic"),
                                    tags=meta.get("tags", []),
                                    source=meta.get("source", "reindex"),
                                    importance=meta.get("importance", 0.5),
                                    timestamp=datetime.fromisoformat(
                                        meta.get("created", datetime.now(timezone.utc).isoformat())
                                    ),
                                )
                            reindexed += 1
        except Exception as e:
            logger.debug(f"Skipping {md_file}: {e}")

    report["steps"].append({"name": "reindex", "files_reindexed": reindexed})
    logger.info(f"Re-indexed {reindexed} files")

    # Step 5: Aggregate RL signals
    rl_signals_dir = memory_dir / "06_System" / "rl_signals"
    rl_aggregated = 0
    if rl_signals_dir.exists() and not dry_run:
        try:
            from rl_signals import aggregate_signals
            rl_aggregated = aggregate_signals(str(NEXUS_HOME))
            logger.info(f"Aggregated {rl_aggregated} RL signals into training batch")
        except ImportError:
            logger.debug("rl_signals module not available — skipping RL aggregation")
        except Exception as e:
            logger.warning(f"RL signal aggregation failed: {e}")

    report["steps"].append({"name": "rl_aggregation", "signals_aggregated": rl_aggregated})

    # Step 6: Clean up orphaned ChromaDB entries (no matching markdown file)
    orphaned = 0
    if ms._collection and not dry_run:
        try:
            all_items = ms._collection.get()
            all_md_ids = set()
            for md_file in memory_dir.rglob("*.md"):
                if ".system" not in str(md_file):
                    all_md_ids.add(md_file.stem.split("_")[2] if len(md_file.stem.split("_")) > 2 else "")
                    try:
                        text = md_file.read_text(encoding="utf-8")
                        if text.startswith("---"):
                            parts = text.split("---", 2)
                            if len(parts) >= 3:
                                import yaml
                                meta = yaml.safe_load(parts[1]) or {}
                                if meta.get("id"):
                                    all_md_ids.add(meta["id"])
                    except Exception:
                        pass

            for chroma_id in all_items["ids"]:
                # Strip section suffix for matching
                base_id = chroma_id.split("__s")[0]
                if base_id not in all_md_ids:
                    ms._collection.delete(ids=[chroma_id])
                    orphaned += 1
        except Exception as e:
            logger.warning(f"Orphan cleanup failed: {e}")

    report["steps"].append({"name": "cleanup", "orphaned_removed": orphaned})
    logger.info(f"Removed {orphaned} orphaned vector entries")

    # Step 7: Final stats
    stats_after = ms.stats()
    report["stats_after"] = stats_after
    logger.info(f"After: {stats_after['total_vectors']} vectors, {stats_after['total_markdown_files']} files")

    # Save report
    reports_dir = NEXUS_HOME / "memory" / ".system" / "reports"
    reports_dir.mkdir(parents=True, exist_ok=True)
    report_path = reports_dir / f"consolidation_{datetime.now().strftime('%Y%m%d')}.json"
    with open(report_path, "w") as f:
        json.dump(report, f, indent=2)

    logger.info(f"Report saved to {report_path}")
    return report


def main():
    parser = argparse.ArgumentParser(description="Nexus Nightly Consolidation")
    parser.add_argument("--days", type=int, default=7, help="Consolidate memories older than N days")
    parser.add_argument("--min-importance", type=float, default=0.3, help="Min importance threshold")
    parser.add_argument("--dry-run", action="store_true", help="Preview without making changes")
    args = parser.parse_args()

    report = run_consolidation(
        days_old=args.days,
        min_importance=args.min_importance,
        dry_run=args.dry_run,
    )
    print(json.dumps(report, indent=2))


if __name__ == "__main__":
    main()
