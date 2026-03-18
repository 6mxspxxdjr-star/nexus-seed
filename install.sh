#!/usr/bin/env bash
# ============================================================================
# Nexus Installer
#
# One-command install: curl -fsSL https://raw.githubusercontent.com/6mxspxxdjr-star/nexus-seed/master/install.sh | bash
#
# This script:
#   1. Detects OS and architecture
#   2. Installs system dependencies (Homebrew, Python, Node, Ollama, etc.)
#   3. Creates the ~/nexus directory structure
#   4. Sets up Python virtual environment with all packages
#   5. Pulls required Ollama models
#   6. Deploys agent identities, skill definitions, and configs
#   7. Sets up nightly memory consolidation (launchd/systemd)
#   8. Initializes a git repository
#   9. Runs validation tests
#  10. Launches the first-boot wizard
#
# Idempotent: safe to run multiple times. Skips already-completed steps.
#
# Configuration:
#   NEXUS_HOME  — install directory (default: ~/nexus)
#   NEXUS_SKIP_MODELS — set to 1 to skip Ollama model pulls
#   NEXUS_SKIP_WIZARD — set to 1 to skip the first-boot wizard
# ============================================================================
set -euo pipefail

# === Configuration ===
NEXUS_HOME="${NEXUS_HOME:-$HOME/nexus}"
LOG_FILE="/tmp/nexus-install-$(date +%Y%m%d_%H%M%S).log"
PYTHON_VERSION="3.11"
REQUIRED_RAM_GB=8

# === Colors ===
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

# === Logging ===
exec > >(tee -a "$LOG_FILE") 2>&1

log()  { echo -e "${CYAN}[nexus]${NC} $*"; }
ok()   { echo -e "${GREEN}[  ok ]${NC} $*"; }
warn() { echo -e "${YELLOW}[ warn]${NC} $*"; }
err()  { echo -e "${RED}[error]${NC} $*"; }
step() { echo ""; echo -e "${BLUE}${BOLD}━━━ $* ━━━${NC}"; }

# === Error handler ===
trap 'err "Installation failed at line $LINENO. Log: $LOG_FILE"; exit 1' ERR

# === Banner ===
echo ""
echo -e "${CYAN}${BOLD}"
echo "  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗"
echo "  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝"
echo "  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗"
echo "  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║"
echo "  ██║ ╚████║███████╗██╔╝ ╚██╗╚██████╔╝███████║"
echo "  ╚═╝  ╚═══╝╚══════╝╚═╝   ╚═╝ ╚═════╝ ╚══════╝"
echo -e "${NC}"
echo -e "  ${BOLD}Autonomous Intelligence System — Installer${NC}"
echo -e "  Install log: ${LOG_FILE}"
echo ""

# ============================================================================
# PLATFORM DETECTION
# ============================================================================
step "Detecting Platform"

OS="unknown"
ARCH="unknown"
PKG_MANAGER=""

case "$(uname -s)" in
    Darwin)
        OS="macos"
        PKG_MANAGER="brew"
        ;;
    Linux)
        OS="linux"
        if command -v apt-get &>/dev/null; then
            PKG_MANAGER="apt"
        elif command -v dnf &>/dev/null; then
            PKG_MANAGER="dnf"
        elif command -v pacman &>/dev/null; then
            PKG_MANAGER="pacman"
        elif command -v apk &>/dev/null; then
            PKG_MANAGER="apk"
        fi
        ;;
    *)
        err "Unsupported OS: $(uname -s)"
        exit 1
        ;;
esac

case "$(uname -m)" in
    x86_64|amd64)  ARCH="x86_64" ;;
    arm64|aarch64) ARCH="arm64" ;;
    *)
        err "Unsupported architecture: $(uname -m)"
        exit 1
        ;;
esac

# Detect available RAM
if [[ "$OS" == "macos" ]]; then
    RAM_BYTES=$(sysctl -n hw.memsize 2>/dev/null || echo 0)
    RAM_GB=$(( RAM_BYTES / 1073741824 ))
else
    RAM_KB=$(grep MemTotal /proc/meminfo 2>/dev/null | awk '{print $2}' || echo 0)
    RAM_GB=$(( RAM_KB / 1048576 ))
fi

ok "OS: $OS ($ARCH)"
ok "RAM: ${RAM_GB}GB"
ok "Package manager: ${PKG_MANAGER:-none detected}"

if [[ $RAM_GB -lt $REQUIRED_RAM_GB ]]; then
    warn "Low RAM (${RAM_GB}GB < ${REQUIRED_RAM_GB}GB). Will use smaller models."
fi

# Choose Ollama model based on RAM
if [[ $RAM_GB -ge 16 ]]; then
    OLLAMA_LLM="qwen2.5:14b"
elif [[ $RAM_GB -ge 8 ]]; then
    OLLAMA_LLM="qwen2.5:7b"
else
    OLLAMA_LLM="qwen2.5:3b"
fi
log "Selected LLM model: $OLLAMA_LLM (based on ${RAM_GB}GB RAM)"

# ============================================================================
# DEPENDENCY INSTALLATION
# ============================================================================
step "Installing Dependencies"

command_exists() { command -v "$1" &>/dev/null; }

# --- Homebrew (macOS) ---
if [[ "$OS" == "macos" ]] && ! command_exists brew; then
    log "Installing Homebrew..."
    /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)"
    # Add to PATH for this session
    if [[ "$ARCH" == "arm64" ]]; then
        eval "$(/opt/homebrew/bin/brew shellenv)"
    else
        eval "$(/usr/local/bin/brew shellenv)"
    fi
    ok "Homebrew installed"
else
    ok "Homebrew: $(brew --version 2>/dev/null | head -1 || echo 'skipped (Linux)')"
fi

# --- Git ---
if ! command_exists git; then
    log "Installing git..."
    case "$PKG_MANAGER" in
        brew)   brew install git ;;
        apt)    sudo apt-get update -qq && sudo apt-get install -y -qq git ;;
        dnf)    sudo dnf install -y git ;;
        pacman) sudo pacman -S --noconfirm git ;;
        apk)    sudo apk add git ;;
    esac
fi
ok "Git: $(git --version)"

# --- Python 3.11+ ---
install_python() {
    log "Installing Python ${PYTHON_VERSION}..."
    case "$PKG_MANAGER" in
        brew)
            brew install "python@${PYTHON_VERSION}"
            ;;
        apt)
            sudo apt-get update -qq
            sudo apt-get install -y -qq software-properties-common
            sudo add-apt-repository -y ppa:deadsnakes/ppa 2>/dev/null || true
            sudo apt-get update -qq
            sudo apt-get install -y -qq "python${PYTHON_VERSION}" "python${PYTHON_VERSION}-venv" "python${PYTHON_VERSION}-dev"
            ;;
        dnf)
            sudo dnf install -y "python${PYTHON_VERSION}" "python${PYTHON_VERSION}-devel"
            ;;
        pacman)
            sudo pacman -S --noconfirm python
            ;;
        apk)
            sudo apk add "python3" "python3-dev" "py3-pip"
            ;;
    esac
}

