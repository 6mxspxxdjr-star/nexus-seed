# search-memory

## Description
Search the Nexus semantic memory system using natural language queries.
Returns relevant memories ranked by similarity.

## Parameters
- `query` (required): Natural language search query
- `top_k` (optional, default=5): Number of results to return
- `memory_type` (optional): Filter by type (episodic, semantic, procedural, strategic)
- `time_range` (optional): Filter by date range (e.g., "last 7 days")

## Usage
```bash
./run "What were the results of the last trading simulation?"
./run --top_k 10 --type strategic "profit optimization strategies"
```

## Returns
JSON array of memory objects with fields: id, content, similarity_score, timestamp, type, source
