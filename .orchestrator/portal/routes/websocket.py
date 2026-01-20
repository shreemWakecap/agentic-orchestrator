"""WebSocket routes for real-time updates."""
import logging
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from portal.streaming.websocket import get_websocket_manager

logger = logging.getLogger(__name__)

router = APIRouter(tags=["websocket"])


@router.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint for real-time updates.

    Clients can subscribe to channels:
    - "dashboard": Dashboard stats updates
    - "plan:{plan_id}": Individual plan status updates
    - "builds": Active builds status updates
    - "stuck": Stuck plans alerts

    Message format:
    - Subscribe: {"type": "subscribe", "channel": "dashboard"}
    - Unsubscribe: {"type": "unsubscribe", "channel": "dashboard"}
    - Ping: {"type": "ping"}
    - Get status: {"type": "get_status", "plan_id": "..."}
    """
    manager = get_websocket_manager()

    try:
        client_id = await manager.connect(websocket)
        logger.info(f"WebSocket client connected: {client_id}")

        while True:
            try:
                data = await websocket.receive_json()
                await manager.handle_message(websocket, data)
            except ValueError as e:
                # Invalid JSON
                await websocket.send_json({
                    "type": "error",
                    "message": f"Invalid JSON: {str(e)}"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket client disconnected")

    except Exception as e:
        logger.error(f"WebSocket error: {e}")
        manager.disconnect(websocket)


@router.websocket("/ws/plans/{plan_id}")
async def plan_websocket_endpoint(websocket: WebSocket, plan_id: str):
    """
    WebSocket endpoint for a specific plan's updates.

    Automatically subscribes to plan:{plan_id} channel.
    """
    manager = get_websocket_manager()

    try:
        client_id = await manager.connect(websocket)
        logger.info(f"WebSocket client {client_id} connected for plan {plan_id}")

        # Auto-subscribe to this plan's channel
        await manager.handle_message(websocket, {
            "type": "subscribe",
            "channel": f"plan:{plan_id}"
        })

        # Also subscribe to builds channel for overall progress
        await manager.handle_message(websocket, {
            "type": "subscribe",
            "channel": "builds"
        })

        while True:
            try:
                data = await websocket.receive_json()
                await manager.handle_message(websocket, data)
            except ValueError as e:
                await websocket.send_json({
                    "type": "error",
                    "message": f"Invalid JSON: {str(e)}"
                })

    except WebSocketDisconnect:
        manager.disconnect(websocket)
        logger.info(f"WebSocket client disconnected from plan {plan_id}")

    except Exception as e:
        logger.error(f"WebSocket error for plan {plan_id}: {e}")
        manager.disconnect(websocket)
