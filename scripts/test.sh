#!/usr/bin/env bash
# ============================================================================
# Nexus Post-Installation Test Suite
#
# Verifies all components are working after installation.
# Run: bash ~/nexus/scripts/test.sh
# ============================================================================
set -uo pipefail

NEXUS_HOME="${NEXUS_HOME:-$HOME/nexus}"
VENV_PYTHON="$NEXUS_HOME/.venv/bin/python"

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

PASSED=0
FAILED=0
WARNED=0

pass() { ((PASSED++)); echo -e "  ${GREEN}✓ PASS${NC}: $1"; }
fail() { ((FAILED++)); echo -e "  ${RED}✗ FAIL${NC}: $1"; }
warn() { ((WARNED++)); echo -e "  ${YELLOW}⚠ WARN${NC}: $1"; }

echo ""
echo -e "${CYAN}${BOLD}Nexus Installation Test Suite${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# === 1. Directory Structure ===
echo -e "${BOLD}1. Directory Structure${NC}"

for dir in memory agents skills configs scripts simulations optimizer .venv; do
    if [[ -d "$NEXUS_HOME/$dir" ]]; then
        pass "$dir/ exists"
    else
        fail "$dir/ missing"
    fi
done

for subdir in 00_Core 01_Conversations 02_Research 03_Content 04_Simulations 05_Decisions 06_Archive .system; do
    if [[ -d "$NEXUS_HOME/memory/$subdir" ]]; then
        pass "memory/$subdir/ exists"
    else
        fail "memory/$subdir/ missing"
    fi
done
echo ""

# === 2. Python Environment ===
echo -e "${BOLD}2. Python Environment${NC}"

if [[ -x "$VENV_PYTHON" ]]; then
    pass "Python venv exists"
    PYVER=$("$VENV_PYTHON" --version 2>&1)
    pass "Python version: $PYVER"
else
    fail "Python venv not found at $VENV_PYTHON"
fi

# Check Python packages
for pkg in chromadb yaml requests; do
    if "$VENV_PYTHON" -c "import $pkg" 2>/dev/null; then
        pass "Python package: $pkg"
    else
        if [[ "$pkg" == "yaml" ]]; then
            if "$VENV_PYTHON" -c "import yaml" 2>/dev/null; then
                pass "Python package: pyyaml"
            else
                fail "Python package: pyyaml"
            fi
        else
            fail "Python package: $pkg"
        fi
    fi
done
echo ""

# === 3. Memory System ===
echo -e "${BOLD}3. Memory System${NC}"

# Test store
STORE_RESULT=$("$VENV_PYTHON" "$NEXUS_HOME/scripts/memory_system.py" store \
    "Test memory from installation verification" \
    --type semantic --source test --importance 0.1 2>&1) || true

if echo "$STORE_RESULT" | grep -q '"status": "stored"'; then
    pass "Memory store works"
    MEMORY_ID=$(echo "$STORE_RESULT" | "$VENV_PYTHON" -c "import sys,json; print(json.load(sys.stdin)['id'])" 2>/dev/null || echo "")
else
    fail "Memory store: $STORE_RESULT"
    MEMORY_ID=""
fi

# Test search
SEARCH_RESULT=$("$VENV_PYTHON" "$NEXUS_HOME/scripts/memory_system.py" search \
    "test installation" --top_k 3 2>&1) || true

if echo "$SEARCH_RESULT" | grep -q "similarity_score"; then
    pass "Memory search works"
else
    warn "Memory search returned no results (may need embeddings model)"
fi

# Test recall
if [[ -n "$MEMORY_ID" ]]; then
    RECALL_RESULT=$("$VENV_PYTHON" "$NEXUS_HOME/scripts/memory_system.py" recall "$MEMORY_ID" 2>&1) || true
    if echo "$RECALL_RESULT" | grep -q "content"; then
        pass "Memory recall works"
    else
        fail "Memory recall failed"
    fi
fi

# Test stats
STATS_RESULT=$("$VENV_PYTHON" "$NEXUS_HOME/scripts/memory_system.py" stats 2>&1) || true
if echo "$STATS_RESULT" | grep -q "total_vectors"; then
    pass "Memory stats works"
else
    fail "Memory stats failed"
fi
echo ""

# === 4. Ollama / LLM ===
echo -e "${BOLD}4. Ollama & Models${NC}"

