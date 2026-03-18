#!/usr/bin/env python3
"""
Nexus Semantic Memory System

Unified memory interface combining:
- ChromaDB for vector search
- Markdown files for human-readable storage (Obsidian-compatible)
- Typed memory categories (episodic, semantic, procedural, strategic)

Usage:
    from memory_system import MemorySystem
    ms = MemorySystem("~/nexus")
    ms.store("Important finding", memory_type="strategic", tags=["trading"])
    results = ms.search("trading strategies", top_k=5)
"""

import hashlib
import json
import logging
import os
import re
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("nexus.memory")


class MemorySystem:
    """Unified semantic memory with vector search and markdown storage."""

    MEMORY_TYPES = ("episodic", "semantic", "procedural", "strategic")

    VAULT_SUBDIRS = {
        "00_Core": "System configuration and identity documents",
        "01_Conversations": "Conversation logs and interaction history",
        "02_Research": "Research findings and analysis",
        "03_Content": "Generated content and drafts",
        "04_Simulations": "Simulation results and parameters",
        "05_Decisions": "Decision logs and guardian reviews",
        "06_Archive": "Consolidated and archived memories",
    }

    def __init__(self, nexus_home: Optional[str] = None):
        self.home = Path(nexus_home or os.environ.get("NEXUS_HOME", Path.home() / "nexus"))
        self.memory_dir = self.home / "memory"
        self.system_dir = self.memory_dir / ".system"
        self.db_path = self.system_dir / "chroma"

        # Ensure directories exist
        self.system_dir.mkdir(parents=True, exist_ok=True)
        for subdir in self.VAULT_SUBDIRS:
            (self.memory_dir / subdir).mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB
        self._chroma_client = None
        self._collection = None
        self._init_chroma()

    def _init_chroma(self):
        """Initialize ChromaDB with persistent storage."""
        try:
            import chromadb
            from chromadb.config import Settings

            self._chroma_client = chromadb.PersistentClient(
                path=str(self.db_path),
                settings=Settings(anonymized_telemetry=False),
            )
            self._collection = self._chroma_client.get_or_create_collection(
                name="nexus_memory",
                metadata={"hnsw:space": "cosine"},
            )
            logger.info(f"ChromaDB initialized at {self.db_path}")
        except ImportError:
            logger.warning("ChromaDB not installed — vector search disabled")
        except Exception as e:
            logger.warning(f"ChromaDB init failed: {e} — vector search disabled")

    def store(
        self,
        content: str,
        memory_type: str = "semantic",
        tags: Optional[list] = None,
        source: str = "unknown",
        importance: float = 0.5,
        metadata: Optional[dict] = None,
    ) -> dict:
        """
        Store a memory in both markdown vault and vector database.

        Returns dict with: id, status, timestamp, file_path
        """
        if memory_type not in self.MEMORY_TYPES:
            raise ValueError(f"Invalid memory_type: {memory_type}. Must be one of {self.MEMORY_TYPES}")

        memory_id = str(uuid.uuid4())[:12]
        timestamp = datetime.now(timezone.utc)
        tags = tags or []

        # Determine vault subdirectory based on type/source
        subdir = self._type_to_subdir(memory_type, source)

        # Write markdown file
        md_path = self._write_markdown(
            memory_id=memory_id,
            content=content,
            memory_type=memory_type,
            tags=tags,
            source=source,
            importance=importance,
            timestamp=timestamp,
            subdir=subdir,
            metadata=metadata,
        )

        # Index in ChromaDB
        chroma_ok = self._index_in_chroma(
            memory_id=memory_id,
            content=content,
            memory_type=memory_type,
            tags=tags,
            source=source,
            importance=importance,
            timestamp=timestamp,
        )

        return {
            "id": memory_id,
            "status": "stored",
            "timestamp": timestamp.isoformat(),
            "file_path": str(md_path),
            "vector_indexed": chroma_ok,
        }

    def search(
        self,
        query: str,
        top_k: int = 5,
        memory_type: Optional[str] = None,
        time_range: Optional[str] = None,
        **kwargs,
    ) -> list:
        """
        Search memories using vector similarity.

        Returns list of dicts with: id, content, similarity_score, timestamp, type, source
        """
        if not self._collection:
            # Fallback to file-based search
            return self._file_search(query, top_k, memory_type)

        where_filter = {}
        if memory_type:
            where_filter["memory_type"] = memory_type

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=top_k,
                where=where_filter if where_filter else None,
            )
        except Exception as e:
            logger.warning(f"ChromaDB search failed: {e}")
            return self._file_search(query, top_k, memory_type)

        memories = []
        if results and results["ids"] and results["ids"][0]:
            for i, mid in enumerate(results["ids"][0]):
                meta = results["metadatas"][0][i] if results["metadatas"] else {}
                dist = results["distances"][0][i] if results["distances"] else 1.0
                doc = results["documents"][0][i] if results["documents"] else ""
                memories.append({
                    "id": mid,
                    "content": doc,
                    "similarity_score": round(1 - dist, 4),
                    "timestamp": meta.get("timestamp", ""),
                    "type": meta.get("memory_type", "unknown"),
                    "source": meta.get("source", "unknown"),
                    "importance": meta.get("importance", 0.5),
                })

        return sorted(memories, key=lambda m: m["similarity_score"], reverse=True)

    def recall(self, memory_id: str) -> Optional[dict]:
        """Retrieve a specific memory by ID."""
        if self._collection:
            try:
                result = self._collection.get(ids=[memory_id])
                if result["ids"]:
                    meta = result["metadatas"][0] if result["metadatas"] else {}
                    return {
                        "id": memory_id,
                        "content": result["documents"][0] if result["documents"] else "",
                        "type": meta.get("memory_type", "unknown"),
                        "source": meta.get("source", "unknown"),
                        "timestamp": meta.get("timestamp", ""),
                        "importance": meta.get("importance", 0.5),
                        "tags": meta.get("tags", ""),
                    }
            except Exception:
                pass

        # Fallback: search markdown files
        for md_file in self.memory_dir.rglob("*.md"):
            if memory_id in md_file.name:
                return self._parse_markdown(md_file)
        return None

    def consolidate(self, days_old: int = 7, min_importance: float = 0.3) -> dict:
        """
        Consolidate old, low-importance memories into summaries.
        Moves originals to archive, creates consolidated summary.

        Returns dict with: consolidated_count, archived_count, summary_id
        """
        archive_dir = self.memory_dir / "06_Archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        cutoff = datetime.now(timezone.utc).timestamp() - (days_old * 86400)
        to_consolidate = []

        # Find old, low-importance memories
        if self._collection:
            try:
                all_items = self._collection.get(include=["metadatas", "documents"])
                for i, mid in enumerate(all_items["ids"]):
                    meta = all_items["metadatas"][i]
                    ts = meta.get("timestamp", "")
                    importance = float(meta.get("importance", 0.5))
                    if importance < min_importance:
                        try:
                            mem_time = datetime.fromisoformat(ts).timestamp()
                            if mem_time < cutoff:
                                to_consolidate.append({
                                    "id": mid,
                                    "content": all_items["documents"][i],
                                    "metadata": meta,
                                })
                        except (ValueError, TypeError):
                            pass
            except Exception as e:
                logger.warning(f"Consolidation query failed: {e}")

        if not to_consolidate:
            return {"consolidated_count": 0, "archived_count": 0, "summary_id": None}

        # Create consolidated summary
        summary_parts = [f"- [{m['id']}] {m['content'][:100]}..." for m in to_consolidate[:50]]
        summary_content = (
            f"Consolidated {len(to_consolidate)} memories older than {days_old} days "
            f"with importance < {min_importance}.\n\n## Entries\n" + "\n".join(summary_parts)
        )

        summary = self.store(
            content=summary_content,
            memory_type="semantic",
            tags=["consolidation", "archive"],
            source="consolidation-engine",
            importance=0.6,
        )

        # Archive originals (move markdown files, remove from chroma)
        archived = 0
        for mem in to_consolidate:
            # Move markdown file if it exists
            for md_file in self.memory_dir.rglob(f"*{mem['id']}*"):
                if md_file.parent.name != "06_Archive":
                    dest = archive_dir / md_file.name
                    md_file.rename(dest)
                    archived += 1

            # Remove from ChromaDB
            if self._collection:
                try:
                    self._collection.delete(ids=[mem["id"]])
                except Exception:
                    pass

        return {
            "consolidated_count": len(to_consolidate),
            "archived_count": archived,
            "summary_id": summary["id"],
        }

    def stats(self) -> dict:
        """Return memory system statistics."""
        total_vectors = 0
        if self._collection:
            try:
                total_vectors = self._collection.count()
            except Exception:
                pass

        md_count = sum(1 for _ in self.memory_dir.rglob("*.md") if ".system" not in str(_))

        return {
            "total_vectors": total_vectors,
            "total_markdown_files": md_count,
            "vault_path": str(self.memory_dir),
            "chroma_path": str(self.db_path),
            "subdirectories": {
                name: sum(1 for _ in (self.memory_dir / name).rglob("*.md"))
                for name in self.VAULT_SUBDIRS
                if (self.memory_dir / name).exists()
            },
        }

    # === Private Methods ===

    def _type_to_subdir(self, memory_type: str, source: str) -> str:
        """Map memory type to vault subdirectory."""
        mapping = {
            "episodic": "01_Conversations",
            "semantic": "02_Research",
            "procedural": "05_Decisions",
            "strategic": "04_Simulations",
        }
        # Override for specific sources
        if "simulation" in source.lower():
            return "04_Simulations"
        if "content" in source.lower():
            return "03_Content"
        if "guardian" in source.lower():
            return "05_Decisions"
        return mapping.get(memory_type, "02_Research")

    def _write_markdown(
        self, memory_id, content, memory_type, tags, source, importance, timestamp, subdir, metadata=None
    ) -> Path:
        """Write memory as a markdown file with YAML frontmatter."""
        target_dir = self.memory_dir / subdir
        target_dir.mkdir(parents=True, exist_ok=True)

        # Create filename from timestamp and ID
        date_str = timestamp.strftime("%Y%m%d_%H%M%S")
        safe_preview = re.sub(r"[^a-z0-9]+", "-", content[:40].lower()).strip("-")
        filename = f"{date_str}_{memory_id}_{safe_preview}.md"
        filepath = target_dir / filename

        frontmatter = {
            "id": memory_id,
            "type": memory_type,
            "tags": tags,
            "source": source,
            "importance": importance,
            "created": timestamp.isoformat(),
        }
        if metadata:
            frontmatter["metadata"] = metadata

        md_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n{content}\n"

        filepath.write_text(md_content, encoding="utf-8")
        return filepath

    def _index_in_chroma(self, memory_id, content, memory_type, tags, source, importance, timestamp) -> bool:
        """Index memory in ChromaDB for vector search."""
        if not self._collection:
            return False

        try:
            self._collection.upsert(
                ids=[memory_id],
                documents=[content],
                metadatas=[{
                    "memory_type": memory_type,
                    "tags": ",".join(tags),
                    "source": source,
                    "importance": importance,
                    "timestamp": timestamp.isoformat(),
                }],
            )
            return True
        except Exception as e:
            logger.warning(f"ChromaDB indexing failed: {e}")
            return False

    def _file_search(self, query: str, top_k: int, memory_type: Optional[str] = None) -> list:
        """Fallback file-based search when ChromaDB is unavailable."""
        query_terms = set(query.lower().split())
        results = []

        for md_file in self.memory_dir.rglob("*.md"):
            if ".system" in str(md_file):
                continue
            try:
                text = md_file.read_text(encoding="utf-8").lower()
                # Simple term overlap scoring
                score = sum(1 for term in query_terms if term in text) / max(len(query_terms), 1)
                if score > 0:
                    parsed = self._parse_markdown(md_file)
                    if parsed and (not memory_type or parsed.get("type") == memory_type):
                        parsed["similarity_score"] = round(score, 4)
                        results.append(parsed)
            except Exception:
                continue

        results.sort(key=lambda r: r.get("similarity_score", 0), reverse=True)
        return results[:top_k]

    def _parse_markdown(self, filepath: Path) -> Optional[dict]:
        """Parse a markdown memory file with YAML frontmatter."""
        try:
            text = filepath.read_text(encoding="utf-8")
            if text.startswith("---"):
                parts = text.split("---", 2)
                if len(parts) >= 3:
                    meta = yaml.safe_load(parts[1]) or {}
                    content = parts[2].strip()
                    return {
                        "id": meta.get("id", filepath.stem),
                        "content": content,
                        "type": meta.get("type", "unknown"),
                        "source": meta.get("source", "unknown"),
                        "timestamp": meta.get("created", ""),
                        "importance": meta.get("importance", 0.5),
                        "tags": meta.get("tags", []),
                    }
            # No frontmatter — treat entire file as content
            return {
                "id": filepath.stem,
                "content": text[:500],
                "type": "unknown",
                "source": "file",
                "timestamp": "",
                "importance": 0.3,
            }
        except Exception:
            return None


