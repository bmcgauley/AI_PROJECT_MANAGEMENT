"""
FastAPI web interface for AI Project Management System.
Provides visualization of agent interactions and web development project management.
"""

from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request
import json
import asyncio
from typing import Dict, List, Optional

from src.agents.chat_coordinator import ChatCoordinatorAgent
from src.agents.project_manager import ProjectManagerAgent

app = FastAPI(title="AI Project Management System")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # In production, replace with specific origins
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")
templates = Jinja2Templates(directory="src/web/templates")

# Store active connections and agent states
active_connections: List[WebSocket] = []
agent_states: Dict[str, str] = {}

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the main dashboard."""
    return templates.TemplateResponse(
        "index.html", 
        {"request": request}
    )

@app.get("/api/status")
async def get_system_status():
    """Get the current status of all system components."""
    try:
        return {
            "status": "operational",
            "components": {
                "web_interface": "running",
                "ollama": "running",
                "mcp_servers": {
                    "filesystem": "running",
                    "context7": "running",
                    "atlassian": "running"
                },
                "agents": agent_states
            }
        }
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections for real-time agent updates."""
    await websocket.accept()
    active_connections.append(websocket)
    try:
        while True:
            data = await websocket.receive_text()
            # Process incoming messages from the web client
            message = json.loads(data)
            if message["type"] == "request":
                # Forward request to chat coordinator
                response = await process_agent_request(message["content"], websocket.app.state.chat_coordinator)
                await websocket.send_json({
                    "type": "response",
                    "content": response
                })
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        active_connections.remove(websocket)

@app.post("/api/project")
async def create_project(request: Request):
    """Create a new web development project."""
    data = await request.json()
    try:
        if not request.app.state.project_manager:
            raise HTTPException(status_code=500, detail="Project manager agent not initialized")
            
        # Use ProjectManagerAgent to create project structure
        response = await request.app.state.project_manager.process({
            "text": f"Create new web development project: {data['name']}",
            "details": data
        })
        return {"status": "success", "response": response}
    except Exception as e:
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agents")
async def get_agents(request: Request):
    """Get status of all agents."""
    if not request.app.state.chat_coordinator:
        return {"agents": []}
        
    agents = request.app.state.chat_coordinator.agents
    return {
        "agents": [
            {
                "name": agent.name,
                "status": agent_states.get(agent.name, "idle"),
                "description": agent.description
            }
            for name, agent in agents.items()
            if name != "request_parser"
        ]
    }

async def process_agent_request(request: str, chat_coordinator: ChatCoordinatorAgent) -> dict:
    """Process a request through the chat coordinator."""
    try:
        if not chat_coordinator:
            return {
                "status": "error",
                "error": "Chat coordinator not initialized"
            }
            
        response = await chat_coordinator.process({"text": request})
        return response
    except Exception as e:
        return {
            "status": "error",
            "error": str(e)
        }

async def broadcast_agent_update(agent_name: str, status: str):
    """Broadcast agent status updates to all connected clients."""
    agent_states[agent_name] = status
    for connection in active_connections:
        await connection.send_json({
            "type": "agent_update",
            "agent": agent_name,
            "status": status
        })