if command -v ollama &>/dev/null; then
    pass "Ollama installed"

    if curl -sf http://localhost:11434/api/tags >/dev/null 2>&1; then
        pass "Ollama server running"

        MODELS=$(curl -sf http://localhost:11434/api/tags 2>/dev/null || echo "{}")
        if echo "$MODELS" | grep -q "nomic-embed-text"; then
            pass "Model: nomic-embed-text"
        else
            warn "Model nomic-embed-text not pulled (needed for embeddings)"
        fi

        if echo "$MODELS" | grep -q "qwen2.5"; then
            pass "Model: qwen2.5"
        else
            warn "Model qwen2.5 not pulled (needed for LLM queries)"
        fi
    else
        warn "Ollama not running — start with: ollama serve"
    fi
else
    warn "Ollama not installed — local LLM features disabled"
fi
echo ""

# === 5. Agent Identities ===
echo -e "${BOLD}5. Agent Identities${NC}"

for agent in strategist guardian worker evolution; do
    if [[ -f "$NEXUS_HOME/agents/$agent/IDENTITY.md" ]]; then
        pass "Agent: $agent"
    else
        fail "Agent: $agent (missing IDENTITY.md)"
    fi
done
echo ""

# === 6. Skills ===
echo -e "${BOLD}6. Skills${NC}"

for skill in search-memory store-memory ask-questions create-agent run-simulation guardian-review trading-simulator lead-generator content-creator; do
    if [[ -f "$NEXUS_HOME/skills/$skill/SKILL.md" ]] && [[ -f "$NEXUS_HOME/skills/$skill/run" ]]; then
        pass "Skill: $skill"
    else
        fail "Skill: $skill (missing SKILL.md or run)"
    fi
done
echo ""

# === 7. Simulation Engine ===
echo -e "${BOLD}7. Simulation Engine${NC}"

SIM_RESULT=$("$VENV_PYTHON" "$NEXUS_HOME/scripts/run_simulation.py" \
    --agents 10 --rounds 5 --market crypto 2>&1) || true

if echo "$SIM_RESULT" | grep -q "simulation_id"; then
    pass "Simulation engine works"
    ROI=$(echo "$SIM_RESULT" | "$VENV_PYTHON" -c "import sys,json; print(json.load(sys.stdin)['summary']['mean_roi_pct'])" 2>/dev/null || echo "?")
    echo -e "    └─ Quick test: mean ROI = ${ROI}%"
else
    fail "Simulation engine: $SIM_RESULT"
fi
echo ""

# === 8. Configuration ===
echo -e "${BOLD}8. Configuration${NC}"

if [[ -f "$NEXUS_HOME/configs/user.yaml" ]]; then
    pass "User config exists"
else
    warn "User config not found — run first-boot: bash $NEXUS_HOME/scripts/first-boot.sh"
fi

if [[ -f "$NEXUS_HOME/configs/openclaw.yaml" ]]; then
    pass "OpenClaw config exists"
else
    warn "OpenClaw config missing"
fi
echo ""

# === 9. External Tools ===
echo -e "${BOLD}9. External Tools${NC}"

for tool in git node docker; do
    if command -v "$tool" &>/dev/null; then
        VERSION=$("$tool" --version 2>&1 | head -1)
        pass "$tool: $VERSION"
    else
        if [[ "$tool" == "docker" ]]; then
            warn "$tool not found (needed for Neo4j/MiroFish)"
        else
            warn "$tool not found"
        fi
    fi
done
echo ""

# === 10. Git Repository ===
echo -e "${BOLD}10. Git Repository${NC}"

if [[ -d "$NEXUS_HOME/.git" ]]; then
    COMMIT_COUNT=$(git -C "$NEXUS_HOME" rev-list --count HEAD 2>/dev/null || echo "0")
    pass "Git repo initialized ($COMMIT_COUNT commits)"
else
    warn "Git repo not initialized"
fi
echo ""

# === Summary ===
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo -e "${BOLD}Summary${NC}"
echo -e "  ${GREEN}Passed: $PASSED${NC}"
echo -e "  ${RED}Failed: $FAILED${NC}"
echo -e "  ${YELLOW}Warnings: $WARNED${NC}"
echo ""

if [[ $FAILED -eq 0 ]]; then
    echo -e "${GREEN}${BOLD}All critical tests passed! Nexus is ready.${NC}"
    if [[ $WARNED -gt 0 ]]; then
        echo -e "${YELLOW}Some optional components have warnings — see above.${NC}"
    fi
else
    echo -e "${RED}${BOLD}$FAILED test(s) failed. Review the output above for details.${NC}"
fi
echo ""

# Return appropriate exit code
[[ $FAILED -eq 0 ]]