# Find Python 3.11+
PYTHON_CMD=""
for cmd in "python${PYTHON_VERSION}" "python3.12" "python3.11" "python3"; do
    if command_exists "$cmd"; then
        PY_VER=$("$cmd" -c "import sys; print(f'{sys.version_info.major}.{sys.version_info.minor}')" 2>/dev/null || echo "0.0")
        PY_MAJOR=$(echo "$PY_VER" | cut -d. -f1)
        PY_MINOR=$(echo "$PY_VER" | cut -d. -f2)
        if [[ "$PY_MAJOR" -ge 3 ]] && [[ "$PY_MINOR" -ge 11 ]]; then
            PYTHON_CMD="$cmd"
            break
        fi
    fi
done

if [[ -z "$PYTHON_CMD" ]]; then
    install_python
    PYTHON_CMD="python${PYTHON_VERSION}"
    if ! command_exists "$PYTHON_CMD"; then
        PYTHON_CMD="python3"
    fi
fi
ok "Python: $($PYTHON_CMD --version)"

# --- Node.js ---
if ! command_exists node; then
    log "Installing Node.js..."
    case "$PKG_MANAGER" in
        brew)   brew install node ;;
        apt)
            curl -fsSL https://deb.nodesource.com/setup_20.x | sudo -E bash -
            sudo apt-get install -y -qq nodejs
            ;;
        dnf)    sudo dnf install -y nodejs ;;
        pacman) sudo pacman -S --noconfirm nodejs npm ;;
        apk)    sudo apk add nodejs npm ;;
    esac
fi
ok "Node: $(node --version 2>/dev/null || echo 'not installed')"

# --- Ollama ---
if ! command_exists ollama; then
    log "Installing Ollama..."
    if [[ "$OS" == "macos" ]]; then
        brew install ollama
    else
        curl -fsSL https://ollama.ai/install.sh | sh
    fi
fi
ok "Ollama: $(ollama --version 2>/dev/null || echo 'installed')"

# --- Docker (optional, for MiroFish/Neo4j) ---
if ! command_exists docker; then
    warn "Docker not installed. MiroFish/Neo4j features will be limited."
    warn "Install Docker Desktop from https://docker.com/products/docker-desktop"
else
    ok "Docker: $(docker --version 2>&1 | head -1)"
fi

# ============================================================================
# DIRECTORY STRUCTURE
# ============================================================================
step "Creating Directory Structure"

mkdir -p "$NEXUS_HOME"/{memory/{00_Core,01_Conversations,02_Research,03_Content,04_Simulations,05_Decisions,06_Archive,.system/{chroma,reports}},agents/{strategist,guardian,worker,evolution},skills/{search-memory,store-memory,ask-questions,create-agent,run-simulation,guardian-review,trading-simulator,lead-generator,content-creator},configs,scripts,simulations,optimizer}

ok "Directory structure created at $NEXUS_HOME"

# ============================================================================
# PYTHON VIRTUAL ENVIRONMENT
# ============================================================================
step "Setting Up Python Environment"

VENV_DIR="$NEXUS_HOME/.venv"

if [[ ! -f "$VENV_DIR/bin/python" ]]; then
    log "Creating virtual environment..."
    "$PYTHON_CMD" -m venv "$VENV_DIR"
    ok "Virtual environment created"
else
    ok "Virtual environment already exists"
fi

VENV_PYTHON="$VENV_DIR/bin/python"
VENV_PIP="$VENV_DIR/bin/pip"

# Upgrade pip
"$VENV_PIP" install --upgrade pip setuptools wheel -q

# Install Python packages
log "Installing Python packages (this may take a few minutes)..."
"$VENV_PIP" install -q \
    chromadb \
    sentence-transformers \
    pyyaml \
    requests \
    numpy \
    || warn "Some packages failed to install — check log for details"

# Try optional packages (may not be available)
for pkg in "engramai[all]" "agentmem"; do
    "$VENV_PIP" install -q "$pkg" 2>/dev/null \
        || warn "Optional package $pkg not available — skipping"
done

ok "Python packages installed"
"$VENV_PIP" list --format=columns 2>/dev/null | head -20

# ============================================================================
# OLLAMA MODELS
# ============================================================================
step "Pulling Ollama Models"

if [[ "${NEXUS_SKIP_MODELS:-0}" == "1" ]]; then
    warn "Skipping model pulls (NEXUS_SKIP_MODELS=1)"
else
    # Start Ollama if not running
    if ! curl -sf http://localhost:11434/api/tags &>/dev/null; then
        log "Starting Ollama server..."
        if [[ "$OS" == "macos" ]]; then
            open -a Ollama 2>/dev/null || ollama serve &>/dev/null &
        else
            ollama serve &>/dev/null &
        fi
        # Wait for server
        for i in $(seq 1 30); do
            if curl -sf http://localhost:11434/api/tags &>/dev/null; then break; fi
            sleep 2
        done
    fi

    # Pull embedding model
    log "Pulling nomic-embed-text (embeddings)..."
    ollama pull nomic-embed-text 2>/dev/null && ok "nomic-embed-text ready" \
        || warn "Failed to pull nomic-embed-text"

    # Pull classifier model (always needed for model router)
    log "Pulling qwen2.5:0.5b (router classifier)..."
    ollama pull qwen2.5:0.5b 2>/dev/null && ok "qwen2.5:0.5b ready" \
        || warn "Failed to pull qwen2.5:0.5b"

    # Pull LLM
    log "Pulling $OLLAMA_LLM (this may take a while for first download)..."
    ollama pull "$OLLAMA_LLM" 2>/dev/null && ok "$OLLAMA_LLM ready" \
        || warn "Failed to pull $OLLAMA_LLM"
fi

# ============================================================================
# DEPLOY FILES
# ============================================================================
step "Deploying Nexus Files"

# Determine if we're running from the nexus-seed repo or standalone
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
FROM_REPO=false

if [[ -f "$SCRIPT_DIR/scripts/memory_system.py" ]]; then
    FROM_REPO=true
    log "Installing from local repository at $SCRIPT_DIR"
fi

deploy_file() {
    local src="$1"
    local dest="$2"
    local executable="${3:-false}"

    if [[ "$FROM_REPO" == true ]] && [[ -f "$SCRIPT_DIR/$src" ]]; then
        cp "$SCRIPT_DIR/$src" "$dest"
    else
        # File should already exist from heredoc generation below
        return 0
    fi

    if [[ "$executable" == true ]]; then
        chmod +x "$dest"
    fi
}

