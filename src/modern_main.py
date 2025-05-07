#!/usr/bin/env python3
"""
Modern main entry point for the AI Project Management System.
Uses Pydantic models and LangGraph for agent orchestration.
"""

import asyncio
import logging
import os
import signal
import sys
import time
from typing import Dict, Any
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn

# Apply SQLite patches immediately
from src.sqlite_patch import apply_sqlite_patch
apply_sqlite_patch()

from src.config import setup_environment, get_mcp_config_path, get_web_config
from src.mcp_client import MCPClient
from src.modern_orchestration import ModernOrchestrator
from src.utils.llm_wrapper import CompatibleOllamaLLM  # Import our custom wrapper
from src.web.modern_ws_handlers import ModernWebSocketManager
from src.web.modern_app import app, setup_modern_app

# Set up logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ai_pm_system.modern_main")

# Force stdout to be unbuffered for immediate display of output
sys.stdout.reconfigure(write_through=True)

# Global variables
mcp_client = None
orchestrator = None
shutdown_event = asyncio.Event()

async def startup():
    """Initialize system on startup using the modern agent architecture."""
    global mcp_client, orchestrator
    
    try:
        print("\n======================================================")
        print("   AI Project Management System - Modern Architecture  ")
        print("======================================================\n")
        
        # Detect Docker environment
        if os.path.exists("/.dockerenv"):
            os.environ["RUNNING_IN_DOCKER"] = "true"
            logger.info("Detected Docker environment from /.dockerenv file")

        # Set up environment (SQLite patches, etc.)
        setup_environment()
        logger.info("Environment setup complete")
        
        # Initialize the LLM
        model_name = os.environ.get("OLLAMA_MODEL", "tinyllama")
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        
        logger.info(f"Initializing LLM: {model_name} at {base_url}")
        llm = CompatibleOllamaLLM(model=model_name, base_url=base_url)
        
        # Initialize MCP client
        mcp_config_path = get_mcp_config_path()
        mcp_client = MCPClient(mcp_config_path)
        await mcp_client.start_servers()
        logger.info("MCP servers started")
        
        # Initialize modern orchestrator
        try:
            # Create modern orchestrator with MCP client and LLM
            logger.info("Creating ModernOrchestrator instance...")
            orchestrator = ModernOrchestrator(llm=llm, mcp_client=mcp_client)
            logger.info("ModernOrchestrator created successfully")
            
            # Set up the modern WebSocket manager
            logger.info("Creating ModernWebSocketManager...")
            ws_manager = ModernWebSocketManager()
            
            # Setup the app with the WebSocket manager and register the orchestrator
            logger.info("Setting up the FastAPI application...")
            setup_modern_app(app, ws_manager, orchestrator)
            
            # Ready to receive connections
            logger.info("Modern agent architecture initialized successfully")
            
            # Set system as initialized
            app.state.modern_ws_manager.set_initialized(True)
            
            # Broadcast system ready message
            await app.state.modern_ws_manager.broadcast(
                "system_initialized", 
                message="AI Project Management System with modern architecture initialized successfully",
                agent_count=len(orchestrator.agents)
            )
                
            logger.info("Modern AI Project Management System initialized successfully")
            
        except Exception as init_error:
            logger.error(f"Critical error during modern agent initialization: {str(init_error)}")
            import traceback
            logger.error(f"Detailed error traceback: {traceback.format_exc()}")
            
            # Even if we had an error, ensure we have a baseline orchestrator
            if orchestrator is None:
                logger.info("Creating fallback orchestrator...")
                # Create a minimal orchestrator without initializing agents
                from src.web.api_routes import set_orchestrator
                orchestrator = ModernOrchestrator(llm=llm, mcp_client=mcp_client)
                set_orchestrator(orchestrator)
                logger.info("Fallback orchestrator set to prevent 503 errors")
            
            if hasattr(app.state, 'modern_ws_manager'):
                await app.state.modern_ws_manager.broadcast(
                    "system_error", 
                    message=f"System initialization failed: {str(init_error)}"
                )
            raise
            
    except Exception as e:
        logger.error(f"Error during startup: {e}")
        await shutdown()

async def shutdown():
    """Gracefully shut down the system."""
    global mcp_client, orchestrator
    
    logger.info("Initiating graceful shutdown of modern architecture...")
    
    if hasattr(app.state, 'modern_ws_manager'):
        await app.state.modern_ws_manager.broadcast("system_status", status="shutting_down")
        await app.state.modern_ws_manager.close_all()
    
    if mcp_client:
        await mcp_client.stop_servers()
    
    shutdown_event.set()
    logger.info("Shutdown complete")

def handle_sigterm(*args):
    """Handle SIGTERM signal."""
    asyncio.create_task(shutdown())

# Register signal handlers
signal.signal(signal.SIGTERM, handle_sigterm)

# Define the lifespan context manager
@asynccontextmanager
async def lifespan(app_instance: FastAPI):
    """
    Lifespan context manager for FastAPI application.
    """
    # Startup: Initialize system
    await startup()
    yield
    # Shutdown: Cleanup resources
    await shutdown()

# Set the lifespan handler for the app
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
