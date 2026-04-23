---
name: multi-agent-dev
description: Multi-Agent collaborative software development workflow. Orchestrates Explorer, Architect, Coder (Claude Code), Tester, and Reviewer agents in a phased pipeline — Discovery → Planning → Building → Verification — with confidence-scored reviews and evaluator-optimizer loops.
version: 1.0.0
author: Hermes Agent
license: MIT
metadata:
  hermes:
    tags: [multi-agent, collaboration, development, workflow, claude-code, orchestration]
    related_skills: [claude-code, subagent-driven-development, writing-plans, requesting-code-review]
---

# Multi-Agent Collaborative Development

## Overview

Orchestrate a team of specialized AI agents to collaboratively build software. Inspired by MetaGPT's SOP-driven workflow, Claude Code Plugins' confidence filtering, and Anthropic Cookbook's orchestration patterns.

**Core formula:** `Working Software = Orchestrator(Explore → Architect → Code → Test → Review)ⁿ`

**Key principles (from industry research):**
- **SOP-driven**: Agents communicate via structured artifacts, not raw conversation (MetaGPT)
- **Confidence filtering**: Review findings scored 0-100, only ≥80 retained (Claude Code code-review)
- **Evaluator-Optimizer loops**: Build → Review → Fix cycles, max 3 iterations (Anthropic Cookbook)
- **Dynamic routing**: Not all tasks need all agents — scale agents to task complexity
- **Read-only exploration**: Explorer and Reviewer agents cannot modify code (safety)

## Prerequisites

- **Hermes Agent** with `delegate_task` support
- **Claude Code CLI** installed: `npm install -g @anthropic-ai/claude-code`
- **Claude Code authenticated**: run `claude auth status` to verify
- **Git repository**: project must be a git repo (for worktree isolation)

## Agent Roster

| Agent | Count | Engine | Tools | Role |
|-------|-------|--------|-------|------|
| 🧠 **Orchestrator** | 1 | Hermes (you) | All | Project manager — decomposes, dispatches, aggregates, arbitrates |
| 🔭 **Explorer** | 2-3 parallel | `delegate_task` | **Read-only**: read_file, search_files | Explore codebase, map dependencies, identify patterns |
| 🏛 **Architect** | 1 | `delegate_task` | read_file, search_files, write_file | Design architecture, define interfaces, write specs |
| 🔧 **Coder** | 1-3 parallel | `claude -p` | Read, Edit, Write, Bash | Implement features in isolated worktrees |
| 🧪 **Tester** | 1 | `claude -p` | Read, Write, Bash | Write comprehensive tests, run test suites |
| 🔍 **Reviewer** | 2-4 parallel | `delegate_task` | **Read-only**: read_file, search_files | Multi-perspective review with confidence scoring |

## The 4-Phase Workflow

```
Phase 1: Discovery ──→ Phase 2: Planning ──→ Phase 3: Building ──→ Phase 4: Verification
  (Explorers)           (Architect)            (Coders ∥)            (Tester + Reviewers)
                                                    ↑                       │
                                                    └───── Fix Loop ────────┘
```

### Phase 1: Discovery (Parallel Explorers)

**Goal:** Understand the codebase before making any changes.

Deploy 2-3 Explorer agents in parallel, each investigating a different dimension:

```python
delegate_task(tasks=[
    {
        "goal": "Explore project structure and tech stack",
        "context": """You are a Code Explorer. Your job is READ-ONLY analysis.

PROJECT: {project_path}
USER REQUEST: {user_requirement}

Investigate and report:
1. Project structure — key directories, entry points, config files
2. Tech stack — languages, frameworks, libraries, build tools
3. Architecture patterns — MVC, microservices, monolith, etc.
4. Key conventions — naming, file organization, import patterns

OUTPUT FORMAT (STRICT):
```yaml
structure:
  entry_points: [list of main entry files]
  key_directories: {dir: purpose}
  config_files: [list]
tech_stack:
  language: ...
  framework: ...
  dependencies: [key deps]
  build_tool: ...
architecture:
  pattern: ...
  layers: [list]
conventions:
  naming: ...
  file_org: ...
```

DO NOT modify any files. READ ONLY.""",
        "toolsets": ["file"]
    },
    {
        "goal": "Analyze existing code related to the feature",
        "context": """You are a Code Explorer. Your job is READ-ONLY analysis.

PROJECT: {project_path}
USER REQUEST: {user_requirement}

Investigate and report:
1. Existing code most relevant to this feature
2. Files that will likely need modification
3. Dependencies and imports that the new code will need
4. Similar patterns already in the codebase we should follow
5. Potential conflicts or integration points

OUTPUT FORMAT (STRICT):
```yaml
relevant_code:
  files: [{path: ..., purpose: ..., relevance: high/medium/low}]
  patterns_to_follow: [list of patterns with file references]
