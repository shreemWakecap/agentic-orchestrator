"""FastAPI exception handlers for the portal.

This module registers custom exception handlers that convert
OrchestratorError exceptions to appropriate HTTP responses.
"""
import logging
from fastapi import FastAPI, Request
from fastapi.responses import JSONResponse

from core.exceptions import (
    OrchestratorError,
    PlanNotFoundError,
    PlanStateError,
    PlanValidationError,
    WorkflowExecutionError,
    WorkflowNotFoundError,
    AgentNotFoundError,
    AgentExecutionError,
    BuildStepError,
    BuildStateError,
    DatabaseError,
    RecordNotFoundError,
)

logger = logging.getLogger(__name__)


def register_exception_handlers(app: FastAPI) -> None:
    """Register all exception handlers with the FastAPI app.

    Args:
        app: FastAPI application instance
    """

    @app.exception_handler(PlanNotFoundError)
    async def plan_not_found_handler(
        request: Request, exc: PlanNotFoundError
    ) -> JSONResponse:
        """Handle plan not found errors."""
        logger.warning(f"Plan not found: {exc.plan_id}")
        return JSONResponse(
            status_code=404,
            content={
                "error": "plan_not_found",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(PlanStateError)
    async def plan_state_handler(
        request: Request, exc: PlanStateError
    ) -> JSONResponse:
        """Handle plan state errors."""
        logger.warning(f"Invalid plan state: {exc.message}")
        return JSONResponse(
            status_code=400,
            content={
                "error": "invalid_plan_state",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(PlanValidationError)
    async def plan_validation_handler(
        request: Request, exc: PlanValidationError
    ) -> JSONResponse:
        """Handle plan validation errors."""
        logger.warning(f"Plan validation failed: {exc.message}")
        return JSONResponse(
            status_code=400,
            content={
                "error": "plan_validation_failed",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(WorkflowNotFoundError)
    async def workflow_not_found_handler(
        request: Request, exc: WorkflowNotFoundError
    ) -> JSONResponse:
        """Handle unknown workflow type errors."""
        logger.warning(f"Unknown workflow: {exc.workflow}")
        return JSONResponse(
            status_code=400,
            content={
                "error": "unknown_workflow",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(WorkflowExecutionError)
    async def workflow_execution_handler(
        request: Request, exc: WorkflowExecutionError
    ) -> JSONResponse:
        """Handle workflow execution errors."""
        logger.error(f"Workflow execution failed: {exc.message}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "workflow_execution_failed",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(AgentNotFoundError)
    async def agent_not_found_handler(
        request: Request, exc: AgentNotFoundError
    ) -> JSONResponse:
        """Handle agent not found errors."""
        logger.error(f"Agent not found: {exc.agent_name}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "agent_not_found",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(AgentExecutionError)
    async def agent_execution_handler(
        request: Request, exc: AgentExecutionError
    ) -> JSONResponse:
        """Handle agent execution errors."""
        logger.error(f"Agent execution failed: {exc.message}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "agent_execution_failed",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(BuildStepError)
    async def build_step_handler(
        request: Request, exc: BuildStepError
    ) -> JSONResponse:
        """Handle build step errors."""
        logger.error(f"Build step failed: {exc.message}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "build_step_failed",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(BuildStateError)
    async def build_state_handler(
        request: Request, exc: BuildStateError
    ) -> JSONResponse:
        """Handle build state errors."""
        logger.error(f"Invalid build state: {exc.message}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "invalid_build_state",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(RecordNotFoundError)
    async def record_not_found_handler(
        request: Request, exc: RecordNotFoundError
    ) -> JSONResponse:
        """Handle database record not found errors."""
        logger.warning(f"Record not found: {exc.message}")
        return JSONResponse(
            status_code=404,
            content={
                "error": "record_not_found",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(DatabaseError)
    async def database_handler(
        request: Request, exc: DatabaseError
    ) -> JSONResponse:
        """Handle general database errors."""
        logger.error(f"Database error: {exc.message}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "database_error",
                "message": exc.message,
                "details": exc.details,
            },
        )

    @app.exception_handler(OrchestratorError)
    async def orchestrator_error_handler(
        request: Request, exc: OrchestratorError
    ) -> JSONResponse:
        """Handle any other orchestrator errors."""
        logger.error(f"Orchestrator error: {exc.message}")
        return JSONResponse(
            status_code=500,
            content={
                "error": "orchestrator_error",
                "message": exc.message,
                "details": exc.details,
            },
        )
