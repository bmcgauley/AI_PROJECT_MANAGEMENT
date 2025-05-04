#!/usr/bin/env python3
"""
Main entry point for the AI Project Management System.
Initializes all components and starts the web server.
"""

import asyncio
import logging
import os
import signal
import sys
import uvicorn
from typing import Dict, Any

from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates

# Apply SQLite patches immediately
from src.sqlite_patch import apply_sqlite_patch
apply_sqlite_patch()

from src.config import setup_environment, get_mcp_config_path, get_web_config
from src.mcp_client import MCPClient
from src.orchestration import AgentOrchestrator
from src.request_processor import RequestProcessor
from src.web.ws_handlers import WebSocketManager

# Set up logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ai_pm_system.main")

# Force stdout to be unbuffered for immediate display of output
sys.stdout.reconfigure(write_through=True)  # Python 3.7+

# Global variables
app = FastAPI(title="AI Project Management System")
mcp_client = None
orchestrator = None
request_processor = None
ws_manager = None
shutdown_event = asyncio.Event()

@app.on_event("startup")
async def startup_event():
    """Initialize system on startup."""
    global mcp_client, orchestrator, request_processor, ws_manager
    
    try:
        # Set up environment (SQLite patches, etc.)
        setup_environment()
        logger.info("Environment setup complete")
        
        # Initialize MCP client
        mcp_config_path = get_mcp_config_path()
        mcp_client = MCPClient(mcp_config_path)
        await mcp_client.start_servers()
        logger.info("MCP servers started")
        
        # Initialize agent orchestrator with Crew.ai support
        orchestrator = AgentOrchestrator(mcp_client=mcp_client)
        
        # Create request processor (without initializing yet)
        request_processor = RequestProcessor(orchestrator, mcp_client)
        
        # Initialize WebSocket manager
        ws_manager = WebSocketManager(request_processor)
        
        # Initialize agents and set up ChatCoordinatorAgent
        await orchestrator.initialize_agents(use_crew=True)  # Explicitly enable Crew.ai
        logger.info("Agents initialized with Crew.ai support")
        
        # Now initialize the request processor with the WebSocket manager's event handler
        await request_processor.initialize(event_handler=ws_manager.broadcast_event)
        logger.info("Request processor initialized")
        
        # Update the event handler for ChatCoordinatorAgent if needed
        if orchestrator.chat_coordinator:
            orchestrator.chat_coordinator.set_event_callback(ws_manager.broadcast_event)
            logger.info("Event callback set for ChatCoordinatorAgent")
        
        logger.info("AI Project Management System initialized successfully")
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        # Gracefully shut down in case of initialization error
        await shutdown()

@app.on_event("shutdown")
async def shutdown_event():
    """Clean up on shutdown."""
    await shutdown()

async def shutdown():
    """Perform cleanup operations."""
    global mcp_client
    
    logger.info("Shutting down AI Project Management System")
    
    if mcp_client:
        await mcp_client.stop_servers()
        logger.info("MCP servers stopped")
    
    # Signal the shutdown event
    shutdown_event.set()

# Configure static files and templates
web_config = get_web_config()
app.mount("/static", StaticFiles(directory=web_config["static_dir"]), name="static")
templates = Jinja2Templates(directory=web_config["templates_dir"])

@app.get("/", response_class=HTMLResponse)
async def get_index(request: Request):
    """Serve the main index page."""
    return templates.TemplateResponse("index.html", {"request": request})

@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """Handle WebSocket connections."""
    await ws_manager.handle_connection(websocket)

@app.get("/api/status")
async def get_status():
    """Get the system status."""
    agent_states = {}
    agent_descriptions = {}
    
    if orchestrator:
        agent_states = orchestrator.get_agent_states()
        agent_descriptions = orchestrator.get_agent_descriptions()
        
    active_servers = []
    if mcp_client:
        active_servers = mcp_client.get_active_servers()
    
    return {
        "status": "running" if not shutdown_event.is_set() else "shutting_down",
        "agent_states": agent_states,
        "agent_descriptions": agent_descriptions,
        "active_servers": active_servers
    }

@app.post("/api/request")
async def handle_request(request_data: Dict[str, Any]):
    """Handle a request through the API."""
    user_request = request_data.get("text", "")
    request_id = request_data.get("id")
    
    if not request_processor:
        return {
            "status": "error",
            "message": "System not initialized"
        }
    
    # Process the request
    result = await request_processor.process_request(
        user_request=user_request,
        request_id=request_id
    )
    
    return result

def handle_sigterm(signum, frame):
    """Handle SIGTERM gracefully."""
    logger.info("Received SIGTERM signal, initiating shutdown")
    
    # Create an asyncio task to run the shutdown coroutine
    loop = asyncio.get_event_loop()
    loop.create_task(shutdown())

def run():
    """Run the application."""
    # Set up signal handlers
    signal.signal(signal.SIGTERM, handle_sigterm)
    signal.signal(signal.SIGINT, handle_sigterm)
    
    # Get web configuration
    web_config = get_web_config()
    
    # Start the server
    logger.info(f"Starting web server on {web_config['host']}:{web_config['port']}")
    uvicorn.run(
        "src.main:app",
        host=web_config["host"],
        port=web_config["port"],
        log_level=web_config["log_level"],
        reload=os.getenv("RELOAD", "false").lower() in ["true", "1", "yes"]
    )

if __name__ == "__main__":
    run()
