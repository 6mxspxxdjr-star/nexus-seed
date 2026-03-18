#!/usr/bin/env bash
# ============================================================================
# Nexus First-Boot Wizard
#
# Run after installation to configure user preferences and start core services.
# This script is idempotent — safe to run multiple times.
# ============================================================================
set -euo pipefail

NEXUS_HOME="${NEXUS_HOME:-$HOME/nexus}"
CONFIG_DIR="$NEXUS_HOME/configs"
USER_CONFIG="$CONFIG_DIR/user.yaml"
VENV_PYTHON="$NEXUS_HOME/.venv/bin/python"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
YELLOW='\033[1;33m'
BOLD='\033[1m'
NC='\033[0m'

print_banner() {
    echo ""
    echo -e "${CYAN}${BOLD}"
    echo "  ███╗   ██╗███████╗██╗  ██╗██╗   ██╗███████╗"
    echo "  ████╗  ██║██╔════╝╚██╗██╔╝██║   ██║██╔════╝"
    echo "  ██╔██╗ ██║█████╗   ╚███╔╝ ██║   ██║███████╗"
    echo "  ██║╚██╗██║██╔══╝   ██╔██╗ ██║   ██║╚════██║"
    echo "  ██║ ╚████║███████╗██╔╝ ╚██╗╚██████╔╝███████║"
    echo "  ╚═╝  ╚═══╝╚══════╝╚═╝   ╚═╝ ╚═════╝ ╚══════╝"
    echo -e "${NC}"
    echo -e "${BOLD}  Welcome to Nexus — Your Autonomous Intelligence System${NC}"
    echo ""
}

# Check if already configured
if [[ -f "$USER_CONFIG" ]]; then
    echo -e "${YELLOW}Nexus is already configured.${NC}"
    read -rp "Would you like to reconfigure? (y/N): " reconfigure
    if [[ "${reconfigure,,}" != "y" ]]; then
        echo "Keeping existing configuration."
        exit 0
    fi
fi

print_banner

mkdir -p "$CONFIG_DIR"

# === Step 1: User Name ===
echo -e "${BLUE}${BOLD}Step 1/3: Who are you?${NC}"
read -rp "  Your name: " USER_NAME
while [[ -z "$USER_NAME" ]]; do
    read -rp "  Please enter your name: " USER_NAME
done
echo ""

# === Step 2: Interface Preference ===
echo -e "${BLUE}${BOLD}Step 2/3: How do you want to interact with Nexus?${NC}"
echo "  1) Telegram (recommended — get updates on your phone)"
echo "  2) Discord  (great for team use)"
echo "  3) CLI only (no external interface)"
echo ""
read -rp "  Choice [1/2/3]: " INTERFACE_CHOICE

INTERFACE="cli"
BOT_TOKEN=""
DISCORD_TOKEN=""

case "$INTERFACE_CHOICE" in
    1)
        INTERFACE="telegram"
        echo ""
        echo -e "${CYAN}To set up Telegram:${NC}"
        echo "  1. Open Telegram and search for @BotFather"
        echo "  2. Send /newbot and follow the prompts"
        echo "  3. Copy the bot token"
        echo ""
        read -rp "  Paste your Telegram bot token (or press Enter to skip): " BOT_TOKEN
        if [[ -z "$BOT_TOKEN" ]]; then
            echo -e "${YELLOW}  Skipping Telegram setup — you can configure later in $USER_CONFIG${NC}"
            INTERFACE="cli"
        fi
        ;;
    2)
        INTERFACE="discord"
        echo ""
        echo -e "${CYAN}To set up Discord:${NC}"
        echo "  1. Go to https://discord.com/developers/applications"
        echo "  2. Create a new application → Bot section → Copy token"
        echo "  3. Enable Message Content Intent under Bot → Privileged Gateway Intents"
        echo ""
        read -rp "  Paste your Discord bot token (or press Enter to skip): " DISCORD_TOKEN
        if [[ -z "$DISCORD_TOKEN" ]]; then
            echo -e "${YELLOW}  Skipping Discord setup — you can configure later in $USER_CONFIG${NC}"
            INTERFACE="cli"
        fi
        ;;
    *)
        INTERFACE="cli"
        echo "  Using CLI-only mode."
        ;;
esac
echo ""

# === Step 3: Optional API Keys ===
echo -e "${BLUE}${BOLD}Step 3/3: API Keys (optional — press Enter to skip any)${NC}"
echo "  These enable cloud features like Guardian verification and content publishing."
echo ""

read -rp "  Anthropic API key (for Guardian cloud verification): " ANTHROPIC_KEY
read -rp "  OpenAI API key (fallback for Guardian): " OPENAI_KEY
echo ""

# === Write Configuration ===
cat > "$USER_CONFIG" << EOF
# Nexus User Configuration
# Generated: $(date -u +"%Y-%m-%dT%H:%M:%SZ")

user:
  name: "$USER_NAME"

interface:
  type: "$INTERFACE"
  telegram:
    bot_token: "${BOT_TOKEN}"
  discord:
    bot_token: "${DISCORD_TOKEN}"

