# store-memory

## Description
Store a new memory in the Nexus semantic memory system. Memories are indexed
for vector search and categorized by type.

## Parameters
- `content` (required): The memory content to store
- `memory_type` (optional, default="semantic"): One of: episodic, semantic, procedural, strategic
- `tags` (optional): Comma-separated tags for categorization
- `source` (optional): Where this memory originated (agent name, skill, user)
- `importance` (optional, default=0.5): Float 0-1 indicating importance for consolidation

## Usage
```bash
./run "Trading simulation showed 12% ROI on ETH strategy" --type strategic --tags "trading,eth,simulation"
./run "User prefers Telegram notifications" --type episodic --source "first-boot" --importance 0.8
```

## Returns
JSON object with: id, status, timestamp
