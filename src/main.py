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
import time
import uvicorn
from typing import Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket, Request
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from fastapi.websockets import WebSocketDisconnect

# Apply SQLite patches immediately
from src.sqlite_patch import apply_sqlite_patch
apply_sqlite_patch()

from src.config import setup_environment, get_mcp_config_path, get_web_config
from src.mcp_client import MCPClient
from src.orchestration import AgentOrchestrator
from src.request_processor import RequestProcessor
from src.web.ws_handlers import WebSocketManager

# Import the app from web/app.py
from src.web.app import app, setup_app

# Set up logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ai_pm_system.main")

# Force stdout to be unbuffered for immediate display of output
sys.stdout.reconfigure(write_through=True)  # Python 3.7+

# Global variables
mcp_client = None
orchestrator = None
request_processor = None
shutdown_event = asyncio.Event()

async def startup():
    """Initialize system on startup."""
    global mcp_client, orchestrator, request_processor
    
    try:
        print("\n======================================================")
        print("   AI Project Management System - Modular Edition      ")
        print("======================================================\n")
        
        # Set up environment (SQLite patches, etc.)
        setup_environment()
        logger.info("Environment setup complete")
        
        # Initialize MCP client
        mcp_config_path = get_mcp_config_path()
        mcp_client = MCPClient(mcp_config_path)
        await mcp_client.start_servers()
        logger.info("MCP servers started")
        
        # Initialize agent orchestrator with proper sequence
        try:
            # Create orchestrator with MCP client
            orchestrator = AgentOrchestrator(mcp_client=mcp_client)
            
            # Create request processor now
            request_processor = RequestProcessor(orchestrator, mcp_client)
            
            # Setup the app with request processor (this creates WebSocketManager internally)
            setup_app(app, request_processor)
            
            # Initialize the system - this creates and sets up all agents including ChatCoordinatorAgent
            system_components = await orchestrator.initialize_system(
                event_callback=app.state.ws_manager.handle_agent_event
            )
            logger.info("Agent system initialized successfully")
            
            if not orchestrator.chat_coordinator:
                raise RuntimeError("ChatCoordinatorAgent initialization failed")
            
            # For backward compatibility, store project_manager in app state
            if 'project manager' in orchestrator.agents_dict:  # Changed from base_agents to agents_dict
                app.state.project_manager = orchestrator.agents_dict['project manager']
            
            # Initialize the request processor with the WebSocket manager's event handler
            await request_processor.initialize(event_handler=app.state.ws_manager.handle_agent_event)
            
            if not request_processor.initialized:
                raise RuntimeError("RequestProcessor failed to initialize")
            
            # Signal that the system is initialized
            app.state.ws_manager.set_initialized(True)
            
            # Broadcast system ready message
            await app.state.ws_manager.broadcast(
                "system_initialized", 
                message="AI Project Management System initialized successfully",
                agent_count=len(request_processor.agent_states)
            )
                
            logger.info("AI Project Management System initialized successfully")
            
        except Exception as init_error:
            logger.error(f"Critical error during agent initialization: {str(init_error)}")
            if hasattr(app.state, 'ws_manager'):
                await app.state.ws_manager.broadcast(
                    "system_error", 
                    message=f"System initialization failed: {str(init_error)}"
                )
            raise  # Re-raise to trigger the outer exception handler
            
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        # Gracefully shut down in case of initialization error
        await shutdown()

async def shutdown():
    """Gracefully shut down the system."""
    global mcp_client, orchestrator, request_processor
    
    logger.info("Initiating graceful shutdown...")
    
    if hasattr(app.state, 'ws_manager'):
        await app.state.ws_manager.broadcast("system_status", status="shutting_down")
        await app.state.ws_manager.close_all()
    
    if request_processor:
        await request_processor.cleanup()
    
    if mcp_client:
        await mcp_client.stop_servers()
    
    shutdown_event.set()
    logger.info("Shutdown complete")

def handle_sigterm(*args):
    """Handle SIGTERM signal."""
    asyncio.create_task(shutdown())

# Register signal handlers
signal.signal(signal.SIGTERM, handle_sigterm)

# Define the lifespan context manager to replace the deprecated on_event
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    This replaces the deprecated on_event handlers.
    """
    # Startup: Initialize system
    await startup()
    yield
    # Shutdown: Cleanup resources
    await shutdown()

# Set the lifespan handler for the app
# This replaces the @app.on_event("startup") decorator
app.router.lifespan_context = lifespan

if __name__ == "__main__":
    try:
        web_config = get_web_config()
        config = uvicorn.Config(
            app=app,
            host=web_config["host"],
            port=web_config["port"],
            log_level=web_config["log_level"].lower()
        )
        server = uvicorn.Server(config)
        asyncio.run(server.serve())
    except KeyboardInterrupt:
        print("\nShutting down...")
        asyncio.run(shutdown())
