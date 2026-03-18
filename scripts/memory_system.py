#!/usr/bin/env python3
"""
Nexus Semantic Memory System

Unified memory interface combining:
- ChromaDB for vector search (with section-level indexing)
- BM25 lexical search for keyword matching
- Reciprocal Rank Fusion (RRF) for hybrid results
- Time decay on memory activation scores
- Wikilink graph for backlink boosting
- Markdown files for human-readable storage (Obsidian-compatible)
- Typed memory categories (episodic, semantic, procedural, strategic)

Usage:
    from memory_system import MemorySystem
    ms = MemorySystem("~/nexus")
    ms.store("Important finding", memory_type="strategic", tags=["trading"])
    results = ms.search("trading strategies", top_k=5)
    results = ms.search_hybrid("trading strategies", top_k=5)
"""

import hashlib
import json
import logging
import math
import os
import re
import sys
import uuid
from collections import Counter, defaultdict
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

import yaml

logger = logging.getLogger("nexus.memory")

# Default time decay parameter (half-life ~14 days)
DEFAULT_DECAY_LAMBDA = 0.05
# RRF fusion constant
RRF_K = 60


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
        "06_System": "System data including RL signals",
    }

    def __init__(self, nexus_home: Optional[str] = None, decay_lambda: float = DEFAULT_DECAY_LAMBDA):
        self.home = Path(nexus_home or os.environ.get("NEXUS_HOME", Path.home() / "nexus"))
        self.memory_dir = self.home / "memory"
        self.system_dir = self.memory_dir / ".system"
        self.db_path = self.system_dir / "chroma"
        self.link_graph_path = self.system_dir / "link_graph.json"
        self.decay_lambda = decay_lambda

        # Ensure directories exist
        self.system_dir.mkdir(parents=True, exist_ok=True)
        for subdir in self.VAULT_SUBDIRS:
            (self.memory_dir / subdir).mkdir(parents=True, exist_ok=True)

        # Initialize ChromaDB
        self._chroma_client = None
        self._collection = None
        self._init_chroma()

        # Load link graph
        self._link_graph = self._load_link_graph()

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

    # ========================================================================
    # Store
    # ========================================================================

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
        Indexes at section level (## headings) for granular retrieval.

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

        # Index in ChromaDB (section-level)
        chroma_ok = self._index_sections(
            memory_id=memory_id,
            content=content,
            memory_type=memory_type,
            tags=tags,
            source=source,
            importance=importance,
            timestamp=timestamp,
            file_path=str(md_path),
        )

        # Update link graph with any wikilinks
        self._update_links(memory_id, content)

        return {
            "id": memory_id,
            "status": "stored",
            "timestamp": timestamp.isoformat(),
            "file_path": str(md_path),
            "vector_indexed": chroma_ok,
        }

    # ========================================================================
    # Search
    # ========================================================================

    def search(
        self,
        query: str,
        top_k: int = 5,
        memory_type: Optional[str] = None,
        time_range: Optional[str] = None,
        **kwargs,
    ) -> list:
        """
        Search memories using vector similarity (original API preserved).

        Returns list of dicts with: id, content, similarity_score, timestamp, type, source
        """
        if not self._collection:
            return self._file_search(query, top_k, memory_type)

        where_filter = {}
        if memory_type:
            where_filter["memory_type"] = memory_type

        try:
            results = self._collection.query(
                query_texts=[query],
                n_results=top_k * 3,  # Over-fetch for dedup after section merging
                where=where_filter if where_filter else None,
            )
        except Exception as e:
            logger.warning(f"ChromaDB search failed: {e}")
            return self._file_search(query, top_k, memory_type)

        memories = self._chroma_results_to_memories(results)
        # Deduplicate by base memory ID and apply time decay
        memories = self._dedup_and_decay(memories)
        return memories[:top_k]

    def search_hybrid(
        self,
        query: str,
        top_k: int = 5,
        memory_type: Optional[str] = None,
    ) -> list:
        """
        Hybrid search combining semantic (ChromaDB) and lexical (BM25) results
        via Reciprocal Rank Fusion (RRF).

        Returns list of dicts with: id, content, hybrid_score, similarity_score,
        bm25_score, timestamp, type, source, section_heading
        """
        # Semantic search
        semantic_results = self.search(query, top_k=top_k * 2, memory_type=memory_type)

        # BM25 lexical search
        bm25_results = self._bm25_search(query, top_k=top_k * 2, memory_type=memory_type)

        # RRF fusion: score = Σ 1/(k + rank_i)
        scores = defaultdict(lambda: {"rrf": 0.0, "data": None})

        for rank, mem in enumerate(semantic_results):
            mid = mem["id"]
            scores[mid]["rrf"] += 1.0 / (RRF_K + rank + 1)
            scores[mid]["data"] = mem
            scores[mid]["semantic_rank"] = rank + 1

        for rank, mem in enumerate(bm25_results):
            mid = mem["id"]
            scores[mid]["rrf"] += 1.0 / (RRF_K + rank + 1)
            if scores[mid]["data"] is None:
                scores[mid]["data"] = mem
            scores[mid]["bm25_rank"] = rank + 1

        # Apply link graph boost
        for mid, entry in scores.items():
            backlink_count = len(self._link_graph.get(mid, {}).get("backlinks", []))
            if backlink_count > 0:
                entry["rrf"] *= 1 + 0.1 * min(backlink_count, 5)

        # Sort by RRF score
        ranked = sorted(scores.values(), key=lambda x: x["rrf"], reverse=True)

        results = []
        for entry in ranked[:top_k]:
            mem = entry["data"]
            mem["hybrid_score"] = round(entry["rrf"], 6)
            mem["bm25_score"] = round(1.0 / (RRF_K + entry.get("bm25_rank", top_k * 2 + 1)), 6)
            results.append(mem)

        return results

    def get_linked(self, memory_id: str) -> list:
        """Traverse backlinks to find memories linked from this one."""
        links = self._link_graph.get(memory_id, {})
        backlinks = links.get("backlinks", [])
        forward = links.get("links_to", [])

        result = []
        for linked_id in set(backlinks + forward):
            mem = self.recall(linked_id)
            if mem:
                result.append(mem)
        return result

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

    # ========================================================================
    # Consolidation & Time Decay
    # ========================================================================

    def consolidate(self, days_old: int = 7, min_importance: float = 0.3) -> dict:
        """
        Consolidate old, low-importance memories into summaries.
        Applies time decay to activation scores.
        Moves originals to archive, creates consolidated summary.

        Returns dict with: consolidated_count, archived_count, summary_id, decayed_count
        """
        archive_dir = self.memory_dir / "06_Archive"
        archive_dir.mkdir(parents=True, exist_ok=True)

        cutoff = datetime.now(timezone.utc).timestamp() - (days_old * 86400)
        to_consolidate = []
        decayed_count = 0

        # Apply time decay to all memories and find consolidation candidates
        if self._collection:
            try:
                all_items = self._collection.get(include=["metadatas", "documents"])
                now = datetime.now(timezone.utc)

                for i, mid in enumerate(all_items["ids"]):
                    meta = all_items["metadatas"][i]
                    ts = meta.get("timestamp", "")
                    importance = float(meta.get("importance", 0.5))
                    last_accessed = meta.get("last_accessed", ts)

                    # Apply time decay
                    try:
                        access_time = datetime.fromisoformat(last_accessed) if last_accessed else now
                        days_since = (now - access_time).total_seconds() / 86400
                        activation = importance * math.exp(-self.decay_lambda * days_since)

                        # Update activation in metadata
                        meta["activation"] = round(activation, 4)
                        self._collection.update(
                            ids=[mid],
                            metadatas=[meta],
                        )
                        decayed_count += 1
                    except (ValueError, TypeError):
                        activation = importance

                    # Check for consolidation
                    if activation < min_importance:
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
            return {"consolidated_count": 0, "archived_count": 0, "summary_id": None, "decayed_count": decayed_count}

        # Create consolidated summary
        summary_parts = [f"- [{m['id']}] {m['content'][:100]}..." for m in to_consolidate[:50]]
        summary_content = (
            f"Consolidated {len(to_consolidate)} memories older than {days_old} days "
            f"with activation < {min_importance}.\n\n## Entries\n" + "\n".join(summary_parts)
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
            for md_file in self.memory_dir.rglob(f"*{mem['id']}*"):
                if md_file.parent.name != "06_Archive":
                    dest = archive_dir / md_file.name
                    md_file.rename(dest)
                    archived += 1

            if self._collection:
                try:
                    self._collection.delete(ids=[mem["id"]])
                except Exception:
                    pass

        return {
            "consolidated_count": len(to_consolidate),
            "archived_count": archived,
            "summary_id": summary["id"],
            "decayed_count": decayed_count,
        }

    def rebuild_link_graph(self) -> int:
        """Rebuild the entire link graph from all markdown files. Returns link count."""
        self._link_graph = {}
        count = 0
        for md_file in self.memory_dir.rglob("*.md"):
            if ".system" in str(md_file):
                continue
            parsed = self._parse_markdown(md_file)
            if parsed:
                links = self._extract_wikilinks(parsed.get("content", ""))
                if links:
                    self._link_graph[parsed["id"]] = {
                        "links_to": links,
                        "backlinks": self._link_graph.get(parsed["id"], {}).get("backlinks", []),
                    }
                    for target in links:
                        if target not in self._link_graph:
                            self._link_graph[target] = {"links_to": [], "backlinks": []}
                        if parsed["id"] not in self._link_graph[target]["backlinks"]:
                            self._link_graph[target]["backlinks"].append(parsed["id"])
                    count += len(links)

        self._save_link_graph()
        return count

    def stats(self) -> dict:
        """Return memory system statistics."""
        total_vectors = 0
        if self._collection:
            try:
                total_vectors = self._collection.count()
            except Exception:
                pass

        md_count = sum(1 for _ in self.memory_dir.rglob("*.md") if ".system" not in str(_))
        link_count = sum(len(v.get("links_to", [])) for v in self._link_graph.values())

        return {
            "total_vectors": total_vectors,
            "total_markdown_files": md_count,
            "total_links": link_count,
            "vault_path": str(self.memory_dir),
            "chroma_path": str(self.db_path),
            "subdirectories": {
                name: sum(1 for _ in (self.memory_dir / name).rglob("*.md"))
                for name in self.VAULT_SUBDIRS
                if (self.memory_dir / name).exists()
            },
        }

    # ========================================================================
    # Private: Section-Level Indexing
    # ========================================================================

    def _index_sections(
        self, memory_id, content, memory_type, tags, source, importance, timestamp, file_path
    ) -> bool:
        """Index memory at section level. Each ## heading gets its own vector."""
        if not self._collection:
            return False

        sections = self._split_sections(content)
        if not sections:
            sections = [("", content)]

        try:
            ids = []
            documents = []
            metadatas = []

            for i, (heading, section_content) in enumerate(sections):
                section_id = memory_id if i == 0 and not heading else f"{memory_id}__s{i}"
                ids.append(section_id)
                documents.append(section_content)
                metadatas.append({
                    "memory_type": memory_type,
                    "tags": ",".join(tags),
                    "source": source,
                    "importance": importance,
                    "timestamp": timestamp.isoformat(),
                    "last_accessed": timestamp.isoformat(),
                    "base_memory_id": memory_id,
                    "section_heading": heading,
                    "file_path": file_path,
                })

            self._collection.upsert(ids=ids, documents=documents, metadatas=metadatas)
            return True
        except Exception as e:
            logger.warning(f"Section indexing failed: {e}")
            # Fallback to full-document indexing
            return self._index_in_chroma(memory_id, content, memory_type, tags, source, importance, timestamp)

    def _split_sections(self, content: str) -> list:
        """Split content by ## headings into (heading, content) tuples."""
        lines = content.split("\n")
        sections = []
        current_heading = ""
        current_lines = []

        for line in lines:
            if line.startswith("## "):
                if current_lines:
                    sections.append((current_heading, "\n".join(current_lines).strip()))
                current_heading = line[3:].strip()
                current_lines = [line]
            else:
                current_lines.append(line)

        if current_lines:
            text = "\n".join(current_lines).strip()
            if text:
                sections.append((current_heading, text))

        return sections

    def _index_in_chroma(self, memory_id, content, memory_type, tags, source, importance, timestamp) -> bool:
        """Index memory in ChromaDB for vector search (full document)."""
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
                    "last_accessed": timestamp.isoformat(),
                    "base_memory_id": memory_id,
                    "section_heading": "",
                }],
            )
            return True
        except Exception as e:
            logger.warning(f"ChromaDB indexing failed: {e}")
            return False

    # ========================================================================
    # Private: BM25 Search
    # ========================================================================

    def _bm25_search(self, query: str, top_k: int = 10, memory_type: Optional[str] = None) -> list:
        """BM25-style lexical search over markdown files."""
        query_terms = query.lower().split()
        if not query_terms:
            return []

        # Build simple inverted index + doc lengths
        docs = []
        total_len = 0
        for md_file in self.memory_dir.rglob("*.md"):
            if ".system" in str(md_file):
                continue
            parsed = self._parse_markdown(md_file)
            if not parsed:
                continue
            if memory_type and parsed.get("type") != memory_type:
                continue
            content_lower = parsed["content"].lower()
            terms = content_lower.split()
            docs.append({"parsed": parsed, "terms": terms, "term_freq": Counter(terms)})
            total_len += len(terms)

        if not docs:
            return []

        avg_dl = total_len / len(docs)
        k1, b = 1.5, 0.75

        # Compute IDF for query terms
        idf = {}
        for qt in query_terms:
            df = sum(1 for d in docs if qt in d["term_freq"])
            idf[qt] = math.log((len(docs) - df + 0.5) / (df + 0.5) + 1) if df > 0 else 0

        # Score each document
        for doc in docs:
            score = 0.0
            dl = len(doc["terms"])
            for qt in query_terms:
                tf = doc["term_freq"].get(qt, 0)
                if tf > 0:
                    numerator = tf * (k1 + 1)
                    denominator = tf + k1 * (1 - b + b * dl / avg_dl)
                    score += idf.get(qt, 0) * numerator / denominator
            doc["bm25_score"] = score

        docs.sort(key=lambda d: d["bm25_score"], reverse=True)

        results = []
        for doc in docs[:top_k]:
            if doc["bm25_score"] > 0:
                mem = doc["parsed"]
                mem["similarity_score"] = round(doc["bm25_score"], 4)
                results.append(mem)

        return results

    # ========================================================================
    # Private: Time Decay & Dedup
    # ========================================================================

    def _dedup_and_decay(self, memories: list) -> list:
        """Deduplicate section-level results by base memory ID and apply time decay."""
        now = datetime.now(timezone.utc)
        seen = {}

        for mem in memories:
            base_id = mem.get("id", "").split("__s")[0]
            score = mem.get("similarity_score", 0)

            # Apply time decay
            ts = mem.get("timestamp", "")
            if ts:
                try:
                    mem_time = datetime.fromisoformat(ts)
                    days_since = (now - mem_time).total_seconds() / 86400
                    decay = math.exp(-self.decay_lambda * days_since)
                    score *= decay
                except (ValueError, TypeError):
                    pass

            mem["similarity_score"] = round(score, 4)

            # Keep best-scoring section per base memory
            if base_id not in seen or score > seen[base_id]["similarity_score"]:
                result = dict(mem)
                result["id"] = base_id
                seen[base_id] = result

        results = sorted(seen.values(), key=lambda m: m["similarity_score"], reverse=True)
        return results

    def _chroma_results_to_memories(self, results) -> list:
        """Convert ChromaDB query results to memory dicts."""
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
                    "section_heading": meta.get("section_heading", ""),
                    "file_path": meta.get("file_path", ""),
                })
        return memories

    # ========================================================================
    # Private: Link Graph
    # ========================================================================

    def _extract_wikilinks(self, content: str) -> list:
        """Extract [[wikilink]] targets from content."""
        return re.findall(r'\[\[([^\]]+)\]\]', content)

    def _update_links(self, memory_id: str, content: str):
        """Parse wikilinks and update the link graph."""
        links = self._extract_wikilinks(content)
        if not links:
            return

        if memory_id not in self._link_graph:
            self._link_graph[memory_id] = {"links_to": [], "backlinks": []}
        self._link_graph[memory_id]["links_to"] = links

        for target in links:
            if target not in self._link_graph:
                self._link_graph[target] = {"links_to": [], "backlinks": []}
            if memory_id not in self._link_graph[target]["backlinks"]:
                self._link_graph[target]["backlinks"].append(memory_id)

        self._save_link_graph()

    def _load_link_graph(self) -> dict:
        """Load link graph from JSON sidecar."""
        if self.link_graph_path.exists():
            try:
                return json.loads(self.link_graph_path.read_text(encoding="utf-8"))
            except Exception:
                pass
        return {}

    def _save_link_graph(self):
        """Save link graph to JSON sidecar."""
        try:
            self.link_graph_path.write_text(
                json.dumps(self._link_graph, indent=2),
                encoding="utf-8",
            )
        except Exception as e:
            logger.warning(f"Failed to save link graph: {e}")

    # ========================================================================
    # Private: File operations
    # ========================================================================

    def _type_to_subdir(self, memory_type: str, source: str) -> str:
        """Map memory type to vault subdirectory."""
        mapping = {
            "episodic": "01_Conversations",
            "semantic": "02_Research",
            "procedural": "05_Decisions",
            "strategic": "04_Simulations",
        }
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
            "last_accessed": timestamp.isoformat(),
        }
        if metadata:
            frontmatter["metadata"] = metadata

        md_content = f"---\n{yaml.dump(frontmatter, default_flow_style=False)}---\n\n{content}\n"

        filepath.write_text(md_content, encoding="utf-8")
        return filepath

    def _file_search(self, query: str, top_k: int, memory_type: Optional[str] = None) -> list:
        """Fallback file-based search when ChromaDB is unavailable."""
        query_terms = set(query.lower().split())
        results = []

        for md_file in self.memory_dir.rglob("*.md"):
            if ".system" in str(md_file):
                continue
            try:
                text = md_file.read_text(encoding="utf-8").lower()
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