if [[ "$FROM_REPO" == true ]]; then
    # Copy from repo
    log "Copying files from repository..."

    # Scripts
    cp "$SCRIPT_DIR/scripts/memory_system.py" "$NEXUS_HOME/scripts/"
    cp "$SCRIPT_DIR/scripts/run_simulation.py" "$NEXUS_HOME/scripts/"
    cp "$SCRIPT_DIR/scripts/nightly_consolidation.py" "$NEXUS_HOME/scripts/"
    cp "$SCRIPT_DIR/scripts/model_router.py" "$NEXUS_HOME/scripts/"
    cp "$SCRIPT_DIR/scripts/rl_signals.py" "$NEXUS_HOME/scripts/"
    cp "$SCRIPT_DIR/scripts/setup_keys.py" "$NEXUS_HOME/scripts/"
    cp "$SCRIPT_DIR/scripts/update.py" "$NEXUS_HOME/scripts/"
    cp "$SCRIPT_DIR/scripts/first-boot.sh" "$NEXUS_HOME/scripts/"
    cp "$SCRIPT_DIR/scripts/test.sh" "$NEXUS_HOME/scripts/"
    chmod +x "$NEXUS_HOME/scripts/"*.sh

    # Agents
    for agent in strategist guardian worker evolution; do
        cp "$SCRIPT_DIR/agents/$agent/IDENTITY.md" "$NEXUS_HOME/agents/$agent/"
    done

    # Skills
    for skill in search-memory store-memory ask-questions create-agent run-simulation guardian-review trading-simulator lead-generator content-creator; do
        if [[ -d "$SCRIPT_DIR/skills/$skill" ]]; then
            cp "$SCRIPT_DIR/skills/$skill/"* "$NEXUS_HOME/skills/$skill/"
            chmod +x "$NEXUS_HOME/skills/$skill/run" 2>/dev/null || true
        fi
    done

    # Configs
    cp "$SCRIPT_DIR/configs/"*.yaml "$NEXUS_HOME/configs/" 2>/dev/null || true

    # Optimizer
    cp "$SCRIPT_DIR/optimizer/train.py" "$NEXUS_HOME/optimizer/"
    cp "$SCRIPT_DIR/optimizer/config.yaml" "$NEXUS_HOME/optimizer/"

    # README
    cp "$SCRIPT_DIR/README.md" "$NEXUS_HOME/" 2>/dev/null || true

    ok "All files deployed from repository"
else
    # Running standalone (curl | bash) — clone repo and re-run from there
    log "Standalone install detected. Cloning nexus-seed repo for full install..."
    CLONE_DIR="$(mktemp -d)/nexus-seed"
    if command -v git &>/dev/null; then
        git clone --depth 1 https://github.com/6mxspxxdjr-star/nexus-seed.git "$CLONE_DIR" \
            && ok "Repository cloned to $CLONE_DIR" \
            && exec bash "$CLONE_DIR/install.sh" \
            || warn "Git clone failed, falling back to minimal bootstrap"
    else
        warn "git not found, falling back to minimal bootstrap"
    fi

    # Fallback: generate files inline
    log "Generating files inline..."
    warn "Standalone install: generating minimal bootstrap files."
    warn "For the full install: git clone https://github.com/6mxspxxdjr-star/nexus-seed.git && cd nexus-seed && bash install.sh"

    cat > "$NEXUS_HOME/scripts/memory_system.py" << 'MEMORY_SYSTEM_EOF'
#!/usr/bin/env python3
"""Nexus Memory System — Bootstrap version. Replace with full version from repo."""
import hashlib, json, os, re, sys, uuid, yaml
from datetime import datetime, timezone
from pathlib import Path

class MemorySystem:
    MEMORY_TYPES = ("episodic", "semantic", "procedural", "strategic")
    VAULT_SUBDIRS = {"00_Core":"","01_Conversations":"","02_Research":"","03_Content":"","04_Simulations":"","05_Decisions":"","06_Archive":""}

    def __init__(self, nexus_home=None):
        self.home = Path(nexus_home or os.environ.get("NEXUS_HOME", Path.home()/"nexus"))
        self.memory_dir = self.home / "memory"
        self.system_dir = self.memory_dir / ".system"
        self.db_path = self.system_dir / "chroma"
        self.system_dir.mkdir(parents=True, exist_ok=True)
        for sd in self.VAULT_SUBDIRS:
            (self.memory_dir / sd).mkdir(parents=True, exist_ok=True)
        self._collection = None
        try:
            import chromadb
            from chromadb.config import Settings
            self._chroma_client = chromadb.PersistentClient(path=str(self.db_path), settings=Settings(anonymized_telemetry=False))
            self._collection = self._chroma_client.get_or_create_collection(name="nexus_memory", metadata={"hnsw:space":"cosine"})
        except Exception:
            pass

    def store(self, content, memory_type="semantic", tags=None, source="unknown", importance=0.5, metadata=None):
        tags = tags or []
        memory_id = str(uuid.uuid4())[:12]
        ts = datetime.now(timezone.utc)
        subdir = {"episodic":"01_Conversations","semantic":"02_Research","procedural":"05_Decisions","strategic":"04_Simulations"}.get(memory_type,"02_Research")
        target = self.memory_dir / subdir
        target.mkdir(parents=True, exist_ok=True)
        slug = re.sub(r'[^a-z0-9]+','-',content[:40].lower()).strip('-')
        fp = target / f"{ts.strftime('%Y%m%d_%H%M%S')}_{memory_id}_{slug}.md"
        fm = {"id":memory_id,"type":memory_type,"tags":tags,"source":source,"importance":importance,"created":ts.isoformat()}
        fp.write_text(f"---\n{yaml.dump(fm,default_flow_style=False)}---\n\n{content}\n")
        if self._collection:
            try:
                self._collection.upsert(ids=[memory_id], documents=[content], metadatas=[{"memory_type":memory_type,"tags":",".join(tags),"source":source,"importance":importance,"timestamp":ts.isoformat()}])
            except Exception:
                pass
        return {"id":memory_id,"status":"stored","timestamp":ts.isoformat(),"file_path":str(fp),"vector_indexed":self._collection is not None}

    def search(self, query, top_k=5, memory_type=None, **kw):
        if self._collection:
            try:
                where = {"memory_type":memory_type} if memory_type else None
                r = self._collection.query(query_texts=[query], n_results=top_k, where=where)
                if r and r["ids"] and r["ids"][0]:
                    return [{"id":r["ids"][0][i],"content":r["documents"][0][i],"similarity_score":round(1-r["distances"][0][i],4),"timestamp":r["metadatas"][0][i].get("timestamp",""),"type":r["metadatas"][0][i].get("memory_type",""),"source":r["metadatas"][0][i].get("source","")} for i in range(len(r["ids"][0]))]
            except Exception:
                pass
        # Fallback file search
        terms = set(query.lower().split())
        results = []
        for f in self.memory_dir.rglob("*.md"):
            if ".system" in str(f): continue
            try:
                txt = f.read_text().lower()
                score = sum(1 for t in terms if t in txt)/max(len(terms),1)
                if score > 0:
                    results.append({"id":f.stem,"content":txt[:200],"similarity_score":round(score,4),"timestamp":"","type":"unknown","source":"file"})
            except Exception:
                continue
        return sorted(results, key=lambda x:x["similarity_score"], reverse=True)[:top_k]

    def recall(self, memory_id):
        if self._collection:
            try:
                r = self._collection.get(ids=[memory_id])
                if r["ids"]:
                    m = r["metadatas"][0] if r["metadatas"] else {}
                    return {"id":memory_id,"content":r["documents"][0],"type":m.get("memory_type",""),"source":m.get("source",""),"timestamp":m.get("timestamp","")}
            except Exception:
                pass
        return None

    def consolidate(self, days_old=7, min_importance=0.3):
        return {"consolidated_count":0,"archived_count":0,"summary_id":None}

    def stats(self):
        vc = 0
        if self._collection:
            try: vc = self._collection.count()
            except: pass
        mc = sum(1 for _ in self.memory_dir.rglob("*.md") if ".system" not in str(_))
        return {"total_vectors":vc,"total_markdown_files":mc,"vault_path":str(self.memory_dir),"chroma_path":str(self.db_path)}

