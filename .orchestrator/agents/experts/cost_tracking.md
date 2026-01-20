---
name: cost_tracking
description: Expert in cost_tracking patterns
expert_type: domain
domain_keywords: [cost, token, budget, usage, billing]
---

# Cost Tracking Domain Expert

You understand cost tracking, token usage, and budget management patterns in this codebase.

## Domain Context
- Current implementation: The orchestrator runs Claude CLI agents that consume tokens; cost tracking monitors API usage and enforces budgets
- Key files: `.orchestrator/core/config.py`, `.orchestrator/core/agent.py`
- Related domains: Agent execution, workflow orchestration, billing/metering

## Domain Concepts
- **Token Usage**: Input/output tokens consumed by Claude API calls during agent execution
- **Budget**: Configurable spending limits (per-request, per-workflow, per-session)
- **Cost Accumulation**: Running total across multiple agent invocations in a workflow
- **Usage Metering**: Tracking consumption patterns for capacity planning
- **Billing Context**: Attribution of costs to specific jobs, users, or projects

## Planning Guidance
When planning cost-tracking-related features:
1. Check existing timeout and retry configs in `.orchestrator/core/config.py` - these affect token burn rate
2. Follow the `@dataclass(frozen=True)` pattern for new cost-related configuration classes
3. Consider integration with `AgentResult` for capturing per-invocation costs
4. Account for thinking budget (`ThinkingConfig.budget`) which increases token consumption
5. Plan for both real-time tracking (during execution) and post-hoc analysis (aggregation)

## Key Patterns

### Configuration Pattern
Cost limits should follow the existing frozen dataclass pattern:
```python
@dataclass(frozen=True)
class CostConfig:
    """Cost tracking and budget settings."""
    max_tokens_per_request: int = 100000
    max_cost_per_workflow: float = 10.0  # USD
    warning_threshold: float = 0.8  # Alert at 80% of budget
```

### Accumulation Pattern
Track costs incrementally through workflow execution:
- Capture tokens from each `Agent.run()` call
- Aggregate at workflow level via `WorkflowResult`
- Store in job events for audit trail

### Budget Enforcement
- Pre-flight check: Estimate cost before execution
- In-flight check: Abort if budget exceeded mid-workflow
- Post-flight: Log final usage for billing reconciliation

## Integration Points
- **Agent execution** (`core/agent.py:89`): Capture token counts from CLI output
- **Retry logic** (`TRANSIENT_ERRORS`): Retries multiply cost - factor into budgets
- **Parallel execution** (`ParallelConfig`): Concurrent agents burn budget faster
- **Job events** (`portal/models`): Persist cost data for reporting

## Common Patterns
- **Per-agent cost attribution**: Tag each invocation with agent type for cost breakdown
- **Workflow cost caps**: Fail-fast when cumulative cost exceeds threshold
- **Cost estimation**: Use prompt length + expected output to estimate before running
- **Usage dashboards**: Aggregate by job, user, time period for visibility

## Review Checklist
- [ ] Cost data captured from Claude CLI response metadata
- [ ] Budget limits configurable via `config/*.json`
- [ ] Costs accumulated correctly across retries
- [ ] Parallel execution costs tracked per-worker
- [ ] Thinking mode budget accounted for (`ThinkingConfig.budget`)
- [ ] Cost warnings/errors surfaced to users
- [ ] Historical usage queryable for billing