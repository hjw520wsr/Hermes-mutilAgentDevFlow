# Multi-Agent Development Orchestration Reference
# This document provides the Orchestrator (Hermes) with step-by-step
# commands and decision logic for running the full pipeline.
# v2: Added pre-flight, gates, fallback chains, interface contract generation

## Quick Start Checklist

Before starting, run the **Pre-flight Checks** (MANDATORY):

```python
# ── Step 1: Check delegate_task availability ──
try:
    preflight = delegate_task(
        goal="Return the text 'PREFLIGHT_OK' and nothing else.",
        toolsets=[]
    )
    delegate_ok = "PREFLIGHT_OK" in str(preflight)
except:
    delegate_ok = False

# ── Step 2: Check Claude Code CLI ──
claude_auth = terminal(command="claude auth status --text 2>&1", timeout=10)
claude_ok = claude_auth.exit_code == 0

# ── Step 3: Check git working tree ──
git_status = terminal(command="git status --porcelain", workdir=project_path, timeout=10)
git_clean = len(git_status.output.strip()) == 0

# ── Step 4: Establish fallback plan ──
fallback_plan = {
    "explorer": "delegate_task" if delegate_ok else "orchestrator-self",
    "architect": "delegate_task" if delegate_ok else "orchestrator-self",
    "coder": "claude-cli" if claude_ok else ("delegate_task" if delegate_ok else "orchestrator-self"),
    "tester": "claude-cli" if claude_ok else ("delegate_task" if delegate_ok else "orchestrator-self"),
    "reviewer": "delegate_task" if delegate_ok else "orchestrator-self",
}

# ── Step 5: GATE 0 — Proceed only if at least one engine works ──
assert delegate_ok or claude_ok, "FATAL: Neither delegate_task nor Claude CLI available"
if not git_clean:
    terminal(command="git stash", workdir=project_path)  # auto-stash
```

## Phase-by-Phase Orchestration Commands

### Phase 1: Discovery

```python
# Deploy 3 parallel Explorers (with fallback awareness)
if fallback_plan["explorer"] == "delegate_task":
    delegate_task(tasks=[
        {
            "goal": "Explore project structure and tech stack",
            "context": "<fill from templates/explorer-prompts.yaml: structure_explorer>",
            "toolsets": ["file"]
        },
        {
            "goal": "Analyze existing code related to the feature",
            "context": "<fill from templates/explorer-prompts.yaml: feature_explorer>",
            "toolsets": ["file"]
        },
        {
            "goal": "Analyze test infrastructure and quality tools",
            "context": "<fill from templates/explorer-prompts.yaml: test_explorer>",
            "toolsets": ["file"]
        }
    ])
elif fallback_plan["explorer"] == "claude-acp":
    # Fallback: use Claude Code's ACP transport
    delegate_task(tasks=[...same tasks...],
        acp_command='claude', acp_args=['--acp', '--stdio'])
else:
    # Last resort: Orchestrator self-explores using its own tools
    # Use read_file, search_files to gather the same information manually
    pass
```

**After Explorers return:**
1. Parse YAML from each Explorer's output
2. Merge into a single discovery context
3. Check for gaps — if a critical area wasn't explored, dispatch targeted Explorer
4. Save merged context for Phase 2

**⊕ GATE 1: Validate before proceeding to Phase 2**
```python
# Gate 1 checks
assert merged_discovery is not None, "No discovery report produced"
assert "structure" in merged_discovery or "tech_stack" in merged_discovery, \
    "Discovery report missing critical sections"
# If gate fails: re-run with fallback engine
```

### Phase 2: Planning

```python
# Deploy Architect agent
delegate_task(
    goal="Design architecture and create implementation plan",
    context="<fill from templates/architect-prompt.yaml with merged discovery>",
    toolsets=["file"]
)
```

**After Architect returns:**
1. Read `docs/plans/architecture.yaml` and `docs/plans/plan.md`
2. Parse PARALLEL-GROUP markers from the plan
3. **Generate Interface Contract** from architecture output:

```python
# v2: Generate interface contract from architect output
interface_contract = {
    "include_paths": {
        "style": "relative to src/",
        "base_directory": "src/",
        "examples": {"correct": [...], "wrong": [...]}
    },
    "file_ownership": {},  # filled per-coder from plan tasks
    "third_party_init": {},  # assign single owner per library
    "naming": {...},  # from discovery conventions
    "api_contracts": [...]  # from architecture.yaml interfaces
}

# Assign file ownership per Coder based on PARALLEL-GROUP tasks
for group in plan.parallel_groups:
    for task in group.tasks:
        coder_id = f"coder-{task.id}"
        interface_contract["file_ownership"][coder_id] = {
            "creates": task.files_to_create,
            "modifies": task.files_to_modify,
        }

# Save interface contract as artifact
write_file("docs/plans/interface-contract.yaml", yaml.dump(interface_contract))
```