def main():
    import argparse
    p = argparse.ArgumentParser()
    p.add_argument("--home", default=None)
    s = p.add_subparsers(dest="cmd")
    st = s.add_parser("store"); st.add_argument("content"); st.add_argument("--type",default="semantic"); st.add_argument("--tags",default=""); st.add_argument("--source",default="cli"); st.add_argument("--importance",type=float,default=0.5)
    se = s.add_parser("search"); se.add_argument("query"); se.add_argument("--top_k",type=int,default=5); se.add_argument("--type",default=None)
    rc = s.add_parser("recall"); rc.add_argument("memory_id")
    s.add_parser("stats")
    s.add_parser("consolidate")
    a = p.parse_args()
    if not a.cmd: p.print_help(); sys.exit(1)
    ms = MemorySystem(a.home)
    if a.cmd=="store": print(json.dumps(ms.store(a.content, a.type, [t.strip() for t in a.tags.split(",") if t.strip()], a.source, a.importance), indent=2, default=str))
    elif a.cmd=="search": print(json.dumps(ms.search(a.query, a.top_k, a.type), indent=2, default=str))
    elif a.cmd=="recall": r=ms.recall(a.memory_id); print(json.dumps(r,indent=2,default=str) if r else "Not found")
    elif a.cmd=="stats": print(json.dumps(ms.stats(),indent=2))
    elif a.cmd=="consolidate": print(json.dumps(ms.consolidate(),indent=2,default=str))

if __name__=="__main__": main()
MEMORY_SYSTEM_EOF

    # --- Minimal run_simulation.py ---
    cat > "$NEXUS_HOME/scripts/run_simulation.py" << 'RUN_SIM_EOF'
#!/usr/bin/env python3
"""Nexus Simulation Runner — Bootstrap version."""
import argparse, hashlib, json, os, random, sys, time
from datetime import datetime, timezone
from pathlib import Path

NEXUS_HOME = Path(os.environ.get("NEXUS_HOME", Path.home()/"nexus"))

def run_builtin_simulation(num_agents, num_rounds, market, params):
    import numpy as np
    agents = [{"id":i,"capital":params.get("starting_capital",10000),"position":0,"strategy":random.choice(["momentum","mean-reversion","random","hold"]),"lookback":random.randint(3,20),"threshold":random.uniform(0.01,0.05),"trades":0,"history":[]} for i in range(num_agents)]
    price=100.0; prices=[price]
    drift = 0.0002 if market=="crypto" else 0.0001
    vol = 0.04 if market=="crypto" else 0.015
    for _ in range(num_rounds):
        price *= 1+random.gauss(drift,vol); prices.append(price)
    for rnd in range(1,num_rounds+1):
        ret = (prices[rnd]-prices[rnd-1])/prices[rnd-1]
        for a in agents:
            lb = min(a["lookback"],rnd)
            rets = [(prices[rnd-j]-prices[rnd-j-1])/prices[rnd-j-1] for j in range(lb)]
            sig = 0
            if a["strategy"]=="momentum": sig = 1 if np.mean(rets)>a["threshold"] else (-1 if np.mean(rets)<-a["threshold"] else 0)
            elif a["strategy"]=="mean-reversion": avg=np.mean(prices[max(0,rnd-lb):rnd+1]); dev=(prices[rnd]-avg)/avg; sig=-1 if dev>a["threshold"] else (1 if dev<-a["threshold"] else 0)
            elif a["strategy"]=="random": sig=random.choice([-1,0,1])
            if sig!=a["position"]: a["position"]=sig; a["trades"]+=1
            if a["position"]!=0: a["capital"]*=1+a["position"]*ret
            a["history"].append(a["capital"])
    results = []
    for a in agents:
        roi = (a["capital"]-params.get("starting_capital",10000))/params.get("starting_capital",10000)
        pk=max(a["history"]) if a["history"] else a["capital"]; tr=min(a["history"]) if a["history"] else a["capital"]
        results.append({"agent_id":a["id"],"strategy":a["strategy"],"lookback":a["lookback"],"threshold":a["threshold"],"final_capital":round(a["capital"],2),"roi":round(roi,4),"trades":a["trades"],"max_drawdown":round((pk-tr)/pk if pk>0 else 0,4)})
    return results, prices

def analyze_results(results, prices=None):
    import statistics, numpy as np
    rois=[r["roi"] for r in results]
    m=statistics.mean(rois); s=statistics.stdev(rois) if len(rois)>1 else 0
    sharpe=(m/s)*(252**0.5) if s>0 else 0
    best=max(results,key=lambda r:r["roi"]); worst=min(results,key=lambda r:r["roi"])
    strats={}
    for r in results:
        strats.setdefault(r.get("strategy","?"),[]).append(r["roi"])
    sb={s:{"count":len(v),"mean_roi":round(statistics.mean(v)*100,2),"win_rate":round(sum(1 for x in v if x>0)/len(v)*100,1)} for s,v in strats.items()}
    return {"total_agents":len(results),"mean_roi_pct":round(m*100,2),"std_roi_pct":round(s*100,2),"sharpe_ratio":round(sharpe,3),"win_rate_pct":round(sum(1 for r in rois if r>0)/len(rois)*100,1),"best_agent":{"id":best["agent_id"],"roi_pct":round(best["roi"]*100,2),"strategy":best.get("strategy"),"params":{k:v for k,v in best.items() if k in ("lookback","threshold")}},"worst_agent":{"id":worst["agent_id"],"roi_pct":round(worst["roi"]*100,2)},"strategy_breakdown":sb}

def main():
    p=argparse.ArgumentParser(); p.add_argument("--agents",type=int,default=100); p.add_argument("--rounds",type=int,default=50); p.add_argument("--market",default="crypto"); p.add_argument("--strategy",default=None); p.add_argument("--params",default="{}")
    a=p.parse_args(); params=json.loads(a.params)
    sid=hashlib.md5(f"{a.agents}{a.rounds}{a.market}{time.time()}".encode()).hexdigest()[:12]
    t0=time.time()
    results,prices=run_builtin_simulation(a.agents,a.rounds,a.market,params)
    analysis=analyze_results(results,prices)
    print(json.dumps({"simulation_id":sid,"engine":"builtin","config":{"agents":a.agents,"rounds":a.rounds,"market":a.market},"duration_seconds":round(time.time()-t0,1),"summary":analysis,"timestamp":datetime.now(timezone.utc).isoformat()},indent=2))