modification_candidates:
  must_modify: [{path: ..., reason: ...}]
  might_modify: [{path: ..., reason: ...}]
dependencies:
  internal: [modules/packages used]
  external: [third-party libs needed]
integration_points:
  - {location: ..., description: ...}
```

DO NOT modify any files. READ ONLY.""",
        "toolsets": ["file"]
    },
    {
        "goal": "Analyze test infrastructure and quality patterns",
        "context": """You are a Code Explorer. Your job is READ-ONLY analysis.

PROJECT: {project_path}
USER REQUEST: {user_requirement}

Investigate and report:
1. Test framework and configuration
2. Test directory structure and naming conventions
3. Test patterns used (unit, integration, e2e)
4. Coverage configuration and current metrics if available
5. CI/CD pipeline configuration

OUTPUT FORMAT (STRICT):
```yaml
test_infra:
  framework: ...
  config_file: ...
  run_command: ...
  coverage_command: ...
test_structure:
  directory: ...
  naming_convention: ...
  patterns: [unit/integration/e2e]
  example_test_file: ...
ci_cd:
  tool: ...
  config_file: ...
  test_step: ...
quality:
  linter: ...
  formatter: ...
  type_checker: ...
```

DO NOT modify any files. READ ONLY.""",
        "toolsets": ["file"]
    }
])
```

**Orchestrator action after Phase 1:**
- Merge all Explorer reports into a unified `discovery.yaml`
- Identify gaps — if Explorers missed something critical, dispatch a focused Explorer
- Save the discovery report for Phase 2

### Phase 2: Planning (Architect Agent)

**Goal:** Design the architecture and create an implementation plan.

```python
delegate_task(
    goal="Design architecture and create implementation plan",
    context="""You are a Software Architect. Design the solution and write a detailed implementation plan.

USER REQUIREMENT:
{user_requirement}

DISCOVERY REPORT:
{merged_discovery_report}

YOUR TASKS:
1. Design the high-level architecture for the requested feature
2. Define interfaces/APIs between components
3. Create a step-by-step implementation plan

ARCHITECTURE OUTPUT FORMAT:
```yaml
architecture:
  overview: One paragraph describing the approach
  components:
    - name: ...
      responsibility: ...
      files: [new or modified file paths]
      interfaces:
        - {name: ..., signature: ..., description: ...}
  data_flow: Description of how data flows between components
  decisions:
    - {decision: ..., rationale: ..., alternatives_considered: [...]}
```

IMPLEMENTATION PLAN FORMAT:
Write a markdown plan following these rules:
- Each task = 2-5 minutes of focused work (bite-sized)
- Include exact file paths (create/modify)
- Include complete code examples (copy-pasteable)
- Include test commands with expected output
- Follow TDD: test first → implement → verify
- Tasks ordered by dependency (independent tasks marked as parallelizable)
- Mark tasks that CAN run in parallel with: `[PARALLEL-GROUP: N]`

Example task:
### Task 1: Create User model [PARALLEL-GROUP: 1]
**Files:** Create `src/models/user.py`, Create `tests/models/test_user.py`
**Step 1:** Write failing test...
**Step 2:** Implement...
**Step 3:** Verify: `pytest tests/models/test_user.py -v` → expected PASS

Save the plan to `docs/plans/plan.md` and architecture to `docs/plans/architecture.yaml`.
""",
    toolsets=["file"]
)
```

**Orchestrator action after Phase 2:**
- Read the plan and architecture docs
- Present a summary to the user for confirmation
- Ask: "Shall I proceed with implementation?" (or request modifications)
- Group tasks by PARALLEL-GROUP for Phase 3

### Phase 3: Building (Parallel Coders via Claude Code)

**Goal:** Implement all tasks from the plan using Claude Code agents.

#### For independent tasks (same PARALLEL-GROUP), run in parallel:

