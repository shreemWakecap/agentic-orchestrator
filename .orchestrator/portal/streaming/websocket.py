"""
WebSocket - Real-time bidirectional communication for plan status updates.

Provides WebSocket connections for:
- Plan status changes
- Build progress updates
- Dashboard stats refresh notifications
- Stuck plan alerts
"""
import asyncio
import json
import logging
from datetime import datetime
from typing import Dict, Set, Optional, Any
from dataclasses import dataclass, field
from collections import defaultdict

from fastapi import WebSocket, WebSocketDisconnect
from starlette.websockets import WebSocketState

logger = logging.getLogger(__name__)


@dataclass
class WSConnection:
    """Represents a WebSocket connection."""
    websocket: WebSocket
    client_id: str
    connected_at: datetime = field(default_factory=datetime.utcnow)
    subscriptions: Set[str] = field(default_factory=set)
    last_ping: datetime = field(default_factory=datetime.utcnow)


class WebSocketManager:
    """
    Manages WebSocket connections for real-time updates.

    Supports channel-based subscriptions:
    - 'dashboard': Dashboard stats updates
    - 'plan:{plan_id}': Individual plan status updates
    - 'builds': Active builds status updates
    - 'stuck': Stuck plans alerts

    Usage:
        manager = WebSocketManager()

        # In FastAPI route:
        @app.websocket("/ws")
        async def websocket_endpoint(websocket: WebSocket):
            await manager.connect(websocket)
            try:
                while True:
                    data = await websocket.receive_json()
                    await manager.handle_message(websocket, data)
            except WebSocketDisconnect:
                manager.disconnect(websocket)

        # Broadcasting:
        await manager.broadcast("dashboard", {"type": "stats", "data": {...}})
    """

    def __init__(self, ping_interval: float = 30.0):
        """
        Initialize WebSocket manager.

        Args:
            ping_interval: Seconds between ping messages to keep connection alive
        """
        self.ping_interval = ping_interval

        # Connection tracking
        self._connections: Dict[str, WSConnection] = {}  # client_id -> connection
        self._ws_to_client: Dict[WebSocket, str] = {}    # websocket -> client_id
        self._connection_counter = 0

        # Channel subscriptions: channel -> set of client_ids
        self._channels: Dict[str, Set[str]] = defaultdict(set)

        # Ping task
        self._ping_task: Optional[asyncio.Task] = None

    @property
    def connection_count(self) -> int:
        """Get total number of active connections."""
        return len(self._connections)

    async def start(self):
        """Start the WebSocket manager (ping loop)."""
        if self._ping_task is None:
            self._ping_task = asyncio.create_task(self._ping_loop())
            logger.info("WebSocket manager started")

    async def stop(self):
        """Stop the WebSocket manager."""
        if self._ping_task:
            self._ping_task.cancel()
            try:
                await self._ping_task
            except asyncio.CancelledError:
                pass
            self._ping_task = None

        # Close all connections
        for conn in list(self._connections.values()):
            await self._close_connection(conn.websocket)

        logger.info("WebSocket manager stopped")

    # =========================================================================
    # Connection Management
    # =========================================================================

    def _generate_client_id(self) -> str:
        """Generate unique client ID."""
        self._connection_counter += 1
        return f"ws_{self._connection_counter}_{datetime.utcnow().timestamp():.0f}"

    async def connect(self, websocket: WebSocket) -> str:
        """
        Accept a new WebSocket connection.

        Args:
            websocket: The WebSocket to accept

        Returns:
            Client ID for this connection
        """
        await websocket.accept()

        client_id = self._generate_client_id()
        conn = WSConnection(
            websocket=websocket,
            client_id=client_id,
        )

        self._connections[client_id] = conn
        self._ws_to_client[websocket] = client_id

        # Send welcome message with client ID
        await self._send_to_client(client_id, {
            "type": "connected",
            "client_id": client_id,
            "timestamp": datetime.utcnow().isoformat(),
        })

        logger.debug(f"WebSocket connected: {client_id}")
        return client_id

    def disconnect(self, websocket: WebSocket):
        """
        Handle WebSocket disconnection.

        Args:
            websocket: The disconnected WebSocket
        """
        client_id = self._ws_to_client.get(websocket)
        if not client_id:
            return

        conn = self._connections.get(client_id)
        if conn:
            # Remove from all subscribed channels
            for channel in list(conn.subscriptions):
                self._channels[channel].discard(client_id)
                if not self._channels[channel]:
                    del self._channels[channel]

            del self._connections[client_id]

        del self._ws_to_client[websocket]
        logger.debug(f"WebSocket disconnected: {client_id}")

    async def _close_connection(self, websocket: WebSocket):
        """Close a WebSocket connection gracefully."""
        try:
            if websocket.client_state == WebSocketState.CONNECTED:
                await websocket.close()
        except Exception as e:
            logger.debug(f"Error closing WebSocket: {e}")
        finally:
            self.disconnect(websocket)

    # =========================================================================
    # Message Handling
    # =========================================================================

    async def handle_message(self, websocket: WebSocket, data: Dict[str, Any]):
        """
        Handle incoming WebSocket message.

        Supported message types:
        - subscribe: Subscribe to a channel
        - unsubscribe: Unsubscribe from a channel
        - ping: Respond with pong

        Args:
            websocket: The WebSocket that sent the message
            data: Parsed JSON message data
        """
        client_id = self._ws_to_client.get(websocket)
        if not client_id:
            return

        msg_type = data.get("type")

        if msg_type == "subscribe":
            channel = data.get("channel")
            if channel:
                await self._subscribe(client_id, channel)

        elif msg_type == "unsubscribe":
            channel = data.get("channel")
            if channel:
                await self._unsubscribe(client_id, channel)

        elif msg_type == "ping":
            await self._send_to_client(client_id, {
                "type": "pong",
                "timestamp": datetime.utcnow().isoformat(),
            })
            # Update last ping time
            conn = self._connections.get(client_id)
            if conn:
                conn.last_ping = datetime.utcnow()

        elif msg_type == "get_status":
            # Request current status for a plan
            plan_id = data.get("plan_id")
            if plan_id:
                await self._send_plan_status(client_id, plan_id)

    async def _subscribe(self, client_id: str, channel: str):
        """Subscribe a client to a channel."""
        conn = self._connections.get(client_id)
        if not conn:
            return

        conn.subscriptions.add(channel)
        self._channels[channel].add(client_id)

        await self._send_to_client(client_id, {
            "type": "subscribed",
            "channel": channel,
            "timestamp": datetime.utcnow().isoformat(),
        })

        logger.debug(f"Client {client_id} subscribed to {channel}")

    async def _unsubscribe(self, client_id: str, channel: str):
        """Unsubscribe a client from a channel."""
        conn = self._connections.get(client_id)
        if not conn:
            return

        conn.subscriptions.discard(channel)
        self._channels[channel].discard(client_id)

        if not self._channels[channel]:
            del self._channels[channel]

        await self._send_to_client(client_id, {
            "type": "unsubscribed",
            "channel": channel,
            "timestamp": datetime.utcnow().isoformat(),
        })

        logger.debug(f"Client {client_id} unsubscribed from {channel}")

    async def _send_plan_status(self, client_id: str, plan_id: str):
        """Send current plan status to a client."""
        from db import get_plan_repository, get_build_state_repository

        plan_repo = get_plan_repository()
        build_state_repo = get_build_state_repository()

        plan = plan_repo.get_by_id(plan_id)
        if not plan:
            await self._send_to_client(client_id, {
                "type": "error",
                "message": f"Plan {plan_id} not found",
            })
            return

        build_state = build_state_repo.get(plan_id)

        status_data = {
            "type": "plan_status",
            "plan_id": plan_id,
            "status": plan.get("status", "pending"),
            "timestamp": datetime.utcnow().isoformat(),
        }

        if build_state:
            status_data.update({
                "current_step": build_state.get("current_step"),
                "progress": self._calculate_progress(build_state),
                "completed_steps": build_state.get("completed_steps", []),
                "failed_steps": build_state.get("failed_steps", []),
                "last_error": build_state.get("last_error"),
                "updated_at": build_state.get("updated_at"),
            })

        await self._send_to_client(client_id, status_data)

    def _calculate_progress(self, build_state: Dict) -> int:
        """Calculate build progress percentage."""
        total = build_state.get("total_steps", 0)
        if total == 0:
            return 0
        completed = len(build_state.get("completed_steps", []))
        return int((completed / total) * 100)

    # =========================================================================
    # Broadcasting
    # =========================================================================

    async def broadcast(self, channel: str, data: Dict[str, Any]):
        """
        Broadcast a message to all subscribers of a channel.

        Args:
            channel: Channel name to broadcast to
            data: Message data to send
        """
        subscribers = self._channels.get(channel, set())
        if not subscribers:
            return

        # Add channel and timestamp to message
        message = {
            **data,
            "channel": channel,
            "timestamp": datetime.utcnow().isoformat(),
        }

        # Send to all subscribers
        disconnected = []
        for client_id in subscribers:
            success = await self._send_to_client(client_id, message)
            if not success:
                disconnected.append(client_id)

        # Clean up disconnected clients
        for client_id in disconnected:
            conn = self._connections.get(client_id)
            if conn:
                await self._close_connection(conn.websocket)

    async def broadcast_to_all(self, data: Dict[str, Any]):
        """
        Broadcast a message to all connected clients.

        Args:
            data: Message data to send
        """
        message = {
            **data,
            "timestamp": datetime.utcnow().isoformat(),
        }

        disconnected = []
        for client_id in list(self._connections.keys()):
            success = await self._send_to_client(client_id, message)
            if not success:
                disconnected.append(client_id)

        for client_id in disconnected:
            conn = self._connections.get(client_id)
            if conn:
                await self._close_connection(conn.websocket)

    async def _send_to_client(self, client_id: str, data: Dict[str, Any]) -> bool:
        """
        Send a message to a specific client.

        Args:
            client_id: Target client ID
            data: Message data to send

        Returns:
            True if sent successfully, False otherwise
        """
        conn = self._connections.get(client_id)
        if not conn:
            return False

        try:
            if conn.websocket.client_state == WebSocketState.CONNECTED:
                await conn.websocket.send_json(data)
                return True
        except Exception as e:
            logger.debug(f"Error sending to {client_id}: {e}")

        return False

    # =========================================================================
    # Ping/Pong for Connection Health
    # =========================================================================

    async def _ping_loop(self):
        """Send periodic pings to keep connections alive."""
        while True:
            try:
                await asyncio.sleep(self.ping_interval)
                await self._send_pings()
            except asyncio.CancelledError:
                break

    async def _send_pings(self):
        """Send ping to all connections."""
        ping_data = {
            "type": "ping",
            "timestamp": datetime.utcnow().isoformat(),
        }

        disconnected = []
        for client_id in list(self._connections.keys()):
            success = await self._send_to_client(client_id, ping_data)
            if not success:
                disconnected.append(client_id)

        for client_id in disconnected:
            conn = self._connections.get(client_id)
            if conn:
                await self._close_connection(conn.websocket)

    # =========================================================================
    # Plan Status Broadcasting Helpers
    # =========================================================================

    async def broadcast_plan_status(
        self,
        plan_id: str,
        status: str,
        **extra_data
    ):
        """
        Broadcast plan status update.

        Args:
            plan_id: Plan ID
            status: New status
            **extra_data: Additional data to include
        """
        await self.broadcast(f"plan:{plan_id}", {
            "type": "plan_status",
            "plan_id": plan_id,
            "status": status,
            **extra_data,
        })

        # Also broadcast to general builds channel if status is building/in_progress
        if status in ("building", "in_progress"):
            await self.broadcast("builds", {
                "type": "build_update",
                "plan_id": plan_id,
                "status": status,
                **extra_data,
            })

    async def broadcast_build_progress(
        self,
        plan_id: str,
        progress: int,
        current_step: Optional[str] = None,
        **extra_data
    ):
        """
        Broadcast build progress update.

        Args:
            plan_id: Plan ID
            progress: Progress percentage (0-100)
            current_step: Current step name
            **extra_data: Additional data to include
        """
        data = {
            "type": "build_progress",
            "plan_id": plan_id,
            "progress": progress,
            **extra_data,
        }
        if current_step:
            data["current_step"] = current_step

        await self.broadcast(f"plan:{plan_id}", data)
        await self.broadcast("builds", data)

    async def broadcast_dashboard_stats(self, counts: Dict[str, int]):
        """
        Broadcast dashboard stats update.

        Args:
            counts: Plan counts by status
        """
        await self.broadcast("dashboard", {
            "type": "stats",
            "counts": counts,
        })

    async def broadcast_stuck_alert(
        self,
        plan_id: str,
        minutes_stale: int,
        **extra_data
    ):
        """
        Broadcast stuck plan alert.

        Args:
            plan_id: Plan ID
            minutes_stale: Minutes since last update
            **extra_data: Additional data to include
        """
        await self.broadcast("stuck", {
            "type": "stuck_alert",
            "plan_id": plan_id,
            "minutes_stale": minutes_stale,
            **extra_data,
        })


# Singleton instance
_manager: Optional[WebSocketManager] = None


def get_websocket_manager() -> WebSocketManager:
    """Get the global WebSocket manager instance."""
    global _manager
    if _manager is None:
        _manager = WebSocketManager()
    return _manager


async def init_websocket_manager() -> WebSocketManager:
    """Initialize and start the global WebSocket manager."""
    global _manager
    _manager = WebSocketManager()
    await _manager.start()
    return _manager


async def shutdown_websocket_manager():
    """Shutdown the global WebSocket manager."""
    global _manager
    if _manager:
        await _manager.stop()
        _manager = None