if __name__=="__main__": main()
RUN_SIM_EOF

    # --- first-boot.sh (inline minimal version) ---
    cat > "$NEXUS_HOME/scripts/first-boot.sh" << 'FIRSTBOOT_EOF'
#!/usr/bin/env bash
set -euo pipefail
NEXUS_HOME="${NEXUS_HOME:-$HOME/nexus}"
CONFIG_DIR="$NEXUS_HOME/configs"
USER_CONFIG="$CONFIG_DIR/user.yaml"
VENV_PYTHON="$NEXUS_HOME/.venv/bin/python"
RED='\033[0;31m'; GREEN='\033[0;32m'; BLUE='\033[0;34m'; CYAN='\033[0;36m'; YELLOW='\033[1;33m'; BOLD='\033[1m'; NC='\033[0m'
echo ""; echo -e "${CYAN}${BOLD}  Nexus — First Boot Setup${NC}"; echo ""
if [[ -f "$USER_CONFIG" ]]; then read -rp "Already configured. Reconfigure? (y/N): " r; [[ "${r,,}" != "y" ]] && exit 0; fi
mkdir -p "$CONFIG_DIR"
echo -e "${BLUE}${BOLD}Step 1/3: Who are you?${NC}"
read -rp "  Your name: " USER_NAME; while [[ -z "$USER_NAME" ]]; do read -rp "  Name: " USER_NAME; done
echo -e "\n${BLUE}${BOLD}Step 2/3: Interface${NC}"
echo "  1) Telegram  2) Discord  3) CLI only"
read -rp "  Choice [1/2/3]: " IC; INTERFACE="cli"; BT=""; DT=""
case "$IC" in
    1) INTERFACE="telegram"; echo "Create bot via @BotFather on Telegram"; read -rp "  Bot token: " BT; [[ -z "$BT" ]] && INTERFACE="cli" ;;
    2) INTERFACE="discord"; read -rp "  Bot token: " DT; [[ -z "$DT" ]] && INTERFACE="cli" ;;
esac
echo -e "\n${BLUE}${BOLD}Step 3/3: API Keys (optional)${NC}"
read -rp "  Anthropic API key: " AK; read -rp "  OpenAI API key: " OK
cat > "$USER_CONFIG" << EOF
user: {name: "$USER_NAME"}
interface: {type: "$INTERFACE", telegram: {bot_token: "$BT"}, discord: {bot_token: "$DT"}}
api_keys: {anthropic: "$AK", openai: "$OK"}
preferences: {notifications: true, auto_optimize: true}
EOF
chmod 600 "$USER_CONFIG"
: > "$NEXUS_HOME/.env"
[[ -n "$AK" ]] && echo "export ANTHROPIC_API_KEY='$AK'" >> "$NEXUS_HOME/.env"
[[ -n "$OK" ]] && echo "export OPENAI_API_KEY='$OK'" >> "$NEXUS_HOME/.env"
[[ -f "$NEXUS_HOME/.env" ]] && chmod 600 "$NEXUS_HOME/.env"
echo -e "\n${GREEN}${BOLD}Nexus configured! Run: $VENV_PYTHON $NEXUS_HOME/scripts/memory_system.py stats${NC}\n"
FIRSTBOOT_EOF
    chmod +x "$NEXUS_HOME/scripts/first-boot.sh"

    # --- test.sh (inline minimal version) ---
    cat > "$NEXUS_HOME/scripts/test.sh" << 'TEST_EOF'
#!/usr/bin/env bash
set -uo pipefail
NEXUS_HOME="${NEXUS_HOME:-$HOME/nexus}"; VP="$NEXUS_HOME/.venv/bin/python"
G='\033[0;32m'; R='\033[0;31m'; Y='\033[1;33m'; B='\033[1m'; N='\033[0m'
P=0; F=0; W=0
pass() { ((P++)); echo -e "  ${G}✓${N} $1"; }; fail() { ((F++)); echo -e "  ${R}✗${N} $1"; }; warn_() { ((W++)); echo -e "  ${Y}⚠${N} $1"; }
echo -e "\n${B}Nexus Tests${N}\n"
for d in memory agents skills configs scripts .venv; do [[ -d "$NEXUS_HOME/$d" ]] && pass "$d/" || fail "$d/"; done
[[ -x "$VP" ]] && pass "Python venv" || fail "Python venv"
for p in chromadb yaml requests; do "$VP" -c "import $p" 2>/dev/null && pass "pkg: $p" || fail "pkg: $p"; done
R=$("$VP" "$NEXUS_HOME/scripts/memory_system.py" store "test" --type semantic --source test 2>&1)
echo "$R" | grep -q stored && pass "Memory store" || fail "Memory store"
R=$("$VP" "$NEXUS_HOME/scripts/memory_system.py" stats 2>&1)
echo "$R" | grep -q total_vectors && pass "Memory stats" || fail "Memory stats"
R=$("$VP" "$NEXUS_HOME/scripts/run_simulation.py" --agents 10 --rounds 5 2>&1)
echo "$R" | grep -q simulation_id && pass "Simulation" || fail "Simulation"
for a in strategist guardian worker evolution; do [[ -f "$NEXUS_HOME/agents/$a/IDENTITY.md" ]] && pass "Agent: $a" || fail "Agent: $a"; done
command -v ollama &>/dev/null && pass "Ollama" || warn_ "Ollama missing"
echo -e "\n${B}Results: ${G}$P passed${N}, ${R}$F failed${N}, ${Y}$W warnings${N}\n"
[[ $F -eq 0 ]]
TEST_EOF
    chmod +x "$NEXUS_HOME/scripts/test.sh"

    # --- nightly_consolidation.py ---
    cat > "$NEXUS_HOME/scripts/nightly_consolidation.py" << 'CONSOLIDATE_EOF'
#!/usr/bin/env python3
"""Nightly consolidation — bootstrap version."""
import json, os, sys
from pathlib import Path
NEXUS_HOME = Path(os.environ.get("NEXUS_HOME", Path.home()/"nexus"))
sys.path.insert(0, str(NEXUS_HOME/"scripts"))
from memory_system import MemorySystem
ms = MemorySystem(str(NEXUS_HOME))
result = ms.consolidate()
print(json.dumps(result, indent=2, default=str))
CONSOLIDATE_EOF

    # --- Agent identities ---
    for agent in strategist guardian worker evolution; do
        cat > "$NEXUS_HOME/agents/$agent/IDENTITY.md" << EOF
# ${agent^} Agent

This is the ${agent} agent identity. For the full version, install from the nexus-seed repository.