```bash
# Coder A — Backend tasks
terminal(command="claude -p '{task_prompt_A}' \
  --allowedTools 'Read,Edit,Write,Bash' \
  --max-turns 15 \
  --append-system-prompt 'You are a Backend Developer. Follow the implementation plan exactly. Use TDD. Commit after each task.' \
  --output-format json", \
  workdir="{project_path}", timeout=300)

# Coder B — Frontend tasks (parallel)
terminal(command="claude -p '{task_prompt_B}' \
  --allowedTools 'Read,Edit,Write,Bash' \
  --max-turns 15 \
  --append-system-prompt 'You are a Frontend Developer. Follow the implementation plan exactly. Use TDD. Commit after each task.' \
  --output-format json", \
  workdir="{project_path}", timeout=300)
```

#### For dependent tasks, run sequentially:

```bash
# Task depends on previous — run after prior completes
terminal(command="claude -p '{task_prompt_sequential}' \
  --allowedTools 'Read,Edit,Write,Bash' \
  --max-turns 15 \
  --output-format json", \
  workdir="{project_path}", timeout=300)
```

#### Coder prompt template:

```
Implement the following task from the implementation plan:

TASK: {task_title}
{task_full_text}

PROJECT CONTEXT:
- Tech stack: {tech_stack}
- Test command: {test_command}
- Conventions: {conventions}

RULES:
1. Follow TDD — write failing test first, then implement
2. Run tests after each change
3. Commit with descriptive message after task completes
4. Do NOT modify files outside the task scope
5. If you encounter a blocker, describe it clearly and stop

After completion, report:
- Files created/modified
- Tests added and their status
- Any issues encountered
```

**Orchestrator action during Phase 3:**
- Track which tasks are complete
- When a parallel group finishes, merge results and start next group
- If a Coder reports a blocker, decide: retry, reassign, or escalate to user

### Phase 4: Verification (Tester + Parallel Reviewers)

#### Step 1: Tester Agent

```bash
terminal(command="claude -p 'Run the full test suite and write any missing tests. \
  Current project needs: integration tests for the new feature, edge case tests, \
  and error handling tests. \
  \
  WHAT WAS BUILT: {summary_of_phase3_changes} \
  TEST COMMAND: {test_command} \
  \
  Steps: \
  1. Run existing tests — report any failures \
  2. Identify gaps in test coverage for new code \
  3. Write missing tests \
  4. Run full suite — all must pass \
  5. Report coverage metrics if available' \
  --allowedTools 'Read,Write,Bash' \
  --max-turns 20 \
  --output-format json", \
  workdir="{project_path}", timeout=300)
```

#### Step 2: Parallel Reviewers with Confidence Scoring

Deploy 2-4 reviewers, each with a different focus:

```python
delegate_task(tasks=[
    {
        "goal": "Review for bugs and logic errors",
        "context": """You are a Bug Hunter reviewer. Review ONLY for bugs and logic errors.

FILES CHANGED: {changed_files}
FEATURE DESCRIPTION: {user_requirement}

For each issue found, output EXACTLY:
```yaml
issues:
  - file: path/to/file.py
    line: 42
    severity: critical|high|medium|low
    confidence: 0-100
    category: bug
    description: Clear description of the bug
    suggestion: How to fix it
    evidence: Why you believe this is a real bug
```

CONFIDENCE SCORING RULES:
- 90-100: Certain bug — clear logic error, null reference, off-by-one
- 70-89: Likely bug — suspicious pattern but may be intentional
- 50-69: Possible issue — code smell that could lead to bugs
- Below 50: Do not report

FILTER OUT (these are NOT bugs):
- Style preferences
- Existing issues (pre-existing code, not from this change)
- Hypothetical issues in code paths not reachable from the change
- Linter-catchable issues (formatting, unused imports)

DO NOT modify any files. READ ONLY.""",
        "toolsets": ["file"]
    },
    {
        "goal": "Review for security vulnerabilities",
        "context": """You are a Security Reviewer. Review ONLY for security issues.

FILES CHANGED: {changed_files}
FEATURE DESCRIPTION: {user_requirement}

For each issue found, output EXACTLY:
```yaml
issues:
  - file: path/to/file.py
    line: 42
    severity: critical|high|medium|low
    confidence: 0-100
    category: security
    description: Clear description of the vulnerability
    suggestion: How to fix it
    evidence: Why this is exploitable
    cwe: CWE-XXX if applicable
