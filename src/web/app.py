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
import logging
import json
import asyncio
from typing import Dict, List, Optional, Callable, Any

# Updated import paths to use agents from the old directory
from src.agents.chat_coordinator import ChatCoordinatorAgent
from src.agents.modern_project_manager import ProjectManagerAgent
from src.request_processor import RequestProcessor
from src.web.ws_handlers import WebSocketManager

# Set up logging
logger = logging.getLogger("ai_pm_system.web.app")

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

# WebSocket manager will replace direct connection management
ws_manager = None

@app.get("/", response_class=HTMLResponse)
async def home(request: Request):
    """Render the main dashboard."""
    return templates.TemplateResponse(
        "index.html", 
        {"request": request}
    )

@app.get("/api/status")
async def get_system_status(request: Request):
    """Get the current status of all system components."""
    try:
        agent_states = {}
        if hasattr(request.app.state, 'request_processor') and request.app.state.request_processor:
            agent_states = request.app.state.request_processor.agent_states
            
        system_initialized = False
        if hasattr(request.app.state, 'request_processor') and request.app.state.request_processor:
            system_initialized = request.app.state.request_processor.initialized
            
        return {
            "status": "operational" if system_initialized else "initializing",
            "components": {
                "web_interface": "running",
                "ollama": "running",
                "mcp_servers": {
                    "filesystem": "running",
                    "context7": "running",
                    "atlassian": "running"
                },
                "agents": agent_states,
                "system_initialized": system_initialized
            }
        }
    except Exception as e:
        logger.error(f"Error getting system status: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections for real-time agent updates."""
    if not app.state.ws_manager:
        await websocket.accept()
        await websocket.send_json({
            "type": "error",
            "message": "WebSocket manager not initialized"
        })
        await websocket.close()
        return
    
    # Use the WebSocketManager to handle the connection
    await app.state.ws_manager.handle_connection(websocket)

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
        logger.error(f"Error creating project: {str(e)}")
        raise HTTPException(status_code=500, detail=str(e))

@app.get("/api/agents")
async def get_agents(request: Request):
    """Get status of all agents."""
    agent_states = {}
    agent_descriptions = {}
    
    if hasattr(request.app.state, 'request_processor') and request.app.state.request_processor:
        agent_states = request.app.state.request_processor.agent_states
        
        # Get agent descriptions if coordinator is initialized
        if hasattr(request.app.state.request_processor, 'coordinator') and request.app.state.request_processor.coordinator:
            available_agents = request.app.state.request_processor.coordinator.get_available_agents()
            agent_descriptions = {
                name: desc for name, desc in [
                    line.split(": ", 1) for line in available_agents.split("\n") if ": " in line
                ]
            }
    
    # Format response
    agents = []
    for name, status in agent_states.items():
        agents.append({
            "name": name,
            "status": status,
            "description": agent_descriptions.get(name, "")
        })
    
    return {"agents": agents, "initialized": hasattr(request.app.state, 'request_processor') and request.app.state.request_processor.initialized}

# Setup function to initialize the app with agents
def setup_app(app_instance: FastAPI, request_processor: RequestProcessor):
    """
    Initialize FastAPI app with the request processor and WebSocket manager.
    
    Args:
        app_instance: The FastAPI application instance
        request_processor: The request processor that handles agent communication
    """
    app_instance.state.request_processor = request_processor
    
    # Create and configure WebSocketManager
    global ws_manager
    ws_manager = WebSocketManager(request_processor)
    app_instance.state.ws_manager = ws_manager
    
    # Connect the WebSocketManager to the RequestProcessor
    request_processor.set_ws_manager(ws_manager)
    
    # Set event handler for the request processor
    request_processor.event_handler = ws_manager.handle_agent_event
    
    # For backward compatibility
    if hasattr(request_processor, 'coordinator') and request_processor.coordinator:
        app_instance.state.chat_coordinator = request_processor.coordinator
        
    logger.info("Application setup complete with WebSocketManager and RequestProcessor")