## Role
$(case $agent in
    strategist) echo "Analyze data and recommend value-generating strategies." ;;
    guardian) echo "Review and approve/reject all critical system actions." ;;
    worker) echo "Execute tasks assigned by the Strategist." ;;
    evolution) echo "Continuously optimize system parameters and strategies." ;;
esac)

## Core Directives
- Log all actions to memory
- Critical actions require Guardian approval
- Report results accurately
EOF
    done

    # --- Skill stubs ---
    for skill in search-memory store-memory ask-questions create-agent run-simulation guardian-review trading-simulator lead-generator content-creator; do
        cat > "$NEXUS_HOME/skills/$skill/SKILL.md" << EOF
# $skill

Skill definition. For the full version, install from the nexus-seed repository.
EOF
        cat > "$NEXUS_HOME/skills/$skill/run" << EOF
#!/usr/bin/env bash
set -euo pipefail
NEXUS_HOME="\${NEXUS_HOME:-\$HOME/nexus}"
echo "Skill $skill — bootstrap stub. Install full version from nexus-seed repo."
EOF
        chmod +x "$NEXUS_HOME/skills/$skill/run"
    done

    # --- Configs ---
    cat > "$NEXUS_HOME/configs/openclaw.yaml" << 'EOF'
orchestrator:
  name: nexus
  version: "1.0.0"
  llm:
    provider: ollama
    model: auto
    endpoint: http://localhost:11434
  model_routing:
    enabled: true
    classifier_model: "qwen2.5:0.5b"
EOF

    cat > "$NEXUS_HOME/configs/qmd.yaml" << 'EOF'
qmd:
  version: "1.0"
  sources:
    - path: "${NEXUS_HOME}/memory"
      recursive: true
      extensions: [".md"]
EOF

    # --- Optimizer ---
    cat > "$NEXUS_HOME/optimizer/train.py" << 'EOF'
#!/usr/bin/env python3
"""Optimizer training script — bootstrap version."""
import json, os, sys, time
from pathlib import Path
NEXUS_HOME = Path(os.environ.get("NEXUS_HOME", Path.home()/"nexus"))
sys.path.insert(0, str(NEXUS_HOME/"scripts"))
from run_simulation import run_builtin_simulation, analyze_results
results, prices = run_builtin_simulation(100, 30, "crypto", {"starting_capital": 10000})
analysis = analyze_results(results, prices)
metric = (analysis["mean_roi_pct"]*0.4 + analysis["sharpe_ratio"]*30 + analysis["win_rate_pct"]*0.3) / 100
print(f"{metric:.6f}")
EOF

    cat > "$NEXUS_HOME/optimizer/config.yaml" << 'EOF'
autoresearch:
  train_script: "${NEXUS_HOME}/optimizer/train.py"
  objective: maximize
  schedule: {mode: overnight, start_hour: 0, end_hour: 6}
EOF

    ok "Bootstrap files generated (for full versions, use the nexus-seed repo)"
fi

# ============================================================================
# OPTIONAL: CLONE MIROFISH & AUTORESEARCH
# ============================================================================
step "Setting Up External Components"

# MiroFish (if repo is accessible)
if [[ ! -d "$NEXUS_HOME/simulations/MiroFish-Offline" ]]; then
    log "Attempting to clone MiroFish..."
    git clone --depth 1 https://github.com/mirofish/MiroFish-Offline.git \
        "$NEXUS_HOME/simulations/MiroFish-Offline" 2>/dev/null \
        && ok "MiroFish cloned" \
        || warn "MiroFish repo not available — using built-in simulation engine"
fi

# Autoresearch MLX
if [[ ! -d "$NEXUS_HOME/optimizer/autoresearch-mlx" ]]; then
    log "Attempting to clone autoresearch-mlx..."
    git clone --depth 1 https://github.com/autoresearch/autoresearch-mlx.git \
        "$NEXUS_HOME/optimizer/autoresearch-mlx" 2>/dev/null \
        && ok "autoresearch-mlx cloned" \
        || warn "autoresearch-mlx repo not available — using built-in optimizer"
fi

# NemoClaw / OpenClaw
if ! command_exists openclaw; then
    log "Attempting to install NemoClaw..."
    pip install nemoclaw 2>/dev/null \
        && ok "NemoClaw installed" \
        || warn "NemoClaw not available — agent orchestration will use config files"
fi

# ============================================================================
# NIGHTLY CONSOLIDATION SERVICE
# ============================================================================
step "Setting Up Scheduled Consolidation"

if [[ "$OS" == "macos" ]]; then
    PLIST_PATH="$HOME/Library/LaunchAgents/com.nexus.consolidation.plist"
    if [[ ! -f "$PLIST_PATH" ]]; then
        mkdir -p "$HOME/Library/LaunchAgents"
        cat > "$PLIST_PATH" << PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nexus.consolidation</string>
    <key>ProgramArguments</key>
    <array>
        <string>${NEXUS_HOME}/.venv/bin/python</string>
        <string>${NEXUS_HOME}/scripts/nightly_consolidation.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>3</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${NEXUS_HOME}/memory/.system/consolidation_stdout.log</string>
    <key>StandardErrorPath</key>
    <string>${NEXUS_HOME}/memory/.system/consolidation_stderr.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>NEXUS_HOME</key>
        <string>${NEXUS_HOME}</string>
    </dict>
</dict>
</plist>
PLIST_EOF
        launchctl load "$PLIST_PATH" 2>/dev/null || true
        ok "Nightly consolidation scheduled (launchd, 3:00 AM)"
    else
        ok "Consolidation schedule already exists"
    fi

elif [[ "$OS" == "linux" ]]; then
    # Use systemd timer if available, otherwise cron
    if command_exists systemctl; then
        TIMER_DIR="$HOME/.config/systemd/user"
        mkdir -p "$TIMER_DIR"

        cat > "$TIMER_DIR/nexus-consolidation.service" << SYSTEMD_SVC_EOF
[Unit]
Description=Nexus Nightly Memory Consolidation

[Service]
Type=oneshot
Environment=NEXUS_HOME=${NEXUS_HOME}
ExecStart=${NEXUS_HOME}/.venv/bin/python ${NEXUS_HOME}/scripts/nightly_consolidation.py
SYSTEMD_SVC_EOF

        cat > "$TIMER_DIR/nexus-consolidation.timer" << SYSTEMD_TMR_EOF
[Unit]
Description=Nexus consolidation timer

[Timer]
OnCalendar=*-*-* 03:00:00
Persistent=true

[Install]
WantedBy=timers.target
SYSTEMD_TMR_EOF

        systemctl --user daemon-reload 2>/dev/null || true
        systemctl --user enable nexus-consolidation.timer 2>/dev/null || true
        systemctl --user start nexus-consolidation.timer 2>/dev/null || true
        ok "Nightly consolidation scheduled (systemd timer, 3:00 AM)"
    else
        # Fallback to cron
        CRON_LINE="0 3 * * * NEXUS_HOME=$NEXUS_HOME $NEXUS_HOME/.venv/bin/python $NEXUS_HOME/scripts/nightly_consolidation.py >> $NEXUS_HOME/memory/.system/consolidation.log 2>&1"
        (crontab -l 2>/dev/null | grep -v "nexus.*consolidation"; echo "$CRON_LINE") | crontab -
        ok "Nightly consolidation scheduled (cron, 3:00 AM)"
    fi
