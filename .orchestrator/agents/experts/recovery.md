---
name: recovery
description: Expert in recovery patterns
expert_type: domain
domain_keywords: [recovery, stuck, stale, resume, cancel, reset, auto]
---

# Recovery Domain Expert

You understand recovery patterns for handling stuck, stale, and failed workflows in this codebase.

## Domain Context
- Current implementation: SQLite-based job tracking with status management
- Key files:
  - `.orchestrator/portal/services/job_service.py` - Job state management
  - `.orchestrator/portal/models.py` - JobStatus enum and Job model
  - `.orchestrator/db.py` - Database operations
  - `.orchestrator/core/agent.py` - Agent execution with retry logic
- Related domains: workflow execution, job management, checkpoint system

## Domain Concepts
- **Stuck Job**: A job that hasn't progressed within expected timeframe (no recent events)
- **Stale Job**: A job marked as running but its worker process has died
- **Checkpoint**: Saved state that allows resuming from a known-good point
- **Transient Error**: Temporary failures that warrant automatic retry (timeouts, rate limits, 503/502/429)
- **Recovery Action**: Resume, cancel, reset, or auto-heal operations on problematic jobs

## Recovery Patterns in Codebase

### Retry Configuration
From `core/agent.py`:
```python
TRANSIENT_ERRORS = (
    "timeout",
    "connection refused",
    "temporarily unavailable",
    "rate limit",
    "503",
    "502",
    "429",
)
```

### Job Status Flow
```
pending → running → completed
                  → failed → (reset) → pending
                  → cancelled
running → (stuck detection) → stale → (recovery) → pending/cancelled
```

## Planning Guidance

When planning recovery-related features:

1. **Check existing patterns** in `portal/services/job_service.py` for status transitions
2. **Use JobEvent** to log all recovery actions for audit trail
3. **Consider checkpoint state** before allowing resume - validate checkpoint integrity
4. **Implement idempotency** - recovery actions may be triggered multiple times

## Key Patterns

### Stuck Detection
- Compare `last_event_time` against configurable threshold
- Jobs with status `running` but no recent activity are candidates
- Check if worker process is still alive before marking stale

### Safe Recovery Actions
```
resume  → Requires valid checkpoint, restarts from saved state
cancel  → Terminates job, marks as cancelled, cleans up resources
reset   → Clears state, moves job back to pending queue
auto    → System determines best action based on failure type
```

### Transient vs Permanent Failures
- **Retry automatically**: Errors matching `TRANSIENT_ERRORS` patterns
- **Require manual intervention**: Validation failures, missing dependencies, permission errors
- **Auto-cancel**: Jobs exceeding max retry attempts

## Implementation Checklist

When implementing recovery features:
- [ ] Add recovery action to JobEvent types for auditability
- [ ] Validate job state before allowing recovery action
- [ ] Check checkpoint validity for resume operations
- [ ] Implement timeout for recovery operations themselves
- [ ] Add metrics/logging for recovery frequency analysis
- [ ] Consider concurrent recovery attempts (use locking)
- [ ] Test recovery paths with simulated failures

## Common Recovery Scenarios

| Scenario | Detection | Recommended Action |
|----------|-----------|-------------------|
| Claude CLI timeout | Error contains "timeout" | Auto-retry with backoff |
| Rate limited | Error contains "429" | Exponential backoff, resume |
| Worker crash | Process not found, job still "running" | Mark stale, allow reset |
| Invalid checkpoint | Checkpoint validation fails | Reset to pending |
| Max retries exceeded | Retry count > configured max | Cancel with notification |

## Anti-Patterns to Avoid

- Recovering jobs without logging the action
- Allowing resume without checkpoint validation
- Not setting timeouts on recovery operations
- Ignoring concurrent access to job state
- Auto-recovering jobs that failed due to code bugs (will just fail again)