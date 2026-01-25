"""
Token Usage Signal - Emits events when runs execute or plans are estimated.

The TokenUsageSignal is a signaling system that:
1. Emits events when execution starts
2. Emits events when execution completes (with actual token usage)
3. Emits events when plan estimation completes
4. Allows subscribers to react to token usage events
"""
import asyncio
import logging
from datetime import datetime
from enum import Enum
from typing import Optional, Dict, Any, List, Callable, Awaitable
from dataclasses import dataclass, field

logger = logging.getLogger(__name__)


class SignalType(str, Enum):
    """Signal types for token usage events."""
    EXECUTION_STARTED = "execution_started"
    EXECUTION_COMPLETED = "execution_completed"
    ESTIMATION_COMPLETED = "estimation_completed"


@dataclass
class TokenUsageData:
    """Data structure for token usage information."""
    job_id: str
    plan_id: Optional[str] = None
    input_tokens: int = 0
    output_tokens: int = 0
    total_tokens: int = 0
    estimated_input_tokens: int = 0
    estimated_output_tokens: int = 0
    estimated_total_tokens: int = 0
    model: str = ""
    cost_estimate: float = 0.0
    actual_cost: float = 0.0
    timestamp: datetime = field(default_factory=datetime.utcnow)
    metadata: Dict[str, Any] = field(default_factory=dict)


@dataclass
class TokenUsageEvent:
    """Event emitted by TokenUsageSignal."""
    signal_type: SignalType
    data: TokenUsageData
    timestamp: datetime = field(default_factory=datetime.utcnow)


# Type for signal handler callback
SignalHandler = Callable[[TokenUsageEvent], Awaitable[None]]


