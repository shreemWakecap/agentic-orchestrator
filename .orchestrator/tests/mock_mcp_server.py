"""Mock MCP server for testing streaming mode."""

import asyncio
import json
import uuid
from datetime import datetime
from fastapi import FastAPI, Request
from fastapi.responses import StreamingResponse
import uvicorn

app = FastAPI(title="Mock MCP Server")

# Store for active sessions
sessions = {}


@app.post("/")
async def handle_request(request: Request):
    """Handle MCP protocol requests."""
    body = await request.json()
    method = body.get("method", "")
    msg_id = body.get("id", str(uuid.uuid4()))

    if method == "initialize":
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "result": {
                "protocolVersion": "1.0",
                "serverInfo": {"name": "mock-mcp-server", "version": "1.0.0"},
                "capabilities": {"streaming": True}
            }
        }

    elif method == "agent/run":
        # Return a streaming response
        params = body.get("params", {})
        agent_name = params.get("agent", "unknown")
        message = params.get("message", "")

        async def generate_events():
            # Simulate agent processing with streaming events
            steps = [
                ("progress", {"step": "analyzing", "progress": 10}),
                ("token", {"text": f"Processing request for {agent_name}...\n"}),
                ("progress", {"step": "planning", "progress": 30}),
                ("token", {"text": "Analyzing requirements...\n"}),
                ("tool_use", {"tool": "read_file", "result": {"path": "README.md"}}),
                ("progress", {"step": "generating", "progress": 60}),
                ("token", {"text": "Generating implementation plan...\n"}),
                ("token", {"text": f"\n## Plan for: {message[:50]}...\n\n"}),
                ("token", {"text": "1. Setup project structure\n"}),
                ("token", {"text": "2. Implement core functionality\n"}),
                ("token", {"text": "3. Add tests\n"}),
                ("token", {"text": "4. Documentation\n\n"}),
                ("progress", {"step": "finalizing", "progress": 90}),
                ("token", {"text": "Plan complete!\n"}),
                ("complete", {"response": "Plan generated successfully", "tokens_used": 1234}),
            ]

            for event_type, data in steps:
                event = {
                    "jsonrpc": "2.0",
                    "method": "agent/event",
                    "params": {
                        "type": event_type,
                        "data": data,
                        "timestamp": datetime.now().isoformat()
                    }
                }
                yield f"data: {json.dumps(event)}\n\n"
                await asyncio.sleep(0.3)  # Simulate processing time

        return StreamingResponse(
            generate_events(),
            media_type="text/event-stream",
            headers={"Cache-Control": "no-cache", "Connection": "keep-alive"}
        )

    elif method == "shutdown":
        return {"jsonrpc": "2.0", "id": msg_id, "result": {"status": "ok"}}

    else:
        return {
            "jsonrpc": "2.0",
            "id": msg_id,
            "error": {"code": -32601, "message": f"Method not found: {method}"}
        }


@app.get("/health")
async def health():
    return {"status": "ok"}


def run_server(host: str = "127.0.0.1", port: int = 3000):
    """Run the mock MCP server."""
    print(f"Starting Mock MCP Server on http://{host}:{port}")
    uvicorn.run(app, host=host, port=port, log_level="info")


if __name__ == "__main__":
    run_server()
