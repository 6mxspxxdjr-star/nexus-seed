# Nexus Seed

Source repository for the Nexus Autonomous Intelligence System installer.

## Install

### One-command install
```bash
curl -fsSL https://raw.githubusercontent.com/6mxspxxdjr-star/nexus-seed/master/install.sh | bash
```

### From this repository
```bash
git clone https://github.com/6mxspxxdjr-star/nexus-seed.git
cd nexus-seed
bash install.sh
```

## What Gets Installed

The installer creates `~/nexus` (configurable via `NEXUS_HOME`) with:

- **Semantic Memory System** — ChromaDB vectors + Obsidian-compatible Markdown vault
- **4 AI Agents** — Strategist, Guardian, Worker, Evolution
- **9 Skills** — including 3 profit engines (trading sim, lead gen, content creator)
- **Simulation Engine** — Multi-agent economic simulations (built-in + MiroFish)
- **Architecture Optimizer** — Autoresearch integration for overnight parameter tuning
- **Nightly Consolidation** — Automatic memory cleanup via launchd/systemd

## Repository Structure

```
nexus-seed/
├── install.sh                    # Main installer (idempotent, cross-platform)
├── README.md                     # This file
├── scripts/
│   ├── memory_system.py          # Core semantic memory (full version)
│   ├── run_simulation.py         # Simulation wrapper (full version)
│   ├── nightly_consolidation.py  # Memory consolidation
│   ├── first-boot.sh             # First-boot wizard (full version)
│   └── test.sh                   # Validation test suite (full version)
├── agents/
│   ├── strategist/IDENTITY.md
│   ├── guardian/IDENTITY.md
│   ├── worker/IDENTITY.md
│   └── evolution/IDENTITY.md
├── skills/
│   ├── search-memory/            # SKILL.md + run
│   ├── store-memory/
│   ├── ask-questions/
│   ├── create-agent/
│   ├── run-simulation/
│   ├── guardian-review/
│   ├── trading-simulator/        # Profit engine
│   ├── lead-generator/           # Profit engine
│   └── content-creator/          # Profit engine
├── configs/
│   ├── openclaw.yaml             # Agent orchestration config
│   └── qmd.yaml                  # File indexing config
└── optimizer/
    ├── train.py                  # Mutable training script
    └── config.yaml               # Autoresearch search space
```

## Configuration

| Environment Variable | Default | Description |
|---------------------|---------|-------------|
| `NEXUS_HOME` | `~/nexus` | Installation directory |
| `NEXUS_SKIP_MODELS` | `0` | Set to `1` to skip Ollama model downloads |
| `NEXUS_SKIP_WIZARD` | `0` | Set to `1` to skip first-boot wizard |

## System Requirements

- **OS**: macOS (Intel/Apple Silicon) or Linux (x86_64/ARM64)
- **RAM**: 8GB minimum, 16GB+ recommended
- **Disk**: ~10GB for models + dependencies
- **Network**: Required for initial install and model downloads

## Post-Install

After installation, see `~/nexus/README.md` for usage instructions.
