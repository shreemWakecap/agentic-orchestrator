"""
Chat Routes for the Portal.

Provides WebSocket-based chat interface for interacting with
codebase knowledge and triggering actions.
"""
import asyncio
import json
import logging
import uuid
from typing import Optional

from fastapi import APIRouter, WebSocket, WebSocketDisconnect, Depends, HTTPException, Request
from fastapi.responses import HTMLResponse
from pydantic import BaseModel

from portal.services.chat_service import ChatService, get_chat_service

logger = logging.getLogger(__name__)
router = APIRouter(prefix="/chat", tags=["chat"])


# --- Request/Response Models ---

class CreateSessionRequest(BaseModel):
    """Request to create a new chat session."""
    context: Optional[str] = None  # Optional initial context


class CreateSessionResponse(BaseModel):
    """Response with new session ID."""
    session_id: str
    message: str


class ChatMessageRequest(BaseModel):
    """Request to send a chat message."""
    message: str
    session_id: Optional[str] = None


class ChatMessageResponse(BaseModel):
    """Response from chat."""
    response: str
    action_taken: Optional[str] = None
    data: Optional[dict] = None


# --- WebSocket Connection Manager ---

class ConnectionManager:
    """Manages WebSocket connections for chat."""

    def __init__(self):
        self.active_connections: dict[str, WebSocket] = {}

    async def connect(self, websocket: WebSocket, session_id: str):
        await websocket.accept()
        self.active_connections[session_id] = websocket

    def disconnect(self, session_id: str):
        if session_id in self.active_connections:
            del self.active_connections[session_id]

    async def send_message(self, session_id: str, message: dict):
        if session_id in self.active_connections:
            await self.active_connections[session_id].send_json(message)

    async def broadcast(self, message: dict):
        for connection in self.active_connections.values():
            await connection.send_json(message)


manager = ConnectionManager()


# --- REST Endpoints ---

@router.post("/session", response_model=CreateSessionResponse)
async def create_session(
    request: CreateSessionRequest,
    chat_service: ChatService = Depends(get_chat_service)
) -> CreateSessionResponse:
    """Create a new chat session."""
    session_id = str(uuid.uuid4())
    chat_service.create_session(session_id, context=request.context)

    return CreateSessionResponse(
        session_id=session_id,
        message="Session created successfully"
    )


@router.post("/message", response_model=ChatMessageResponse)
async def send_message(
    request: ChatMessageRequest,
    chat_service: ChatService = Depends(get_chat_service)
) -> ChatMessageResponse:
    """Send a message and get a response (REST endpoint for non-WebSocket clients)."""
    session_id = request.session_id or str(uuid.uuid4())

    if not chat_service.has_session(session_id):
        chat_service.create_session(session_id)

    result = await chat_service.handle_message(request.message, session_id)

    return ChatMessageResponse(
        response=result.get("response", ""),
        action_taken=result.get("action"),
        data=result.get("data")
    )


# --- WebSocket Endpoints ---

@router.websocket("/ws/{session_id}")
async def websocket_endpoint(
    websocket: WebSocket,
    session_id: str,
    chat_service: ChatService = Depends(get_chat_service)
):
    """WebSocket endpoint for real-time chat."""
    await manager.connect(websocket, session_id)

    # Create session if not exists
    if not chat_service.has_session(session_id):
        chat_service.create_session(session_id)

    # Send welcome message
    await manager.send_message(session_id, {
        "type": "system",
        "message": "Connected to chat. How can I help you?",
        "session_id": session_id
    })

    try:
        while True:
            # Receive message from client
            data = await websocket.receive_json()
            message = data.get("message", "")

            if not message:
                continue

            # Send typing indicator
            await manager.send_message(session_id, {
                "type": "status",
                "status": "thinking"
            })

            try:
                # Process message
                result = await chat_service.handle_message(message, session_id)

                # Send response
                await manager.send_message(session_id, {
                    "type": "response",
                    "message": result.get("response", ""),
                    "action": result.get("action"),
                    "data": result.get("data")
                })
            except Exception as e:
                logger.error(f"Error processing message: {e}")
                await manager.send_message(session_id, {
                    "type": "error",
                    "message": f"Error processing message: {str(e)}"
                })

    except WebSocketDisconnect:
        manager.disconnect(session_id)
        chat_service.end_session(session_id)


# --- Page Route ---

@router.get("", response_class=HTMLResponse)
async def chat_page(request: Request):
    """Render the chat page."""
    from portal.routes.pages import templates

    session_id = str(uuid.uuid4())

    return templates.TemplateResponse(
        "chat.html",
        {
            "request": request,
            "page_title": "Chat",
            "session_id": session_id
        }
    )