4. **⊕ GATE 2: User confirmation REQUIRED**
```python
# Present plan summary to user
summary = f"""
Architecture: {architecture_overview}
Tasks: {total_tasks} across {parallel_groups} parallel groups
Interface Contract: {len(file_ownership)} coder assignments
Estimated duration: ~{estimated_minutes}m
"""

# MANDATORY user approval — do NOT auto-proceed
response = clarify(
    question=f"Review the plan:\n{summary}\nProceed with implementation?",
    choices=["Approve and proceed", "Modify plan", "Cancel"]
)

if "Modify" in response:
    # Re-run Architect with user's modification feedback
    pass
elif "Cancel" in response:
    # Abort workflow
    pass
# Only proceed to Phase 3 if user approved
```

### Phase 3: Building

**For each PARALLEL-GROUP (sequential groups):**

```python
# Option A: Single Coder (simple tasks)
terminal(
    command="""claude -p 'TASK: {task_title}

{task_full_text}

PROJECT CONTEXT:
- Tech stack: {tech_stack}
- Test command: {test_command}
- Conventions: {conventions}

{interface_contract_for_this_coder}

RULES:
1. Follow TDD — write failing test, implement, verify
2. Run tests after each change
3. Commit with descriptive message
4. Do NOT modify files outside task scope
5. Follow Interface Contract strictly' \
  --allowedTools 'Read,Edit,Write,Bash' \
  --max-turns 15 \
  --output-format json""",
    workdir="{project_path}",
    timeout=300
)

# Option B: Parallel Coders (independent tasks in same group)
# IMPORTANT: Each Coder gets their own interface_contract section
# with ONLY their file ownership listed

# Coder A
terminal(
    command="claude -p '{task_A_prompt_with_interface_contract}' --allowedTools 'Read,Edit,Write,Bash' --max-turns 15 --output-format json",
    workdir="{project_path}",
    timeout=300,
    background=True,
    notify_on_complete=True
)

# Coder B (parallel)
terminal(
    command="claude -p '{task_B_prompt_with_interface_contract}' --allowedTools 'Read,Edit,Write,Bash' --max-turns 15 --output-format json",
    workdir="{project_path}",
    timeout=300,
    background=True,
    notify_on_complete=True
)

# ── Fallback if Claude CLI fails ──
# Use delegate_task with terminal toolset instead:
# delegate_task(
#     goal="Implement task: {task_title}",
#     context="{task_prompt_with_interface_contract}",
#     toolsets=["terminal", "file"]
# )
```

**After each group completes:**
1. Parse JSON output — check `subtype` for success/error
2. **v2: Check for cross-Coder dependency reports** in completion output
3. If any Coder reported cross-dependencies, handle them before next group
4. Run quick sanity check: `git log --oneline -5` to see commits
5. **v2: Run integration build** — `{build_command}` to catch include-path errors early
6. Run tests: `{test_command}` — must pass before next group
7. If tests fail, dispatch fix Coder before proceeding

### Phase 4: Verification

**Step 1: Tester**
```python
# Get list of changed files
terminal(command="git diff --name-only {base_commit}..HEAD", workdir="{project_path}")

# Deploy Tester
terminal(
    command="""claude -p '<fill from templates/tester-prompt.yaml>' \
      --allowedTools 'Read,Write,Bash' \
      --max-turns 20 \
      --output-format json""",
    workdir="{project_path}",
    timeout=300
)

# Fallback if Claude CLI unavailable:
# delegate_task(goal="Run tests and write missing tests", 
#     context="...", toolsets=["terminal", "file"])
```

**Step 2: Parallel Reviewers**
```python
# Get diffs for reviewers
terminal(command="git diff {base_commit}..HEAD", workdir="{project_path}")

# Deploy 3 parallel Reviewers
delegate_task(tasks=[
    {
        "goal": "Review for bugs and logic errors",
        "context": "<fill from templates/reviewer-prompts.yaml: bug_reviewer>",
        "toolsets": ["file"]
    },
    {
        "goal": "Review for security vulnerabilities",
        "context": "<fill from templates/reviewer-prompts.yaml: security_reviewer>",
        "toolsets": ["file"]
    },
    {
        "goal": "Review for architecture and design quality",
        "context": "<fill from templates/reviewer-prompts.yaml: architecture_reviewer>",
        "toolsets": ["file"]
    }
])

# Fallback: If delegate_task fails, use Claude ACP:
# delegate_task(tasks=[...], acp_command='claude', acp_args=['--acp', '--stdio'])
# Last resort: Orchestrator self-reviews by reading diffs and analyzing code
```

