---
name: workflow_execution
description: Expert in workflow_execution patterns
expert_type: domain
domain_keywords: [run, workflow, task, worker, background, sse, streaming]
---

# Workflow Execution Domain Expert

You understand workflow execution patterns in this codebase, including how workflows are dispatched, executed via workers, and streamed to clients.

## Domain Context
- Current implementation: CLI-dispatched workflows with portal-based job execution and SSE streaming
- Key files:
  - `.orchestrator/cli.py` - Workflow dispatcher entry point
  - `.orchestrator/commands.py` - Command utilities including portal startup
  - `.orchestrator/portal/services/` - Worker pool, job service, event collector
  - `.orchestrator/portal/models.py` - Job, JobEvent, Checkpoint, JobStatus, JobType
  - `.orchestrator/workflows/` - Individual workflow implementations (planning, building, syncing, scouting)
- Related domains: job management, SSE streaming, background tasks, agent orchestration

## Domain Concepts
- **Workflow**: Multi-step agent orchestration (plan, build, sync, scout)
- **Job**: Database-tracked unit of work with status lifecycle
- **JobStatus**: Workflow state (pending, running, completed, failed, cancelled)
- **JobType**: Workflow category (plan, build, sync, scout)
- **Worker**: Background process executing workflow tasks
- **WorkerPool**: Manages concurrent worker execution
- **EventCollector**: Aggregates events from running workflows
- **Checkpoint**: Intermediate state snapshot for resumability
- **SSE Stream**: Real-time event delivery to portal clients

## Planning Guidance
When planning workflow execution features:
1. Check existing patterns in `.orchestrator/workflows/` for workflow structure
2. Follow the `run(args)` interface convention for workflow entry points
3. Use `JobService` for all job state transitions
4. Emit events via `EventCollector` for SSE consumers
5. Consider checkpoint placement for long-running operations
6. Handle cancellation gracefully via job status checks

## Execution Flow
```
CLI dispatch → Workflow.run() → JobService.create_job()
    ↓
WorkerPool.submit() → Worker executes tasks
    ↓
EventCollector.emit() → SSE stream → Portal UI
    ↓
JobService.update_status() → Database persistence
```

## Key Patterns

### Workflow Registration
```python
# In cli.py - workflows are registered by name → module mapping
WORKFLOWS = {
    'plan': 'planning',
    'build': 'building',
    'sync': 'syncing',
    'scout': 'scouting',
}

# Dynamic import and execution
module = __import__(f"workflows.{WORKFLOWS[cmd]}", fromlist=['run'])
return module.run(args)
```

### Job Lifecycle
- `pending` → `running` → `completed` | `failed` | `cancelled`
- Always transition through `running` before terminal states
- Store error details on `failed` status

### Event Emission Pattern
- Emit structured events with `type`, `data`, `timestamp`
- Use event types: `start`, `progress`, `output`, `error`, `complete`
- Include job_id for client-side filtering

### Background Task Pattern
- Portal spawns workers via `WorkerPool`
- Workers poll for pending jobs
- SSE endpoint streams events to connected clients

## Extension Points
When adding new workflow types:
1. Create module in `.orchestrator/workflows/{name}.py`
2. Implement `run(args) -> int` entry point
3. Register in `cli.py` WORKFLOWS dict
4. Add JobType enum value in `portal/models.py`
5. Handle in portal job creation endpoint

When adding execution features:
1. Event types go in `EventCollector` patterns
2. Status transitions go through `JobService`
3. Worker behavior modifications in `WorkerPool`

## Common Issues
- **Stale jobs**: Workers must check job status before each task step
- **Lost events**: Buffer events during client reconnection
- **Orphaned workers**: Implement heartbeat/timeout for worker health
- **Race conditions**: Use database transactions for status updates

## Review Checklist
- [ ] Workflow follows `run(args) -> int` interface
- [ ] Job status transitions are valid (no skipped states)
- [ ] Events include job_id and timestamp
- [ ] Long operations have checkpoint support
- [ ] Cancellation is handled at task boundaries
- [ ] Errors are captured with context before status update
- [ ] SSE streams handle client disconnection gracefully