```

CONFIDENCE SCORING RULES:
- 90-100: Confirmed vulnerability — injection, auth bypass, secrets exposure
- 70-89: Likely vulnerability — unsafe pattern in security-sensitive context
- 50-69: Potential concern — defense-in-depth suggestion
- Below 50: Do not report

FILTER OUT:
- Theoretical attacks with no realistic exploit path
- Issues in dependencies (report only code in this project)
- Pre-existing vulnerabilities not introduced by this change

DO NOT modify any files. READ ONLY.""",
        "toolsets": ["file"]
    },
    {
        "goal": "Review for architecture and design quality",
        "context": """You are an Architecture Reviewer. Review for design quality and maintainability.

FILES CHANGED: {changed_files}
ARCHITECTURE SPEC: {architecture_yaml}
FEATURE DESCRIPTION: {user_requirement}

For each issue found, output EXACTLY:
```yaml
issues:
  - file: path/to/file.py
    line: 42
    severity: critical|high|medium|low
    confidence: 0-100
    category: design
    description: Clear description of the design issue
    suggestion: How to improve
    evidence: Why this matters for maintainability
```

CHECK:
- Does implementation match the architecture spec?
- Are SOLID principles followed?
- Is the code DRY (no copy-paste)?
- Is YAGNI respected (no over-engineering)?
- Are interfaces clean and well-defined?
- Are error handling patterns consistent?
- Is the code testable?

CONFIDENCE SCORING:
- 90-100: Clear violation of architecture spec or SOLID principles
- 70-89: Significant design smell that will cause maintenance issues
- 50-69: Minor improvement suggestion
- Below 50: Do not report

DO NOT modify any files. READ ONLY.""",
        "toolsets": ["file"]
    }
])
```

**Orchestrator action after Phase 4:**

1. **Aggregate** all review results
2. **Filter** — keep only issues with confidence ≥ 80
3. **Deduplicate** — merge overlapping findings from different reviewers
4. **Categorize** — group by severity (critical → high → medium → low)
5. **Decision:**
   - If critical/high issues found → Enter Fix Loop (Phase 3 → Phase 4, max 3 iterations)
   - If only medium/low → Present to user for decision
   - If clean → Proceed to completion

### Fix Loop (Evaluator-Optimizer Pattern)

```
Iteration 1: Build → Review → Issues Found?
                                  ├── No → ✅ Done
                                  └── Yes → Fix → Review Again
Iteration 2: Fix → Review → Issues Found?
                                  ├── No → ✅ Done
                                  └── Yes → Fix → Review Again
Iteration 3: Fix → Review → Final (accept remaining minor issues)
```

```bash
# Fix loop — send issues to a Coder
terminal(command="claude -p 'Fix the following issues found during code review: \
  \
  ISSUES TO FIX: \
  {filtered_issues_yaml} \
  \
  For each issue: \
  1. Read the relevant file \
  2. Fix the issue \
  3. Run tests to verify no regressions \
  4. Commit with message: fix: {issue_description}' \
  --allowedTools 'Read,Edit,Bash' \
  --max-turns 15 \
  --output-format json", \
  workdir="{project_path}", timeout=300)
```

## Task Complexity Routing

Not every request needs the full pipeline. Route based on complexity:

| Complexity | Signal | Agents Used |
|-----------|--------|-------------|
| **Simple** | Single file change, clear fix | Coder only |
| **Medium** | 2-5 files, clear requirements | Explorer → Coder → Reviewer |
| **Complex** | New feature, 5+ files, design decisions | Full pipeline (all phases) |
| **Mega** | System-wide refactor, new subsystem | Full pipeline + parallel Coders with worktrees |

```
Routing decision tree:
  Is it a bug fix with known location? → Simple
  Is it a new feature? 
    → Touches ≤ 5 files with clear spec? → Medium
    → Needs design decisions? → Complex
    → Requires parallel work streams? → Mega
```

## Communication Protocol: Structured Artifacts

Agents communicate via YAML artifacts, NOT raw conversation:

```
Explorer → discovery.yaml → Orchestrator
Orchestrator → merged_context → Architect
Architect → architecture.yaml + plan.md → Orchestrator
Orchestrator → task_assignment → Coder
Coder → completion_report.yaml → Orchestrator
Orchestrator → review_request → Reviewer
Reviewer → review_findings.yaml → Orchestrator
Orchestrator → fix_request → Coder (if needed)
```

## Quick Start

### Minimal invocation (user says: "build me X"):

```
1. Read this skill
2. Ask user for project path + requirements (if not clear)
3. Route complexity (Simple/Medium/Complex/Mega)
4. Execute appropriate phases
5. Present results + summary
```

### Full invocation example:

```
User: "Add user authentication with JWT to my FastAPI project at ~/myapp"

Orchestrator:
  Phase 1: Deploy 3 Explorers → merged discovery.yaml
  Phase 2: Architect → architecture.yaml + plan.md
  [Show plan to user, get confirmation]
  Phase 3: Coder A (user model + auth logic) ∥ Coder B (endpoints + middleware)
  Phase 4: Tester (test suite) → 3 Reviewers (bug/security/design)
  [Filter confidence ≥ 80, fix critical/high issues]
  Fix Loop: Coder fixes → Re-review → Clean ✅
  Report: "Authentication system implemented. 12 files changed, 47 tests passing, 
           2 review issues fixed. Ready for your review."
```

## Pitfalls

1. **Don't skip Discovery** — Coders without context write code that doesn't fit the project
2. **Don't let Explorers/Reviewers write files** — toolsets must be read-only (`["file"]` without terminal)
3. **Don't exceed 3 fix loop iterations** — diminishing returns; accept minor issues after 3
4. **Don't parallel-edit the same files** — if two Coders touch the same file, make them sequential
5. **Always filter reviews by confidence ≥ 80** — low-confidence findings are mostly noise
6. **Provide complete context to each Agent** — they have NO memory of other agents' work; include everything they need in the prompt
7. **Use `--max-turns` with Claude Code** — prevent runaway loops (15 for implementation, 20 for testing)
8. **Save intermediate artifacts** — if a phase fails, you can restart from the last good artifact instead of redoing everything

## Real-Time Dashboard (Visual Monitoring)

The workflow includes an optional real-time 2D visual dashboard that shows agent lifecycle events as they happen.

### Architecture

```
scripts/
├── dashboard_server.py    # aiohttp server — HTTP + WebSocket on single port (default 9121)
├── dashboard.html         # 2D Canvas visualization frontend
└── dashboard_client.py    # Python client for emitting events (stdlib only, no deps)
```

### Quick Start

```python
# In orchestrator script — start dashboard server + open browser
from dashboard_client import ensure_server
db = ensure_server()  # auto-starts server on port 9121, opens browser

# Emit events during workflow
db.workflow_start("myproject", "~/myapp", "Build user auth")
db.phase_start(1)
db.agent_spawn("explorer-1", "explorer", phase=1)
db.agent_tool_call("explorer-1", "read_file", file="src/main.py", iteration=1)
db.agent_complete("explorer-1", summary="Done", artifacts=["discovery.yaml"])
db.phase_complete(1)
# ... repeat for each phase ...
db.workflow_complete()
```

### Dashboard Features

- **2D Canvas visualization** — Orchestrator at center, agents orbit by phase (Discovery=top, Planning=right, Building=bottom, Verification=left)
- **Animated data flow** — pulsing dots on connections between running agents and orchestrator
- **Phase progress bar** — 4-phase pipeline with active/done/pending indicators
- **Live metrics** — agents spawned, tool calls, tests passed, issues found
- **Agent cards** — click for detail modal with activity log
- **Event log** — real-time scrolling event stream
- **Demo mode** — press 'D' key in browser to see full workflow animation

### Event Types

| Event | Fields | When |
|-------|--------|------|
| `workflow.start` | project.{name,path,requirement} | Workflow begins |
| `workflow.complete` | — | All phases done |
| `workflow.fail` | error | Unrecoverable failure |
| `phase.start` | phase (1-4) | Phase begins |
| `phase.complete` | phase | Phase ends |
| `agent.spawn` | agent_id, role, phase, engine | Agent created |
| `agent.tool_call` | agent_id, tool, file, iteration | Agent uses a tool |
| `agent.complete` | agent_id, summary, artifacts | Agent finishes |
| `agent.fail` | agent_id, error | Agent errors out |
| `metrics.update` | metrics.{tests_passed, issues_found, ...} | Metric change |

### Integration Pattern (inside Hermes orchestrator)

The Orchestrator (Hermes agent itself) emits events at each phase transition. When using `delegate_task` or `terminal` for Claude Code, wrap calls with dashboard events:

```python
# Before spawning explorers
db.phase_start(1)
db.agent_spawn("explorer-1", "explorer", phase=1)

# After delegate_task returns
db.agent_complete("explorer-1", summary=result_summary, artifacts=["discovery.yaml"])
```

For Claude Code agents (Phase 3/4), parse the JSON output to extract tool call counts and report metrics after completion.

## Related Skills

- **claude-code**: Deep reference for all Claude Code CLI flags and patterns
- **subagent-driven-development**: Simpler single-agent-per-task pattern (use for smaller projects)
- **writing-plans**: Detailed guide on writing implementation plans (Phase 2)
- **requesting-code-review**: Review dimensions and quality standards (Phase 4)