**Step 3: Aggregate and Filter Reviews**
```
For each reviewer's output:
  1. Parse YAML issues list
  2. Filter: keep only confidence >= 80
  3. Tag with reviewer source (bug/security/architecture)

Deduplication:
  - Group issues by (file, line ±3)
  - If multiple reviewers flag same location:
    → Keep highest confidence finding
    → Merge evidence from all reviewers
    → Escalate severity if 2+ reviewers agree

Severity routing:
  critical (confidence ≥ 90) → MUST fix
  high (confidence ≥ 80)     → SHOULD fix
  medium                     → present to user
  low                        → informational only
```

**⊕ GATE 3: Verify before completion**
```python
assert tester_ran, "Tester phase was skipped — NOT acceptable"
assert reviewer_ran, "Review phase was skipped — NOT acceptable"
assert final_tests_pass, "Final test suite has failures"
# If critical issues remain after 3 fix loops, report to user
```

### Fix Loop (if needed)

```
iteration = 0
while has_critical_or_high_issues AND iteration < 3:
    # Dispatch fix Coder (with interface contract maintained)
    terminal(command="claude -p 'Fix these issues: {issues_yaml}' ...")
    
    # Fallback chain applies here too
    
    # Re-run reviewers on fixed code
    delegate_task(tasks=[...reviewers...])
    
    # Re-filter
    iteration += 1

if iteration == 3 AND still_has_issues:
    # Accept remaining issues, report to user
    print("Max fix iterations reached. Remaining issues: ...")
```

## Complexity Routing Decision Tree

```python
def route_complexity(requirement, project_size):
    """Determine which phases to run."""
    
    # Simple: bug fix, typo, small config change
    if is_single_file_change(requirement):
        return ["phase3_coder_only"]
    
    # Medium: clear feature, few files
    if estimated_files <= 5 and no_design_decisions_needed:
        return ["phase1_single_explorer", "phase3_coder", "phase4_single_reviewer"]
    
    # Complex: new feature with design decisions
    if needs_architecture_design:
        return ["phase1_full", "phase2", "phase3", "phase4_full"]
    
    # Mega: system-wide changes
    if estimated_files > 15 or multiple_subsystems:
        return ["phase1_full", "phase2", "phase3_parallel_worktrees", "phase4_full"]
```

**NOTE:** Pre-flight checks and Gate 0 apply to ALL complexity levels. Gate 2 (user approval) applies to Complex and Mega only.

## Final Report Template

After all phases complete, present to user:

```markdown
## 🏁 Multi-Agent Development Report

### Feature: {feature_name}
### Status: ✅ Complete / ⚠️ Complete with notes / 🔶 Degraded (fallback used)

### Pre-flight
- delegate_task: ✅/❌ | claude CLI: ✅/❌
- Fallback engines used: {list or "none"}

### Phase Summary
| Phase | Duration | Agents | Engine | Result |
|-------|----------|--------|--------|--------|
| Discovery | ~30s | 3 Explorers | {engine} | ✅ Codebase mapped |
| Planning | ~45s | 1 Architect | {engine} | ✅ {N} tasks planned |
| Building | ~{M}m | {K} Coders | {engine} | ✅ {N} tasks implemented |
| Verification | ~60s | 1 Tester + 3 Reviewers | {engine} | ✅ Clean / ⚠️ {X} issues |

### Gates
| Gate | Status | Notes |
|------|--------|-------|
| Gate 0 (Pre-flight) | ✅ Passed / 🔶 Degraded | {fallback notes} |
| Gate 1 (Discovery → Planning) | ✅ | Discovery complete |
| Gate 2 (Planning → Building) | ✅ | User approved |
| Gate 3 (Building → Complete) | ✅ | Tests pass, review clean |

### Changes
- Files created: {list}
- Files modified: {list}
- Tests added: {count}
- Commits: {count}

### Test Results
- Total: {N} tests
- Passed: {N}
- Coverage (new code): {X}%

### Review Summary
- Issues found: {total}
- Filtered (confidence < 80): {filtered_out}
- Fixed: {fixed}
- Remaining (accepted): {remaining}

### Fix Loop Iterations: {0-3}

### What's Next
- [ ] Manual review of changes: `git log --oneline {base}..HEAD`
- [ ] Run full CI pipeline
- [ ] Deploy to staging
```