api_keys:
  anthropic: "${ANTHROPIC_KEY}"
  openai: "${OPENAI_KEY}"

preferences:
  notifications: true
  auto_optimize: true
  simulation_on_startup: true
  consolidation_schedule: "daily"

engines:
  trading_simulator: true
  lead_generator: false  # Requires Apify + REISkip keys
  content_creator: false  # Requires WordPress credentials
EOF

chmod 600 "$USER_CONFIG"

# === Export API keys to environment ===
if [[ -n "$ANTHROPIC_KEY" ]]; then
    echo "export ANTHROPIC_API_KEY='$ANTHROPIC_KEY'" >> "$NEXUS_HOME/.env"
fi
if [[ -n "$OPENAI_KEY" ]]; then
    echo "export OPENAI_API_KEY='$OPENAI_KEY'" >> "$NEXUS_HOME/.env"
fi
if [[ -n "$BOT_TOKEN" ]]; then
    echo "export TELEGRAM_BOT_TOKEN='$BOT_TOKEN'" >> "$NEXUS_HOME/.env"
fi
if [[ -n "$DISCORD_TOKEN" ]]; then
    echo "export DISCORD_BOT_TOKEN='$DISCORD_TOKEN'" >> "$NEXUS_HOME/.env"
fi
[[ -f "$NEXUS_HOME/.env" ]] && chmod 600 "$NEXUS_HOME/.env"

# === Store initial memory ===
echo -e "${CYAN}Initializing memory system...${NC}"
if [[ -x "$VENV_PYTHON" ]]; then
    "$VENV_PYTHON" "$NEXUS_HOME/scripts/memory_system.py" store \
        "User $USER_NAME initialized Nexus. Interface: $INTERFACE. First boot completed." \
        --type episodic --source first-boot --importance 0.9 2>/dev/null || true
fi

# === Welcome Message ===
echo ""
echo -e "${GREEN}${BOLD}╔══════════════════════════════════════════════════════════════╗${NC}"
echo -e "${GREEN}${BOLD}║                    Nexus is Ready!                           ║${NC}"
echo -e "${GREEN}${BOLD}╚══════════════════════════════════════════════════════════════╝${NC}"
echo ""
echo -e "  Welcome, ${BOLD}$USER_NAME${NC}! Here's what Nexus can do for you:"
echo ""
echo -e "  ${CYAN}🔮 Profit Engines Available:${NC}"
echo -e "    ${GREEN}●${NC} Trading Simulator — Backtest crypto strategies with AI agents"
echo -e "      Run: ${BOLD}$NEXUS_HOME/skills/trading-simulator/run --coin bitcoin${NC}"
echo ""
echo -e "    ${YELLOW}○${NC} Lead Generator — Find real estate leads (needs API keys)"
echo -e "      Run: ${BOLD}$NEXUS_HOME/skills/lead-generator/run --location \"Austin, TX\"${NC}"
echo ""
echo -e "    ${YELLOW}○${NC} Content Creator — Generate and publish blog posts"
echo -e "      Run: ${BOLD}$NEXUS_HOME/skills/content-creator/run --topic \"Your Topic\"${NC}"
echo ""
echo -e "  ${CYAN}🧠 Memory System:${NC}"
echo -e "    Store: ${BOLD}$VENV_PYTHON $NEXUS_HOME/scripts/memory_system.py store \"your memory\"${NC}"
echo -e "    Search: ${BOLD}$VENV_PYTHON $NEXUS_HOME/scripts/memory_system.py search \"query\"${NC}"
echo -e "    Stats: ${BOLD}$VENV_PYTHON $NEXUS_HOME/scripts/memory_system.py stats${NC}"
echo ""
echo -e "  ${CYAN}🤖 Agents:${NC}"
echo -e "    Strategist — Analyzes and recommends actions"
echo -e "    Guardian — Reviews and approves critical changes"
echo -e "    Worker — Executes tasks"
echo -e "    Evolution — Continuously optimizes in the background"
echo ""
echo -e "  ${CYAN}📁 Your Nexus home: ${BOLD}$NEXUS_HOME${NC}"
echo -e "  ${CYAN}📝 Memory vault (Obsidian-compatible): ${BOLD}$NEXUS_HOME/memory${NC}"
echo -e "  ${CYAN}⚙️  Configuration: ${BOLD}$USER_CONFIG${NC}"
echo ""

# === Start background optimization ===
echo -e "${CYAN}Starting background optimization...${NC}"
if [[ -x "$VENV_PYTHON" ]]; then
    nohup "$VENV_PYTHON" "$NEXUS_HOME/scripts/run_simulation.py" \
        --agents 50 --rounds 20 --market crypto \
        > "$NEXUS_HOME/memory/.system/evolution_startup.log" 2>&1 &
    echo -e "  ${GREEN}Evolution agent started (PID: $!)${NC}"
    echo ""
fi

echo -e "${GREEN}${BOLD}Nexus is live. Start exploring!${NC}"
echo ""
