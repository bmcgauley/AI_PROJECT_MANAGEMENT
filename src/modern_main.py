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
import json
import subprocess
import traceback
import threading
import requests
import httpx
from typing import Dict, List, Optional, Union, Any
from datetime import datetime
from contextlib import asynccontextmanager

from fastapi import FastAPI, WebSocket
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
import uvicorn
from dotenv import load_dotenv
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain_ollama import OllamaLLM

# Force stdout to be unbuffered for immediate display of output
sys.stdout.reconfigure(write_through=True)

# Apply SQLite patches immediately
from src.sqlite_patch import apply_sqlite_patch
apply_sqlite_patch()

from src.config import setup_environment, get_mcp_config_path, get_web_config
from src.mcp_client import MCPClient
from src.modern_orchestration import ModernOrchestrator
from src.utils.llm_wrapper import CompatibleOllamaLLM
from src.web.modern_ws_handlers import ModernWebSocketManager
from src.web.modern_app import app, setup_modern_app

# Import available agent classes
from src.agents.modern_base_agent import ModernBaseAgent
from src.agents.modern_project_manager import ProjectManagerAgent, ModernProjectManager
from src.agents.modern_research_specialist import ResearchSpecialistAgent
from src.agents.chat_coordinator import ChatCoordinatorAgent

# Import legacy agent classes (will be migrated to modern versions later)
from src.agents.base_agent import BaseAgent

# Set up logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ai_pm_system.modern_main")

# Global variables
mcp_client = None
orchestrator = None
shutdown_event = asyncio.Event()

# Global references for specialized agents
chat_coordinator = None
project_manager = None

def check_ollama_availability(base_url="http://127.0.0.1:11434"):
    """Check if Ollama is available at the given base URL."""
    try:
        # Try with a shorter timeout for faster feedback
        response = requests.get(f"{base_url}/api/tags", timeout=3)
        response.raise_for_status()
        print(f"✓ Ollama is available at {base_url}")
        return True, base_url
    except (requests.RequestException, httpx.HTTPError) as e:
        print(f"✗ Ollama not available at {base_url}: {e}")
        
        # Try Docker host address if the default fails
        if base_url == "http://127.0.0.1:11434":
            docker_url = "http://host.docker.internal:11434"
            try:
                response = requests.get(f"{docker_url}/api/tags", timeout=3)
                response.raise_for_status()
                print(f"✓ Ollama is available through Docker host at {docker_url}")
                return True, docker_url
            except (requests.RequestException, httpx.HTTPError) as e:
                print(f"✗ Ollama not available through Docker host: {e}")
        
        return False, base_url

async def startup():
    """Initialize system on startup using the modern agent architecture."""
    global mcp_client, orchestrator, chat_coordinator, project_manager
    
    try:
        print("\n======================================================")
        print("   AI Project Management System - Modern Architecture  ")
        print("======================================================\n")
        
        # Load environment variables
        load_dotenv(dotenv_path=os.path.join(os.path.dirname(__file__), '.env'))
        
        # Detect Docker environment
        if os.path.exists("/.dockerenv"):
            os.environ["RUNNING_IN_DOCKER"] = "true"
            logger.info("Detected Docker environment from /.dockerenv file")

        # Set up environment (SQLite patches, etc.)
        setup_environment()
        logger.info("Environment setup complete")
        
        # Initialize the LLM with Ollama availability check
        model_name = os.environ.get("OLLAMA_MODEL", "tinyllama")
        
        # Try different potential Ollama URLs to ensure connectivity
        urls_to_try = [
            "http://127.0.0.1:11434",
            "http://localhost:11434",
            "http://0.0.0.0:11434"
        ]
        
        ollama_available = False
        base_url = urls_to_try[0]
        
        for url in urls_to_try:
            available, current_url = check_ollama_availability(url)
            if available:
                ollama_available = True
                base_url = current_url
                break
        
        if not ollama_available:
            raise RuntimeError("Ollama is not available at any of the checked URLs. Please ensure Ollama is running.")
        
        print(f"Using Ollama model: {model_name}")
        print(f"Ollama API URL: {base_url}")
        
        logger.info(f"Initializing LLM: {model_name} at {base_url}")
        llm = OllamaLLM(
            model=model_name,
            callbacks=[StreamingStdOutCallbackHandler()],
            base_url=base_url,
            temperature=0.7,
            request_timeout=120.0,
            num_retries=3,
            retry_min_seconds=1,
            retry_max_seconds=10,
        )
        
        # Initialize MCP client
        mcp_config_path = get_mcp_config_path()
        mcp_client = MCPClient(mcp_config_path)
        await mcp_client.start_servers()
        logger.info("MCP servers started")
        
        # Initialize modern orchestrator
        try:
            # Create specialized agents
            print("Creating specialized agents...")
            project_manager = ProjectManagerAgent(llm=llm, mcp_client=mcp_client)
            research_specialist = ResearchSpecialistAgent(llm=llm, mcp_client=mcp_client)
            
            # Initialize chat coordinator
            print("Creating chat coordinator...")
            chat_coordinator = ChatCoordinatorAgent(llm=llm, mcp_client=mcp_client)
            
            # Register specialized agents with coordinator
            print("Registering specialized agents with coordinator...")
            chat_coordinator.add_agent("project_manager", project_manager)
            chat_coordinator.add_agent("research_specialist", research_specialist)
            
            # Create modern orchestrator with MCP client and LLM
            logger.info("Creating ModernOrchestrator instance...")
            orchestrator = ModernOrchestrator(llm=llm, mcp_client=mcp_client)
            logger.info("ModernOrchestrator created successfully")
            
            # Register agents with orchestrator
            orchestrator.register_agent("chat_coordinator", chat_coordinator)
            orchestrator.register_agent("project_manager", project_manager)
            orchestrator.register_agent("research_specialist", research_specialist)
            
            # Set up the modern WebSocket manager
            logger.info("Creating ModernWebSocketManager...")
            ws_manager = ModernWebSocketManager()
            
            # Setup the app with the WebSocket manager and register the orchestrator
            logger.info("Setting up the FastAPI application...")
            setup_modern_app(app, ws_manager, orchestrator)
            
            # Ready to receive connections
            logger.info("Modern agent architecture initialized successfully")
            print("\nAll available agents initialized successfully!")
            
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

async def main():
    """
    Main asynchronous entry point for the application.
    Makes it compatible with direct execution through the command line.
    """
    web_config = get_web_config()
    config = uvicorn.Config(
        app=app,
        host=web_config["host"],
        port=web_config["port"],
        log_level=web_config["log_level"].lower()
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        print("\nShutting down...")
        asyncio.run(shutdown())
