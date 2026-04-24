---
name: multi-agent-dev
description: Multi-Agent collaborative software development workflow. Orchestrates Explorer, Architect, Coder (Claude Code), Tester, and Reviewer agents in a phased pipeline — Discovery → Planning → Building → Verification — with confidence-scored reviews and evaluator-optimizer loops.
version: 2.0.0
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

## Pre-flight Checks (MANDATORY before Phase 1)

Before starting any workflow, run these checks. **Do not proceed if any check fails — fix or establish fallback first.**

```python
# Step 1: Verify delegate_task works (catches provider auth issues)
preflight_result = delegate_task(
    goal="Return the text 'PREFLIGHT_OK' and nothing else.",
    toolsets=[]
)
delegate_ok = "PREFLIGHT_OK" in preflight_result

# Step 2: Verify Claude Code CLI is authenticated
claude_auth = terminal(command="claude auth status --text 2>&1", timeout=10)
claude_ok = claude_auth.exit_code == 0

# Step 3: Verify clean git working tree
git_status = terminal(command="git status --porcelain", workdir=project_path, timeout=10)
git_clean = len(git_status.output.strip()) == 0

# Step 4: Determine available engines and set fallback plan
engines = {
    "delegate_task": delegate_ok,
    "claude_code": claude_ok,
}
```

### Fallback Matrix

Based on pre-flight results, determine which engine to use for each agent role:

| Agent Role | Primary Engine | Fallback 1 | Fallback 2 |
|-----------|---------------|------------|------------|
| Explorer | `delegate_task` | `delegate_task(acp_command='claude')` | Orchestrator self-executes |
| Architect | `delegate_task` | `delegate_task(acp_command='claude')` | Orchestrator self-executes |
| Coder | `claude -p` (CLI) | `delegate_task` | — |
| Tester | `claude -p` (CLI) | `delegate_task` | Orchestrator self-executes |
| Reviewer | `delegate_task` | `delegate_task(acp_command='claude')` | Orchestrator self-executes |

**Rule: A phase can be DEGRADED (using fallback engine) but NEVER SKIPPED entirely.**

If both `delegate_task` and `claude` CLI are unavailable for a role, the Orchestrator MUST execute that role's tasks itself using its own tools (read_file, search_files, write_file, terminal).

## Fallback Strategy

When an agent call fails, follow this escalation chain:

```
delegate_task(default provider) fails
    │
    ├─→ Retry with: delegate_task(acp_command='claude', acp_args=['--acp', '--stdio'])
    │       Uses Claude Code's independent authentication
    │
    ├─→ If still fails: Orchestrator self-executes the task
    │       Use the same prompt/context, but execute with Orchestrator's own tools
    │       Emit dashboard event: agent.spawn(role="orchestrator-fallback")
    │
    └─→ NEVER skip the phase entirely

claude -p (CLI) fails
    │
    ├─→ Retry once with longer timeout
    │
    ├─→ Fallback: delegate_task with terminal toolset
    │
    └─→ Last resort: Orchestrator self-executes
```

### Fallback Code Pattern

```python
def run_with_fallback(goal, context, toolsets, role, phase, dashboard=None):
    """Execute an agent task with automatic fallback chain."""
    agent_id = f"{role}-{phase}"

    # Attempt 1: delegate_task (default provider)
    try:
        if dashboard: dashboard.agent_spawn(agent_id, role, phase, engine="delegate_task")
        result = delegate_task(goal=goal, context=context, toolsets=toolsets)
        if dashboard: dashboard.agent_complete(agent_id, result="success")
        return result
    except Exception as e:
        if dashboard: dashboard.agent_error(agent_id, str(e))

    # Attempt 2: delegate_task with Claude Code ACP
    try:
        fallback_id = f"{role}-{phase}-fallback"
        if dashboard: dashboard.agent_spawn(fallback_id, role, phase, engine="claude-acp")
        result = delegate_task(
            goal=goal, context=context, toolsets=toolsets,
            acp_command='claude', acp_args=['--acp', '--stdio']
        )
        if dashboard: dashboard.agent_complete(fallback_id, result="success-via-fallback")
        return result
    except Exception as e:
        if dashboard: dashboard.agent_error(fallback_id, str(e))

    # Attempt 3: Orchestrator self-executes
    orchestrator_id = f"{role}-{phase}-orchestrator"
    if dashboard: dashboard.agent_spawn(orchestrator_id, "orchestrator-fallback", phase)
    # Orchestrator uses its own tools to fulfill the role
    # ... (execute with read_file, search_files, write_file, terminal as needed)
    if dashboard: dashboard.agent_complete(orchestrator_id, result="orchestrator-fallback")
```

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
Pre-flight ──→ Phase 1: Discovery ──⊕──→ Phase 2: Planning ──⊕──→ Phase 3: Building ──→ Phase 4: Verification
 (Checks)       (Explorers)        Gate1   (Architect)       Gate2   (Coders ∥)           (Tester + Reviewers)
                                                                          ↑                       │
                                                                          └───── Fix Loop ────────┘

