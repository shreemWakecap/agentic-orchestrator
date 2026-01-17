"""Custom exceptions for the orchestrator.

This module defines a hierarchy of exceptions that provide:
- Clear error classification
- Contextual information for debugging
- Proper HTTP status code mapping
"""


class OrchestratorError(Exception):
    """Base exception for all orchestrator errors.

    All custom exceptions should inherit from this class to enable
    consistent error handling across the application.
    """

    def __init__(self, message: str, details: dict = None):
        self.message = message
        self.details = details or {}
        super().__init__(message)


# ============== Plan Errors ==============


class PlanError(OrchestratorError):
    """Base exception for plan-related errors."""

    pass


class PlanNotFoundError(PlanError):
    """Raised when a plan cannot be found.

    HTTP Status: 404
    """

    def __init__(self, plan_id: str):
        self.plan_id = plan_id
        super().__init__(
            f"Plan '{plan_id}' not found",
            details={"plan_id": plan_id},
        )


class PlanStateError(PlanError):
    """Raised when plan is in invalid state for an operation.

    HTTP Status: 400
    """

    def __init__(self, plan_id: str, current_state: str, required_states: list[str]):
        self.plan_id = plan_id
        self.current_state = current_state
        self.required_states = required_states
        super().__init__(
            f"Plan '{plan_id}' is in '{current_state}' state. "
            f"Required: {', '.join(required_states)}",
            details={
                "plan_id": plan_id,
                "current_state": current_state,
                "required_states": required_states,
            },
        )


class PlanValidationError(PlanError):
    """Raised when plan content is invalid.

    HTTP Status: 400
    """

    def __init__(self, plan_id: str, validation_errors: list[str]):
        self.plan_id = plan_id
        self.validation_errors = validation_errors
        super().__init__(
            f"Plan '{plan_id}' validation failed: {'; '.join(validation_errors)}",
            details={
                "plan_id": plan_id,
                "validation_errors": validation_errors,
            },
        )


# ============== Workflow Errors ==============


class WorkflowError(OrchestratorError):
    """Base exception for workflow-related errors."""

    pass


class WorkflowExecutionError(WorkflowError):
    """Raised when workflow execution fails.

    HTTP Status: 500
    """

    def __init__(self, workflow: str, step: str = None, cause: str = None):
        self.workflow = workflow
        self.step = step
        self.cause = cause
        message = f"Workflow '{workflow}' execution failed"
        if step:
            message += f" at step '{step}'"
        if cause:
            message += f": {cause}"
        super().__init__(
            message,
            details={
                "workflow": workflow,
                "step": step,
                "cause": cause,
            },
        )


class WorkflowNotFoundError(WorkflowError):
    """Raised when a workflow type is not recognized.

    HTTP Status: 400
    """

    def __init__(self, workflow: str):
        self.workflow = workflow
        super().__init__(
            f"Unknown workflow type: '{workflow}'",
            details={"workflow": workflow},
        )


# ============== Agent Errors ==============


class AgentError(OrchestratorError):
    """Base exception for agent-related errors."""

    pass


class AgentNotFoundError(AgentError):
    """Raised when an agent cannot be loaded.

    HTTP Status: 500
    """

    def __init__(self, agent_name: str):
        self.agent_name = agent_name
        super().__init__(
            f"Agent '{agent_name}' not found",
            details={"agent_name": agent_name},
        )


class AgentExecutionError(AgentError):
    """Raised when agent execution fails.

    HTTP Status: 500
    """

    def __init__(self, agent_name: str, cause: str = None):
        self.agent_name = agent_name
        self.cause = cause
        message = f"Agent '{agent_name}' execution failed"
        if cause:
            message += f": {cause}"
        super().__init__(
            message,
            details={"agent_name": agent_name, "cause": cause},
        )


# ============== Build Errors ==============


class BuildError(OrchestratorError):
    """Base exception for build-related errors."""

    pass


class BuildStepError(BuildError):
    """Raised when a build step fails.

    HTTP Status: 500
    """

    def __init__(self, plan_id: str, step_id: str, cause: str = None):
        self.plan_id = plan_id
        self.step_id = step_id
        self.cause = cause
        message = f"Build step '{step_id}' failed for plan '{plan_id}'"
        if cause:
            message += f": {cause}"
        super().__init__(
            message,
            details={
                "plan_id": plan_id,
                "step_id": step_id,
                "cause": cause,
            },
        )


class BuildStateError(BuildError):
    """Raised when build state is invalid or corrupted.

    HTTP Status: 500
    """

    def __init__(self, plan_id: str, issue: str):
        self.plan_id = plan_id
        self.issue = issue
        super().__init__(
            f"Invalid build state for plan '{plan_id}': {issue}",
            details={"plan_id": plan_id, "issue": issue},
        )


# ============== Database Errors ==============


class DatabaseError(OrchestratorError):
    """Base exception for database-related errors.

    HTTP Status: 500
    """

    pass


class RecordNotFoundError(DatabaseError):
    """Raised when a database record is not found.

    HTTP Status: 404
    """

    def __init__(self, table: str, key: str, value: str):
        self.table = table
        self.key = key
        self.value = value
        super().__init__(
            f"Record not found in '{table}' where {key}='{value}'",
            details={"table": table, "key": key, "value": value},
        )


# ============== Retry Classification ==============


class TransientError(OrchestratorError):
    """Errors that may succeed on retry.

    Examples: network timeouts, rate limits, temporary unavailability
    """

    pass


class PermanentError(OrchestratorError):
    """Errors that will not succeed on retry.

    Examples: invalid input, missing resources, permission denied
    """

    pass