# === CLI Interface ===

def main():
    """Command-line interface for the memory system."""
    import argparse

    parser = argparse.ArgumentParser(description="Nexus Memory System")
    parser.add_argument("--home", default=None, help="Nexus home directory")
    sub = parser.add_subparsers(dest="command")

    # Store command
    store_p = sub.add_parser("store", help="Store a memory")
    store_p.add_argument("content", help="Memory content")
    store_p.add_argument("--type", default="semantic", choices=MemorySystem.MEMORY_TYPES)
    store_p.add_argument("--tags", default="", help="Comma-separated tags")
    store_p.add_argument("--source", default="cli")
    store_p.add_argument("--importance", type=float, default=0.5)

    # Search command
    search_p = sub.add_parser("search", help="Search memories")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--top_k", type=int, default=5)
    search_p.add_argument("--type", default=None)

    # Recall command
    recall_p = sub.add_parser("recall", help="Recall a specific memory")
    recall_p.add_argument("memory_id", help="Memory ID")

    # Stats command
    sub.add_parser("stats", help="Show memory statistics")

    # Consolidate command
    cons_p = sub.add_parser("consolidate", help="Consolidate old memories")
    cons_p.add_argument("--days", type=int, default=7)
    cons_p.add_argument("--min-importance", type=float, default=0.3)

    args = parser.parse_args()
    if not args.command:
        parser.print_help()
        sys.exit(1)

    ms = MemorySystem(args.home)

    if args.command == "store":
        result = ms.store(
            content=args.content,
            memory_type=args.type,
            tags=[t.strip() for t in args.tags.split(",") if t.strip()],
            source=args.source,
            importance=args.importance,
        )
        print(json.dumps(result, indent=2, default=str))

    elif args.command == "search":
        results = ms.search(args.query, top_k=args.top_k, memory_type=args.type)
        print(json.dumps(results, indent=2, default=str))

    elif args.command == "recall":
        result = ms.recall(args.memory_id)
        if result:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Memory {args.memory_id} not found", file=sys.stderr)
            sys.exit(1)

    elif args.command == "stats":
        print(json.dumps(ms.stats(), indent=2))

    elif args.command == "consolidate":
        result = ms.consolidate(days_old=args.days, min_importance=args.min_importance)
        print(json.dumps(result, indent=2, default=str))


if __name__ == "__main__":
    main()