fi

# ============================================================================
# EVOLUTION AGENT SCHEDULER (Autoresearch overnight)
# ============================================================================
step "Setting Up Evolution Agent Schedule"

if [[ "$OS" == "macos" ]]; then
    EVOL_PLIST="$HOME/Library/LaunchAgents/com.nexus.evolution.plist"
    if [[ ! -f "$EVOL_PLIST" ]]; then
        cat > "$EVOL_PLIST" << EVOL_PLIST_EOF
<?xml version="1.0" encoding="UTF-8"?>
<!DOCTYPE plist PUBLIC "-//Apple//DTD PLIST 1.0//EN" "http://www.apple.com/DTDs/PropertyList-1.0.dtd">
<plist version="1.0">
<dict>
    <key>Label</key>
    <string>com.nexus.evolution</string>
    <key>ProgramArguments</key>
    <array>
        <string>${NEXUS_HOME}/.venv/bin/python</string>
        <string>${NEXUS_HOME}/optimizer/train.py</string>
    </array>
    <key>StartCalendarInterval</key>
    <dict>
        <key>Hour</key>
        <integer>1</integer>
        <key>Minute</key>
        <integer>0</integer>
    </dict>
    <key>StandardOutPath</key>
    <string>${NEXUS_HOME}/optimizer/evolution.log</string>
    <key>StandardErrorPath</key>
    <string>${NEXUS_HOME}/optimizer/evolution.log</string>
    <key>EnvironmentVariables</key>
    <dict>
        <key>NEXUS_HOME</key>
        <string>${NEXUS_HOME}</string>
    </dict>
</dict>
</plist>
EVOL_PLIST_EOF
        launchctl load "$EVOL_PLIST" 2>/dev/null || true
        ok "Evolution agent scheduled (launchd, 1:00 AM)"
    else
        ok "Evolution schedule already exists"
    fi

elif [[ "$OS" == "linux" ]]; then
    if command_exists systemctl; then
        TIMER_DIR="$HOME/.config/systemd/user"
        mkdir -p "$TIMER_DIR"

        cat > "$TIMER_DIR/nexus-evolution.service" << EVOL_SVC_EOF
[Unit]
Description=Nexus Evolution Agent (Autoresearch)

[Service]
Type=oneshot
ExecStart=${NEXUS_HOME}/.venv/bin/python ${NEXUS_HOME}/optimizer/train.py
Environment=NEXUS_HOME=${NEXUS_HOME}
EVOL_SVC_EOF

        cat > "$TIMER_DIR/nexus-evolution.timer" << EVOL_TMR_EOF
[Unit]
Description=Nexus Evolution Agent Timer

[Timer]
OnCalendar=*-*-* 01:00:00
Persistent=true

[Install]
WantedBy=timers.target
EVOL_TMR_EOF

        systemctl --user daemon-reload 2>/dev/null || true
        systemctl --user enable nexus-evolution.timer 2>/dev/null || true
        systemctl --user start nexus-evolution.timer 2>/dev/null || true
        ok "Evolution agent scheduled (systemd timer, 1:00 AM)"
    else
        EVOL_CRON="0 1 * * * NEXUS_HOME=$NEXUS_HOME $NEXUS_HOME/.venv/bin/python $NEXUS_HOME/optimizer/train.py >> $NEXUS_HOME/optimizer/evolution.log 2>&1"
        (crontab -l 2>/dev/null | grep -v "nexus.*evolution"; echo "$EVOL_CRON") | crontab -
        ok "Evolution agent scheduled (cron, 1:00 AM)"
    fi
fi

# ============================================================================
# CREATE OBSIDIAN VAULT MARKER
# ============================================================================
step "Configuring Obsidian Integration"

OBSIDIAN_DIR="$NEXUS_HOME/memory/.obsidian"
if [[ ! -d "$OBSIDIAN_DIR" ]]; then
    mkdir -p "$OBSIDIAN_DIR"
    cat > "$OBSIDIAN_DIR/app.json" << 'OBSIDIAN_EOF'
{
  "alwaysUpdateLinks": true,
  "newLinkFormat": "relative",
  "useMarkdownLinks": false,
  "showFrontmatter": true
}
OBSIDIAN_EOF

    cat > "$OBSIDIAN_DIR/appearance.json" << 'OBSIDIAN_APP_EOF'
{
  "baseFontSize": 16,
  "theme": "obsidian"
}
OBSIDIAN_APP_EOF
    ok "Obsidian vault configured at $NEXUS_HOME/memory"
    log "Open Obsidian → 'Open folder as vault' → select $NEXUS_HOME/memory"
else
    ok "Obsidian vault already configured"
fi

# ============================================================================
# ENVIRONMENT SETUP
# ============================================================================
step "Configuring Environment"

# Add NEXUS_HOME to shell profile
SHELL_RC=""
if [[ -f "$HOME/.zshrc" ]]; then
    SHELL_RC="$HOME/.zshrc"
elif [[ -f "$HOME/.bashrc" ]]; then
    SHELL_RC="$HOME/.bashrc"
elif [[ -f "$HOME/.bash_profile" ]]; then
    SHELL_RC="$HOME/.bash_profile"
fi

if [[ -n "$SHELL_RC" ]]; then
    if ! grep -q "NEXUS_HOME" "$SHELL_RC" 2>/dev/null; then
        cat >> "$SHELL_RC" << RCEOF

# Nexus
export NEXUS_HOME="$NEXUS_HOME"
export PATH="\$NEXUS_HOME/.venv/bin:\$PATH"
[[ -f "\$NEXUS_HOME/.env" ]] && source "\$NEXUS_HOME/.env"
RCEOF
        ok "Added NEXUS_HOME to $SHELL_RC"
    else
        ok "NEXUS_HOME already in $SHELL_RC"
    fi
fi

# ============================================================================
# GIT REPOSITORY
# ============================================================================
step "Initializing Git Repository"

if [[ ! -d "$NEXUS_HOME/.git" ]]; then
    cd "$NEXUS_HOME"
    git init -q

    cat > "$NEXUS_HOME/.gitignore" << 'GITIGNORE_EOF'
# Python
.venv/
__pycache__/
*.pyc
*.pyo

