# Nexus

Self-improving autonomous multi-agent system. Memory-first architecture, semantic search, agent-based simulation, and continuous learning — all running on your local hardware.

## Install

Pick your platform, paste the command, and go.

### Windows (CMD)

```
powershell -ExecutionPolicy Bypass -c "irm https://raw.githubusercontent.com/6mxspxxdjr-star/nexus-seed/master/install.ps1 | iex"
```

### Windows (PowerShell)

```powershell
irm https://raw.githubusercontent.com/6mxspxxdjr-star/nexus-seed/master/install.ps1 | iex
```

### Windows (WSL)

```bash
curl -fsSL https://raw.githubusercontent.com/6mxspxxdjr-star/nexus-seed/master/install.sh | bash
```

### macOS (Terminal)

```bash
curl -fsSL https://raw.githubusercontent.com/6mxspxxdjr-star/nexus-seed/master/install.sh | bash
```

### Linux (Ubuntu / Debian / Fedora / Arch)

```bash
curl -fsSL https://raw.githubusercontent.com/6mxspxxdjr-star/nexus-seed/master/install.sh | bash
```

### Raspberry Pi

```bash
curl -fsSL https://raw.githubusercontent.com/6mxspxxdjr-star/nexus-seed/master/install.sh | bash
```

> Smaller models are auto-selected on low-RAM devices (< 8GB).

### Manual install (any platform)

```bash
git clone https://github.com/6mxspxxdjr-star/nexus-seed.git
cd nexus-seed
# Linux/macOS/WSL:
bash install.sh
# Windows (from PowerShell):
.\install.ps1
```

## What Gets Installed

The installer creates `~/nexus` (or `%USERPROFILE%\nexus` on Windows) with:

- **Semantic Memory System** — ChromaDB vectors + Obsidian-compatible Markdown vault with hybrid search, time decay, and wikilink graphs
- **Model Router** — Intelligent routing across local models (0.5b/7b/14b) and cloud APIs (Claude Sonnet/Opus) based on task complexity
- **4 AI Agents** — Strategist, Guardian, Worker, Evolution with full identity protocols
- **9 Skills** — including 3 profit engines (trading simulator, lead generator, content creator)
- **Simulation Engine** — Multi-agent economic simulations (built-in + MiroFish)
- **OpenClaw-RL** — Continuous learning from user feedback
- **Architecture Optimizer** — Autoresearch for overnight parameter tuning
- **NemoClaw Security** — Sandboxed agent execution with filesystem, network, process, and inference isolation
- **Nightly Consolidation** — Automatic memory cleanup and strengthening

## Repository Structure

```
nexus-seed/
├── install.sh                    # Installer (macOS/Linux/WSL)
├── install.ps1                   # Installer (Windows)
├── launch.bat                    # Windows launcher
├── nexus_ui.py                   # Terminal UI with animated startup
├── scripts/
│   ├── memory_system.py          # Semantic memory (ChromaDB + markdown)
│   ├── model_router.py           # Intelligent model selection
│   ├── rl_signals.py             # OpenClaw-RL signal processing
│   ├── run_simulation.py         # Simulation engine wrapper
│   ├── nightly_consolidation.py  # Memory consolidation
│   ├── first-boot.sh             # First-boot wizard
│   └── test.sh                   # Validation test suite
├── agents/
│   ├── strategist/IDENTITY.md
│   ├── guardian/IDENTITY.md
│   ├── worker/IDENTITY.md
│   └── evolution/IDENTITY.md
├── skills/
│   ├── search-memory/            # Vector + hybrid memory search
│   ├── store-memory/             # Persistent memory storage
│   ├── ask-questions/            # RAG with local LLM
│   ├── create-agent/             # Agent creation (Guardian-gated)
│   ├── run-simulation/           # MiroFish simulation wrapper
│   ├── guardian-review/          # Triple-check review
│   ├── trading-simulator/        # Profit engine
│   ├── lead-generator/           # Profit engine
│   └── content-creator/          # Profit engine
├── configs/
│   ├── openclaw.yaml             # Agent orchestration config
│   ├── qmd.yaml                  # File indexing config
│   └── sandbox/                  # NemoClaw security policies
└── optimizer/
    ├── train.py                  # Mutable training script
    └── config.yaml               # Autoresearch search space
```

## Configuration

| Variable | Default | Description |
|----------|---------|-------------|
| `NEXUS_HOME` | `~/nexus` | Installation directory |
| `NEXUS_SKIP_MODELS` | `0` | Set to `1` to skip Ollama model downloads |
| `NEXUS_SKIP_WIZARD` | `0` | Set to `1` to skip first-boot wizard |

## System Requirements

| | Minimum | Recommended |
|---|---------|-------------|
| **OS** | Windows 10+, macOS 12+, Ubuntu 20.04+ | Any modern OS |
| **RAM** | 8 GB | 16 GB+ |
| **Disk** | ~10 GB | 20 GB+ |
| **Network** | Required for install | Required for cloud model routing |

The installer auto-detects your hardware and selects appropriate model sizes.

## Post-Install

Launch Nexus:
- **Windows**: Double-click the Nexus desktop shortcut, or run `%USERPROFILE%\nexus\.venv\Scripts\python.exe %USERPROFILE%\nexus\nexus_ui.py`
- **macOS/Linux**: `~/nexus/.venv/bin/python ~/nexus/nexus_ui.py`

## License

MIT