class TokenUsageSignal:
    """
    Emits signals when token usage events occur.

    Usage:
        signal = TokenUsageSignal()

        # Subscribe to events
        signal.subscribe(my_handler)

        # Emit events
        await signal.emit(SignalType.EXECUTION_STARTED, TokenUsageData(...))

        # Unsubscribe
        signal.unsubscribe(my_handler)
    """

    def __init__(self):
        """Initialize the token usage signal."""
        self._handlers: List[SignalHandler] = []
        self._event_history: List[TokenUsageEvent] = []
        self._history_max_size: int = 100  # Reduced from 1000 to prevent memory bloat
        self._lock = asyncio.Lock()

    def subscribe(self, handler: SignalHandler) -> None:
        """
        Subscribe a handler to receive token usage events.

        Args:
            handler: Async callback function that receives TokenUsageEvent
        """
        if handler not in self._handlers:
            self._handlers.append(handler)
            logger.debug(f"Handler subscribed to TokenUsageSignal: {handler.__name__}")

    def unsubscribe(self, handler: SignalHandler) -> None:
        """
        Unsubscribe a handler from token usage events.

        Args:
            handler: The handler to remove
        """
        if handler in self._handlers:
            self._handlers.remove(handler)
            logger.debug(f"Handler unsubscribed from TokenUsageSignal: {handler.__name__}")

    async def emit(
        self,
        signal_type: SignalType,
        data: TokenUsageData,
    ) -> None:
        """
        Emit a token usage event to all subscribers.

        Args:
            signal_type: Type of signal (EXECUTION_STARTED, EXECUTION_COMPLETED, ESTIMATION_COMPLETED)
            data: Token usage data associated with the event
        """
        event = TokenUsageEvent(
            signal_type=signal_type,
            data=data,
            timestamp=datetime.utcnow(),
        )

        # Add to history with proactive cleanup
        async with self._lock:
            self._event_history.append(event)
            # Proactive cleanup: trim 20% when limit reached to reduce frequency of trimming
            if len(self._event_history) > self._history_max_size:
                trim_count = int(self._history_max_size * 0.2)  # Remove 20%
                self._event_history = self._event_history[trim_count:]

        logger.info(
            f"TokenUsageSignal emitting {signal_type.value} for job {data.job_id}, "
            f"tokens: {data.total_tokens}, estimated: {data.estimated_total_tokens}"
        )

        # Notify all handlers
        for handler in self._handlers:
            try:
                await handler(event)
            except Exception as e:
                logger.error(f"Error in token usage signal handler {handler.__name__}: {e}")

    async def emit_execution_started(
        self,
        job_id: str,
        plan_id: Optional[str] = None,
        estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
        model: str = "",
        cost_estimate: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Emit an execution started signal.

        Args:
            job_id: The job identifier
            plan_id: Optional plan identifier
            estimated_input_tokens: Estimated input tokens for this execution
            estimated_output_tokens: Estimated output tokens for this execution
            model: Model being used
            cost_estimate: Estimated cost for this execution
            metadata: Additional metadata
        """
        data = TokenUsageData(
            job_id=job_id,
            plan_id=plan_id,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            estimated_total_tokens=estimated_input_tokens + estimated_output_tokens,
            model=model,
            cost_estimate=cost_estimate,
            metadata=metadata or {},
        )
        await self.emit(SignalType.EXECUTION_STARTED, data)

    async def emit_execution_completed(
        self,
        job_id: str,
        plan_id: Optional[str] = None,
        input_tokens: int = 0,
        output_tokens: int = 0,
        estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
        model: str = "",
        actual_cost: float = 0.0,
        cost_estimate: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Emit an execution completed signal.

        Args:
            job_id: The job identifier
            plan_id: Optional plan identifier
            input_tokens: Actual input tokens used
            output_tokens: Actual output tokens used
            estimated_input_tokens: Originally estimated input tokens
            estimated_output_tokens: Originally estimated output tokens
            model: Model that was used
            actual_cost: Actual cost incurred
            cost_estimate: Originally estimated cost
            metadata: Additional metadata
        """
        data = TokenUsageData(
            job_id=job_id,
            plan_id=plan_id,
            input_tokens=input_tokens,
            output_tokens=output_tokens,
            total_tokens=input_tokens + output_tokens,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            estimated_total_tokens=estimated_input_tokens + estimated_output_tokens,
            model=model,
            actual_cost=actual_cost,
            cost_estimate=cost_estimate,
            metadata=metadata or {},
        )
        await self.emit(SignalType.EXECUTION_COMPLETED, data)

    async def emit_estimation_completed(
        self,
        job_id: str,
        plan_id: Optional[str] = None,
        estimated_input_tokens: int = 0,
        estimated_output_tokens: int = 0,
        model: str = "",
        cost_estimate: float = 0.0,
        metadata: Optional[Dict[str, Any]] = None,
    ) -> None:
        """
        Emit an estimation completed signal.

        Args:
            job_id: The job identifier (may be empty for estimates without execution)
            plan_id: Optional plan identifier
            estimated_input_tokens: Estimated input tokens
            estimated_output_tokens: Estimated output tokens
            model: Model for estimation
            cost_estimate: Estimated cost
            metadata: Additional metadata
        """
        data = TokenUsageData(
            job_id=job_id,
            plan_id=plan_id,
            estimated_input_tokens=estimated_input_tokens,
            estimated_output_tokens=estimated_output_tokens,
            estimated_total_tokens=estimated_input_tokens + estimated_output_tokens,
            model=model,
            cost_estimate=cost_estimate,
            metadata=metadata or {},
        )
        await self.emit(SignalType.ESTIMATION_COMPLETED, data)

    def get_recent_events(self, limit: int = 100) -> List[TokenUsageEvent]:
        """
        Get recent token usage events.

        Args:
            limit: Maximum number of events to return

        Returns:
            List of recent TokenUsageEvent objects
        """
        return self._event_history[-limit:]

    def clear_history(self) -> None:
        """Clear the event history."""
        self._event_history.clear()
        logger.debug("TokenUsageSignal history cleared")


# Singleton instance
_signal: Optional[TokenUsageSignal] = None


def get_token_usage_signal() -> TokenUsageSignal:
    """Get the global token usage signal instance."""
    global _signal
    if _signal is None:
        _signal = TokenUsageSignal()
    return _signal


def reset_token_usage_signal() -> None:
    """Reset the global token usage signal instance (useful for testing)."""
    global _signal
    _signal = None
