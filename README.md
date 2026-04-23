# 🤖 Multi-Agent Collaborative Development

**A multi-agent software development workflow powered by [Hermes Agent](https://github.com/nousresearch/hermes-agent) + Claude Code.**

Orchestrate a team of specialized AI agents — Explorers, Architects, Coders, Testers, and Reviewers — to collaboratively build software through a structured 4-phase pipeline, with a real-time 2D visual dashboard.

[English](#overview) | [中文](#概述)

---

## Overview

This project implements a complete multi-agent development workflow inspired by:
- **MetaGPT** — SOP-driven agent communication via structured artifacts
- **Claude Code Plugins** — Parallel review with confidence scoring
- **Anthropic Cookbook** — Orchestrator-Workers + Evaluator-Optimizer patterns

### Architecture

```
┌─────────────────────────────────────────────────────────────────┐
│                    🧠 Orchestrator (Hermes Agent)                │
│               Understands requirements → Dispatches agents       │
│               Aggregates results → Quality gates                 │
├─────────────────────────────────────────────────────────────────┤
│                                                                  │
│  Phase 1: Discovery          Phase 2: Planning                   │
│  ┌────────────────────┐      ┌────────────────────┐             │
│  │ 🔭 Explorer ×2-3   │ ──→  │ 🏛 Architect ×1    │             │
│  │ (parallel, read-only)│     │ Design + Plan       │             │
│  └────────────────────┘      └────────┬───────────┘             │
│                                       ↓                          │
│  Phase 3: Building           Phase 4: Verification               │
│  ┌────────────────────┐      ┌────────────────────┐             │
│  │ 🔧 Coder ×1-3      │ ──→  │ 🧪 Tester ×1       │             │
│  │ (Claude Code, ∥)    │      │ 🔍 Reviewer ×2-4    │             │
│  └────────────────────┘      │ (confidence ≥ 80)    │             │
│                              └────────┬───────────┘             │
│                                       ↓                          │
│                         🔄 Fix Loop (max 3 iterations)           │
└─────────────────────────────────────────────────────────────────┘
```

### Agent Roles

| Agent | Engine | Permission | Responsibility |
|-------|--------|------------|----------------|
| 🧠 **Orchestrator** | Hermes main session | Full | Decompose tasks, dispatch agents, aggregate results |
| 🔭 **Explorer** | `delegate_task` | **Read-only** | Explore codebase, map dependencies, identify patterns |
| 🏛 **Architect** | `delegate_task` | Read + Write docs | Design architecture, define interfaces, write specs |
| 🔧 **Coder** | `claude -p` | Read + Edit + Terminal | Implement features, write unit tests, commit code |
| 🧪 **Tester** | `claude -p` | Read + Write + Terminal | Write tests, run suites, report coverage |
| 🔍 **Reviewer** | `delegate_task` | **Read-only** | Multi-perspective review with confidence scoring |

### Real-Time Dashboard

A web-based 2D visual dashboard shows agent lifecycle events in real-time:

- **Flow visualization** — Agents displayed in phase-grouped layout with status indicators
- **Live progress** — Phase progress bars, active agent count, tool call tracking
- **Event log** — Scrolling real-time event stream
- **Zero dependencies** — Pure Python stdlib server (no pip install needed)

## Prerequisites

- **Python 3.8+** (for dashboard server)
- **[Hermes Agent](https://github.com/nousresearch/hermes-agent)** installed and configured
- **[Claude Code CLI](https://docs.anthropic.com/en/docs/claude-code)** installed: `npm install -g @anthropic-ai/claude-code`
- **Git** (for repository operations)

## Installation

### Quick Install (Recommended)

```bash
git clone https://github.com/YOUR_USERNAME/multi-agent-dev.git
cd multi-agent-dev
bash install.sh
```

This will:
1. Copy skill files to `~/.hermes/skills/software-development/multi-agent-dev/`
2. Verify Python 3.8+ is available
3. Verify Claude Code CLI is installed
4. Make the launch script executable

### Manual Install

```bash
# Clone the repo
git clone https://github.com/YOUR_USERNAME/multi-agent-dev.git
cd multi-agent-dev

# Create the skill directory
mkdir -p ~/.hermes/skills/software-development/multi-agent-dev/{scripts,templates,references}

# Copy files
cp docs/SKILL.md ~/.hermes/skills/software-development/multi-agent-dev/SKILL.md
cp scripts/* ~/.hermes/skills/software-development/multi-agent-dev/scripts/
cp templates/* ~/.hermes/skills/software-development/multi-agent-dev/templates/
cp references/* ~/.hermes/skills/software-development/multi-agent-dev/references/
```

## Usage

### With Hermes Agent (Primary)

Just tell Hermes what you want to build:

```
> 用多 Agent 模式开发一个 Todo REST API，用 FastAPI，放在 ~/projects/todo-api

> Use multi-agent mode to add JWT authentication to ~/projects/myapp

> 用多 Agent 模式给 ~/projects/myapp 做一次全面的代码审查和重构
```

Hermes will automatically:
1. 🖥️ Start the Dashboard server + open browser
2. 🔭 Phase 1: Deploy Explorers to analyze the codebase
3. 🏛 Phase 2: Have Architect design the solution (you confirm the plan)
4. 🔧 Phase 3: Dispatch Coders to implement in parallel
5. 🔍 Phase 4: Run Tester + Reviewers for quality verification
6. 🔄 Fix any high-severity issues automatically (up to 3 rounds)

### Dashboard Only (Standalone)

```bash
# Start the dashboard server
python scripts/dashboard_server.py

# Open in browser
open http://localhost:9121    # macOS
xdg-open http://localhost:9121  # Linux

# Press 'D' in browser for demo animation
```

### Sending Events Programmatically

```python
from scripts.dashboard_client import Dashboard

db = Dashboard()
db.workflow_start("myproject", "~/myapp", "Build user auth")
db.phase_start(1)
db.agent_spawn("explorer-1", "explorer", phase=1)
db.agent_tool_call("explorer-1", "read_file", file="src/main.py")
db.agent_complete("explorer-1", summary="Analysis complete")
db.phase_complete(1)
# ... continue through phases ...
db.workflow_complete()
```

## Complexity Routing

Not every task needs the full pipeline:

| Complexity | Example | Agents Used |
|-----------|---------|-------------|
| **Simple** | Fix a known bug | Coder only |
| **Medium** | Add a new API endpoint | Explorer → Coder → Reviewer |
| **Complex** | New feature (5+ files) | Full 4-phase pipeline |
| **Mega** | New subsystem | Full pipeline + parallel Coders |

## Project Structure

```
multi-agent-dev/
├── README.md                         # This file
├── LICENSE                           # MIT License
├── install.sh                        # One-click installer
├── .gitignore
├── docs/
│   └── SKILL.md                      # Complete workflow guide (Hermes Skill)
├── scripts/
│   ├── dashboard_server.py           # WebSocket + HTTP server (stdlib only)
│   ├── dashboard_client.py           # Python event client (stdlib only)
│   ├── dashboard.html                # 2D Canvas visualization
│   └── launch.sh                     # Dashboard launcher script
├── templates/
│   ├── explorer-prompts.yaml         # Explorer agent prompt templates
│   ├── architect-prompt.yaml         # Architect agent prompt template
│   ├── coder-prompts.yaml            # Coder agent prompt templates
│   ├── reviewer-prompts.yaml         # Reviewer agent prompt templates
│   ├── tester-prompt.yaml            # Tester agent prompt template
│   └── workflow-state.yaml           # Workflow state schema
├── references/
│   └── orchestration-guide.md        # Orchestration patterns reference
└── examples/
    └── bookshelf-api/                # Example project built with this workflow
```

## Key Design Decisions

| Principle | Implementation |
|-----------|---------------|
| **SOP-driven** | Agents communicate via structured YAML artifacts, not raw conversation |
| **Confidence filtering** | Review findings scored 0-100, only ≥80 retained |
| **Evaluator-Optimizer loop** | Build → Review → Fix, max 3 iterations |
| **Read-only safety** | Explorers and Reviewers cannot modify code |
| **Zero dependencies** | Dashboard runs on Python stdlib only |
| **Cross-platform** | Works on macOS, Linux, and WSL |

## Industry Research

This workflow is based on research into:

- [MetaGPT](https://github.com/geekan/MetaGPT) — `Code = SOP(Team)`, standardized artifact passing
- [ChatDev](https://github.com/OpenBMB/ChatDev) — Virtual software company with role-playing agents
- [CrewAI](https://github.com/crewAIInc/crewAI) — Agent = Role + Goal + Backstory + Tools
- [Anthropic Cookbook](https://github.com/anthropics/anthropic-cookbook) — 5 orchestration patterns
- [Claude Code Plugins](https://docs.anthropic.com/en/docs/claude-code) — Parallel review + confidence scoring

---

## 概述

本项目实现了一个完整的多 Agent 协作软件开发工作流，基于 [Hermes Agent](https://github.com/nousresearch/hermes-agent) + Claude Code。

### 核心理念

- **SOP 驱动** — Agent 之间通过结构化 YAML 文件通信，而非裸对话（MetaGPT 模式）
- **置信度过滤** — Review 发现打分 0-100，仅保留 ≥80 的高置信度问题（Claude Code 模式）
- **评估-优化循环** — Build → Review → Fix 循环，最多 3 轮迭代（Anthropic Cookbook 模式）
- **复杂度路由** — 简单任务不需要启动全部 Agent，动态调整团队规模

### 快速开始

```bash
# 安装
git clone https://github.com/YOUR_USERNAME/multi-agent-dev.git
cd multi-agent-dev
bash install.sh

# 使用（在 Hermes Agent 中）
> 用多 Agent 模式开发一个博客系统
```

### 工作流程

```
Phase 1: 发现 → 2-3 个 Explorer 并行探索代码库
Phase 2: 规划 → Architect 设计架构 + 制定计划
Phase 3: 构建 → 1-3 个 Coder 并行实现（Claude Code）
Phase 4: 验证 → Tester 跑测试 + 2-4 个 Reviewer 并行审查
          ↓
    🔄 修复循环（如有高严重度问题）
```

### 实时仪表盘

浏览器打开 `http://localhost:9121` 即可实时查看：
- 每个 Agent 的当前状态和工具调用
- 4 个阶段的进度条
- 实时事件日志

按 **D 键** 查看 Demo 动画。

---

## License

MIT License — see [LICENSE](LICENSE) for details.

## Contributing

Contributions are welcome! Please feel free to submit issues and pull requests.

## Credits

Built with ❤️ using [Hermes Agent](https://github.com/nousresearch/hermes-agent) by [Nous Research](https://nousresearch.com).