# System databases
memory/.system/chroma/
memory/.system/qmd_index/
memory/.system/reports/
memory/.system/*.log

# Secrets
.env
configs/api_keys.yaml
configs/user.yaml

# Docker
simulations/neo4j-data/
simulations/neo4j-logs/

# OS
.DS_Store
Thumbs.db

# Obsidian
memory/.obsidian/workspace.json
memory/.obsidian/cache
GITIGNORE_EOF

    git add -A
    git commit -q -m "Initial Nexus installation

Includes:
- Semantic memory system (ChromaDB + Markdown vault)
- Agent identities (Strategist, Guardian, Worker, Evolution)
- Skill definitions (9 skills including profit engines)
- Simulation engine (built-in + MiroFish support)
- Architecture optimizer (autoresearch integration)
- Nightly consolidation schedule
- Obsidian-compatible memory vault"

    ok "Git repository initialized with initial commit"
else
    ok "Git repository already exists"
fi

# ============================================================================
# WRITE README
# ============================================================================
if [[ ! -f "$NEXUS_HOME/README.md" ]] || [[ "$FROM_REPO" == true ]]; then
    cat > "$NEXUS_HOME/README.md" << 'README_EOF'
# Nexus

Autonomous Intelligence System — self-improving multi-agent platform with
semantic memory, simulation engine, and profit-generating capabilities.

## Quick Start

```bash
# Run the first-boot wizard (if not already done)
bash ~/nexus/scripts/first-boot.sh

# Check system status
~/nexus/.venv/bin/python ~/nexus/scripts/test.sh

# Run a trading simulation
~/nexus/skills/trading-simulator/run --coin bitcoin --days 30

# Search your memory
~/nexus/.venv/bin/python ~/nexus/scripts/memory_system.py search "trading strategies"

# Store a memory
~/nexus/.venv/bin/python ~/nexus/scripts/memory_system.py store "Important finding" --type strategic
```

## Architecture

```
~/nexus/
├── memory/              # Obsidian-compatible markdown vault
│   ├── 00_Core/         # System configuration
│   ├── 01_Conversations/# Interaction logs
│   ├── 02_Research/     # Research findings
│   ├── 03_Content/      # Generated content
│   ├── 04_Simulations/  # Simulation results
│   ├── 05_Decisions/    # Guardian reviews
│   ├── 06_Archive/      # Consolidated memories
│   └── .system/         # ChromaDB, indexes, logs
├── agents/              # Agent identity files
│   ├── strategist/      # Decision-making agent
│   ├── guardian/        # Safety & review agent
│   ├── worker/          # Task execution agent
│   └── evolution/       # Self-improvement agent
├── skills/              # Executable skill modules
│   ├── trading-simulator/
│   ├── lead-generator/
│   ├── content-creator/
│   └── ... (6 more)
├── configs/             # System configuration
├── scripts/             # Core Python/bash scripts
├── simulations/         # MiroFish engine
├── optimizer/           # Autoresearch optimizer
└── .venv/               # Python virtual environment
```

## Agents

| Agent | Role | Auto-Start |
|-------|------|-----------|
| **Strategist** | Analyzes data, recommends strategies, coordinates work | Yes |
| **Guardian** | Reviews & approves critical actions (triple-check) | Yes |
| **Worker** | Executes tasks assigned by Strategist | On demand |
| **Evolution** | Continuously optimizes parameters & strategies | Yes |

## Profit Engines

### Trading Simulator
Backtests crypto trading strategies using multi-agent simulation.
```bash
~/nexus/skills/trading-simulator/run --coin ethereum --days 90 --strategy mean-reversion
```

### Lead Generator
Scrapes real estate data and enriches with skip-trace info.
Requires Apify and REISkip API keys (prompted on first use).
```bash
~/nexus/skills/lead-generator/run --location "Austin, TX" --max_results 100
```

### Content Creator
Generates blog posts using local LLM with optional WordPress publishing.
```bash
~/nexus/skills/content-creator/run --topic "AI Trading Strategies" --style listicle
```

## Memory System

Nexus uses a dual-layer memory system:
- **ChromaDB**: Vector embeddings for semantic search
- **Markdown files**: Human-readable, Obsidian-compatible

### Using Memory
```bash
# Store
python ~/nexus/scripts/memory_system.py store "Your memory" --type strategic --tags "tag1,tag2"

# Search
python ~/nexus/scripts/memory_system.py search "query" --top_k 10

# Stats
python ~/nexus/scripts/memory_system.py stats
```

### Obsidian Integration
Open Obsidian → "Open folder as vault" → select `~/nexus/memory`

## Nightly Consolidation
Runs automatically at 3:00 AM to:
- Archive old, low-importance memories
- Re-index unindexed files
- Clean up orphaned entries

## Updating
```bash
cd ~/nexus
git pull  # If connected to a remote
bash ~/path/to/nexus-seed/install.sh  # Re-run installer (idempotent)
```

## Configuration
- User preferences: `~/nexus/configs/user.yaml`
- Agent orchestration: `~/nexus/configs/openclaw.yaml`
- API keys: `~/nexus/configs/api_keys.yaml` (gitignored)

## Troubleshooting

### Ollama not running
```bash
ollama serve  # Start the server
ollama list   # Check installed models
```

### Memory search returns no results
```bash
# Check if ChromaDB is working
python ~/nexus/scripts/memory_system.py stats
# Re-index if needed
python ~/nexus/scripts/nightly_consolidation.py
```

### Run full test suite
```bash
bash ~/nexus/scripts/test.sh
```
README_EOF
    ok "README.md written"
fi

# ============================================================================
# VALIDATION
# ============================================================================
step "Running Validation Tests"

bash "$NEXUS_HOME/scripts/test.sh" || warn "Some tests failed — check output above"

# ============================================================================
# FIRST-BOOT WIZARD
# ============================================================================
if [[ "${NEXUS_SKIP_WIZARD:-0}" != "1" ]] && [[ ! -f "$NEXUS_HOME/configs/user.yaml" ]]; then
    step "First-Boot Setup"
    bash "$NEXUS_HOME/scripts/first-boot.sh"
else
    if [[ -f "$NEXUS_HOME/configs/user.yaml" ]]; then
        ok "Already configured — skipping first-boot wizard"
    else
        ok "Skipping first-boot wizard (NEXUS_SKIP_WIZARD=1)"
    fi
fi

# ============================================================================
# DONE
# ============================================================================
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║              Nexus Installation Complete!                    ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  ${BOLD}Home:${NC}          $NEXUS_HOME"
echo -e "  ${BOLD}Memory Vault:${NC}  $NEXUS_HOME/memory (Obsidian-compatible)"
echo -e "  ${BOLD}Python:${NC}        $NEXUS_HOME/.venv/bin/python"
echo -e "  ${BOLD}Install Log:${NC}   $LOG_FILE"
echo ""
echo -e "  ${CYAN}Next steps:${NC}"
echo -e "    1. Open a new terminal (to load environment)"
echo -e "    2. Try: ${BOLD}$NEXUS_HOME/skills/trading-simulator/run --coin bitcoin${NC}"
echo -e "    3. Open ${BOLD}$NEXUS_HOME/memory${NC} in Obsidian"
echo ""
echo -e "  ${CYAN}Re-run tests anytime:${NC} bash $NEXUS_HOME/scripts/test.sh"
echo -e "  ${CYAN}Reconfigure:${NC}          bash $NEXUS_HOME/scripts/first-boot.sh"
echo ""
