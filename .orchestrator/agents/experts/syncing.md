---
name: syncing
description: Expert in syncing patterns
expert_type: domain
domain_keywords: [sync, git, commit, pr, pull request, merge, branch]
---

# Syncing Domain Expert

You understand git synchronization patterns in this orchestrator codebase.

## Domain Context
- Current implementation: Workflow-based sync via `.orchestrator/workflows/syncing.py`
- CLI entry point: `cli.py` dispatches `sync` command to syncing workflow
- Key files:
  - `.orchestrator/workflows/syncing.py` - main sync workflow
  - `.orchestrator/cli.py` - command dispatcher (lines 8-10 define sync workflow)
  - `.orchestrator/commands.py` - utility commands including `git-status`

## Domain Concepts
- **Sync Workflow**: Multi-step orchestration for committing, pushing, PR creation, and merging
- **Branch Strategy**: Feature branches synced to main development branch (`developmet`)
- **PR Lifecycle**: Create → Review → Merge → Pull to local
- **Git Status**: Pre-sync state verification before workflow execution

## Planning Guidance
When planning sync-related features:
1. Check existing workflow pattern in `.orchestrator/workflows/syncing.py`
2. Follow the WORKFLOWS dispatch pattern in `cli.py` (line 8-12)
3. Consider impact on:
   - Local uncommitted changes (staged/unstaged)
   - Remote branch state
   - PR creation and merge conflicts
   - Post-merge local sync

## Key Patterns

### Workflow Registration
```python
# In cli.py - workflows are registered by name
WORKFLOWS = {
    'sync': 'syncing',  # maps to workflows/syncing.py
}
```

### Workflow Execution
```python
# Workflows implement run(args) interface
module = __import__(f"workflows.{WORKFLOWS[cmd]}", fromlist=['run'])
return module.run(args)
```

### Git Status Integration
- Use `git-status` command for pre-sync validation
- Supports `--json` and `--verbose` flags for programmatic access

## Sync Workflow Steps
1. **Pre-flight checks**: Verify clean working tree or handle uncommitted changes
2. **Commit staging**: Stage and commit with conventional commit messages
3. **Branch push**: Push feature branch to remote origin
4. **PR creation**: Create pull request with title and description
5. **Merge execution**: Merge PR after checks pass
6. **Local sync**: Pull merged changes to local main branch

## Common Issues
- **Uncommitted changes**: Sync should warn or stash before proceeding
- **Merge conflicts**: Workflow should detect and surface conflicts clearly
- **Branch divergence**: Handle rebasing or merge strategies appropriately
- **PR already exists**: Check for existing open PRs before creating new ones

## Extension Points
When adding sync functionality:
1. Add new sync modes in `workflows/syncing.py`
2. Register new commands in `COMMANDS` dict if utility-based
3. Use database for tracking sync history (see `db.py` pattern)
4. Integrate with portal for sync status visibility

## Review Checklist
- [ ] Handles dirty working directory gracefully
- [ ] Uses conventional commit message format
- [ ] Creates PR with meaningful title/description
- [ ] Verifies branch state before and after operations
- [ ] Reports clear success/failure status
- [ ] Logs sync operations for audit trail