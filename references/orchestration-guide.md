# Multi-Agent Development Orchestration Reference
# This document provides the Orchestrator (Hermes) with step-by-step
# commands and decision logic for running the full pipeline.

## Quick Start Checklist

Before starting, verify:
```bash
# 1. Claude Code installed and authenticated
claude auth status --text

# 2. Project is a git repo
git status

# 3. Clean working tree (commit or stash changes)
git diff --stat
```

## Phase-by-Phase Orchestration Commands

### Phase 1: Discovery

```python
# Deploy 3 parallel Explorers
# Use delegate_task with tasks=[] for parallel execution
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
```

**After Explorers return:**
1. Parse YAML from each Explorer's output
2. Merge into a single discovery context
3. Check for gaps — if a critical area wasn't explored, dispatch targeted Explorer
4. Save merged context for Phase 2

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
3. Present summary to user:
   - Architecture overview
   - Number of tasks and parallel groups
   - Estimated complexity
4. Ask user: "Proceed with implementation?" / "Modify plan?"
5. If user approves, move to Phase 3

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

RULES:
1. Follow TDD — write failing test, implement, verify
2. Run tests after each change
3. Commit with descriptive message
4. Do NOT modify files outside task scope' \
  --allowedTools 'Read,Edit,Write,Bash' \
  --max-turns 15 \
  --output-format json""",
    workdir="{project_path}",
    timeout=300
)

# Option B: Parallel Coders (independent tasks in same group)
# Launch each as background terminal, then poll for completion

# Coder A
terminal(
    command="claude -p '{task_A_prompt}' --allowedTools 'Read,Edit,Write,Bash' --max-turns 15 --output-format json",
    workdir="{project_path}",
    timeout=300,
    background=True,
    notify_on_complete=True
)

# Coder B (parallel)
terminal(
    command="claude -p '{task_B_prompt}' --allowedTools 'Read,Edit,Write,Bash' --max-turns 15 --output-format json",
    workdir="{project_path}",
    timeout=300,
    background=True,
    notify_on_complete=True
)
```

**After each group completes:**
1. Parse JSON output — check `subtype` for success/error
2. Run quick sanity check: `git log --oneline -5` to see commits
3. Run tests: `{test_command}` — must pass before next group
4. If tests fail, dispatch fix Coder before proceeding

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

### Fix Loop (if needed)

```
iteration = 0
while has_critical_or_high_issues AND iteration < 3:
    # Dispatch fix Coder
    terminal(command="claude -p 'Fix these issues: {issues_yaml}' ...")
    
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

## Final Report Template

After all phases complete, present to user:

```markdown
## 🏁 Multi-Agent Development Report

### Feature: {feature_name}
### Status: ✅ Complete / ⚠️ Complete with notes

### Phase Summary
| Phase | Duration | Agents | Result |
|-------|----------|--------|--------|
| Discovery | ~30s | 3 Explorers | ✅ Codebase mapped |
| Planning | ~45s | 1 Architect | ✅ {N} tasks planned |
| Building | ~{M}m | {K} Coders | ✅ {N} tasks implemented |
| Verification | ~60s | 1 Tester + 3 Reviewers | ✅ Clean / ⚠️ {X} issues |

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
