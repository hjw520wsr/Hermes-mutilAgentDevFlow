#!/bin/bash
# Multi-Agent Collaborative Development — Installer
# Copies skill files to ~/.hermes/skills/ and verifies dependencies

set -e

# Colors
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SKILL_DIR="${HERMES_HOME:-$HOME/.hermes}/skills/software-development/multi-agent-dev"
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"

echo ""
echo -e "${CYAN}${BOLD}🤖 Multi-Agent Collaborative Development — Installer${NC}"
echo -e "${CYAN}━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━${NC}"
echo ""

# ── Step 1: Check Python ──────────────────────────────────────
echo -e "${BLUE}[1/4]${NC} Checking Python 3.8+ ..."
if command -v python3 &>/dev/null; then
    PY_VERSION=$(python3 -c 'import sys; print(f"{sys.version_info.major}.{sys.version_info.minor}")')
    PY_MAJOR=$(echo "$PY_VERSION" | cut -d. -f1)
    PY_MINOR=$(echo "$PY_VERSION" | cut -d. -f2)
    if [ "$PY_MAJOR" -ge 3 ] && [ "$PY_MINOR" -ge 8 ]; then
        echo -e "  ${GREEN}✓${NC} Python $PY_VERSION found"
    else
        echo -e "  ${RED}✗${NC} Python $PY_VERSION found, but 3.8+ required"
        exit 1
    fi
else
    echo -e "  ${RED}✗${NC} Python 3 not found. Please install Python 3.8+"
    exit 1
fi

# ── Step 2: Check Claude Code CLI ─────────────────────────────
echo -e "${BLUE}[2/4]${NC} Checking Claude Code CLI ..."
if command -v claude &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Claude Code CLI found: $(which claude)"
else
    echo -e "  ${YELLOW}⚠${NC} Claude Code CLI not found (optional — needed for Coder/Tester agents)"
    echo -e "    Install: ${CYAN}npm install -g @anthropic-ai/claude-code${NC}"
fi

# ── Step 3: Check Hermes Agent ─────────────────────────────────
echo -e "${BLUE}[3/4]${NC} Checking Hermes Agent ..."
if command -v hermes &>/dev/null; then
    echo -e "  ${GREEN}✓${NC} Hermes Agent found: $(which hermes)"
else
    echo -e "  ${YELLOW}⚠${NC} Hermes Agent not found"
    echo -e "    Install: ${CYAN}pip install hermes-agent${NC}"
fi

# ── Step 4: Install skill files ────────────────────────────────
echo -e "${BLUE}[4/4]${NC} Installing skill files to ${SKILL_DIR} ..."

mkdir -p "$SKILL_DIR"/{scripts,templates,references}

# Copy SKILL.md
cp "$SCRIPT_DIR/docs/SKILL.md" "$SKILL_DIR/SKILL.md"
echo -e "  ${GREEN}✓${NC} SKILL.md"

# Copy scripts
for f in "$SCRIPT_DIR"/scripts/*; do
    fname=$(basename "$f")
    cp "$f" "$SKILL_DIR/scripts/$fname"
    echo -e "  ${GREEN}✓${NC} scripts/$fname"
done

# Copy templates
for f in "$SCRIPT_DIR"/templates/*; do
    fname=$(basename "$f")
    cp "$f" "$SKILL_DIR/templates/$fname"
    echo -e "  ${GREEN}✓${NC} templates/$fname"
done

# Copy references
for f in "$SCRIPT_DIR"/references/*; do
    fname=$(basename "$f")
    cp "$f" "$SKILL_DIR/references/$fname"
    echo -e "  ${GREEN}✓${NC} references/$fname"
done

# Make launch script executable
chmod +x "$SKILL_DIR/scripts/launch.sh" 2>/dev/null || true

echo ""
echo -e "${GREEN}${BOLD}✅ Installation complete!${NC}"
echo ""
echo -e "${BOLD}Usage:${NC}"
echo -e "  In Hermes Agent, just say:"
echo -e "  ${CYAN}> 用多 Agent 模式开发一个 Todo REST API${NC}"
echo -e "  ${CYAN}> Use multi-agent mode to build a blog system${NC}"
echo ""
echo -e "${BOLD}Dashboard:${NC}"
echo -e "  ${CYAN}python3 $SKILL_DIR/scripts/dashboard_server.py${NC}"
echo -e "  Then open ${CYAN}http://localhost:9121${NC}"
echo ""