⊕ = Mandatory Gate (cannot be bypassed)
```

## Mandatory Gates (CANNOT BE SKIPPED)

Gates enforce quality checkpoints between phases. The Orchestrator MUST NOT proceed past a gate until its conditions are met.

### Gate 0: Pre-flight → Phase 1
**Condition:** All pre-flight checks pass OR fallback plan established.
```
✅ delegate_task OR claude CLI available (at least one works)
✅ Git working tree is clean
✅ Fallback engine assignments documented
```

### Gate 1: Phase 1 → Phase 2
**Condition:** Discovery report exists and covers minimum required areas.
```
✅ At least ONE Explorer (or Orchestrator fallback) produced a report
✅ Report contains: project structure, tech stack, relevant code analysis
✅ Merged discovery context saved as artifact
```
**If gate fails:** Re-run Discovery with fallback engine, or Orchestrator self-explores.

### Gate 2: Phase 2 → Phase 3 (USER CONFIRMATION REQUIRED)
**Condition:** Architecture and plan exist, AND user has explicitly approved.
```
✅ architecture.yaml exists with component definitions
✅ plan.md exists with PARALLEL-GROUP annotations
✅ Interface contract generated (include paths, naming, file ownership)
✅ User has reviewed and approved the plan via clarify()
```
**Orchestrator MUST:**
1. Present architecture overview + task count + parallel groups to user
2. Call `clarify(question="Review the plan above. Proceed with implementation?", choices=["Approve and proceed", "Modify plan", "Cancel"])`
3. Wait for user response before entering Phase 3
4. If user says "Modify" → re-run Architect with user's feedback

### Gate 3: Phase 3 → Complete (implicit)
**Condition:** Phase 4 (Verification) completed — Testing and Review are NOT optional.
```
✅ Tester Agent ran (or Orchestrator ran tests as fallback)
✅ At least ONE Reviewer ran (or Orchestrator performed review as fallback)
✅ All critical/high issues from review are fixed (or max 3 fix loops reached)
✅ Final test suite passes
```
**Compilation success alone does NOT satisfy this gate.**

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

## Interface Contract (INJECT into every Coder prompt)

When multiple Coders work in parallel, they MUST receive a shared interface contract to prevent conflicts. The Orchestrator generates this from the Architect's output and injects it into every Coder's prompt.

### Required Contract Fields

```yaml
interface_contract:
  # Include path convention — eliminates the #1 integration issue
  include_paths:
    style: "relative to src/"          # e.g., "core/common.h" NOT "src/core/common.h"
    base_directory: "src/"              # what CMake/build tool adds as include dir
    third_party: "third_party/"        # third-party headers prefix
    examples:
      correct: ["core/common.h", "graphics/shader.h", "stb/stb_image.h"]
      wrong: ["src/core/common.h", "../third_party/stb/stb_image.h"]

  # File ownership — each Coder only creates/modifies their assigned files
  file_ownership:
    coder_A:
      creates: ["src/core/engine.cpp", "src/core/engine.h"]
      modifies: ["CMakeLists.txt"]
    coder_B:
      creates: ["src/graphics/renderer.cpp", "src/graphics/shader.cpp"]
      modifies: []
    coder_C:
      creates: ["src/scene/camera.cpp", "src/scene/mesh.cpp"]
      modifies: []
    shared_files: []  # files NO Coder may touch — Orchestrator handles these

  # Third-party initialization — exactly ONE designated owner
  third_party_init:
    stb_image:
      owner: "coder_A"
      implementation_file: "third_party/stb/stb_image_implementation.cpp"
      rule: "Only coder_A creates the #define STB_IMAGE_IMPLEMENTATION file. Other Coders only #include the header."

  # Naming conventions
  naming:
    files: "snake_case"
    classes: "PascalCase"
    methods: "camelCase"
    constants: "UPPER_SNAKE_CASE"
    namespaces: "lowercase"

  # Inter-module API contracts (from Architect output)
  api_contracts:
    - provider: "core/engine.h"
      consumer: ["graphics/renderer.cpp", "scene/scene.cpp"]
      interface: "class Engine { void init(); void run(); void shutdown(); }"