# ============================================================================
# CLI Interface
# ============================================================================

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
    search_p = sub.add_parser("search", help="Search memories (hybrid)")
    search_p.add_argument("query", help="Search query")
    search_p.add_argument("--top_k", type=int, default=5)
    search_p.add_argument("--type", default=None)
    search_p.add_argument("--mode", default="hybrid", choices=["hybrid", "semantic", "bm25"])

    # Recall command
    recall_p = sub.add_parser("recall", help="Recall a specific memory")
    recall_p.add_argument("memory_id", help="Memory ID")

    # Links command
    links_p = sub.add_parser("links", help="Get linked memories")
    links_p.add_argument("memory_id", help="Memory ID")

    # Stats command
    sub.add_parser("stats", help="Show memory statistics")

    # Consolidate command
    cons_p = sub.add_parser("consolidate", help="Consolidate old memories")
    cons_p.add_argument("--days", type=int, default=7)
    cons_p.add_argument("--min-importance", type=float, default=0.3)

    # Rebuild link graph
    sub.add_parser("rebuild-links", help="Rebuild wikilink graph")

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
        if args.mode == "hybrid":
            results = ms.search_hybrid(args.query, top_k=args.top_k, memory_type=args.type)
        elif args.mode == "bm25":
            results = ms._bm25_search(args.query, top_k=args.top_k, memory_type=args.type)
        else:
            results = ms.search(args.query, top_k=args.top_k, memory_type=args.type)
        print(json.dumps(results, indent=2, default=str))

    elif args.command == "recall":
        result = ms.recall(args.memory_id)
        if result:
            print(json.dumps(result, indent=2, default=str))
        else:
            print(f"Memory {args.memory_id} not found", file=sys.stderr)
            sys.exit(1)

    elif args.command == "links":
        results = ms.get_linked(args.memory_id)
        print(json.dumps(results, indent=2, default=str))

    elif args.command == "stats":
        print(json.dumps(ms.stats(), indent=2))

    elif args.command == "consolidate":
        result = ms.consolidate(days_old=args.days, min_importance=args.min_importance)
        print(json.dumps(result, indent=2, default=str))

    elif args.command == "rebuild-links":
        count = ms.rebuild_link_graph()
        print(json.dumps({"links_rebuilt": count}, indent=2))


if __name__ == "__main__":
    main()