```

### Injection Pattern

The Orchestrator MUST append this to every Coder's task prompt:

```
## ⚠️ INTERFACE CONTRACT (MANDATORY — violations will be rejected)

{interface_contract_yaml}

RULES:
1. You may ONLY create/modify files listed under YOUR ownership
2. Use include paths EXACTLY as specified (no src/ prefix, no relative paths)
3. Do NOT define STB_IMAGE_IMPLEMENTATION or similar third-party init macros
   unless you are the designated owner
4. Follow naming conventions exactly
5. When calling APIs from other modules, use the signatures from api_contracts
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

### Original Pitfalls (v1)
1. **Don't skip Discovery** — Coders without context write code that doesn't fit the project
2. **Don't let Explorers/Reviewers write files** — toolsets must be read-only (`["file"]` without terminal)
3. **Don't exceed 3 fix loop iterations** — diminishing returns; accept minor issues after 3
4. **Don't parallel-edit the same files** — if two Coders touch the same file, make them sequential
5. **Always filter reviews by confidence ≥ 80** — low-confidence findings are mostly noise
6. **Provide complete context to each Agent** — they have NO memory of other agents' work; include everything they need in the prompt
7. **Use `--max-turns` with Claude Code** — prevent runaway loops (15 for implementation, 20 for testing)
8. **Save intermediate artifacts** — if a phase fails, you can restart from the last good artifact instead of redoing everything

### v2 Additions (from production retrospective)

9. **NEVER skip Pre-flight Checks** — Provider auth failures mid-workflow waste all previous work. Run pre-flight BEFORE Phase 1, not after.
10. **ALWAYS inject Interface Contract into Coder prompts** — Without explicit include-path conventions and file ownership, parallel Coders produce incompatible code (wrong #include paths, duplicate third-party init macros, naming conflicts). This was the #1 integration failure in production.
11. **NEVER proceed past a Gate without validation** — Gate 2 (user approval) is especially critical. Auto-proceeding from plan to build without user confirmation led to wasted compute on wrong designs.
12. **Establish fallback BEFORE you need it** — Don't discover `delegate_task` is broken after 30 minutes of planning. Pre-flight determines the fallback engine for every role upfront.
13. **Single owner for third-party init macros** — `#define STB_IMAGE_IMPLEMENTATION` (and similar) must appear in EXACTLY one file. Assign one Coder as owner in the interface contract. Multiple definitions cause linker errors that are hard to debug across parallel agents.
14. **Dashboard is not optional for Complex/Mega tasks** — Without visibility into which agent is doing what, debugging multi-agent failures is guesswork. Always start the dashboard for ≥3 parallel agents.
15. **Fallback degrades gracefully, never skips** — If `delegate_task` fails for Explorer, the Orchestrator self-explores. If `claude -p` fails for Coder, use `delegate_task` with terminal toolset. A degraded phase is infinitely better than a skipped phase.
16. **Test the INTEGRATION, not just the units** — After parallel Coders complete, run a build/compile step BEFORE sending to Tester. Catch include-path and linking errors early.

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
