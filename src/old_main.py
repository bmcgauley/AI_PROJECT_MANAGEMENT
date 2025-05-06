#!/usr/bin/env python3
"""
Main entry point for the AI Project Management System.
Sets up the agents and starts the web interface with FastAPI.
"""

import os
import sys
import asyncio
import logging
import json
import time
import subprocess
import traceback
import threading
import uvicorn
import requests
import httpx
from typing import Dict, List, Optional, Union, Any

# Force stdout to be unbuffered for immediate display of output
sys.stdout.reconfigure(write_through=True)  # Python 3.7+

from dotenv import load_dotenv
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain_ollama import OllamaLLM

# Fix import path for running directly
if __name__ == "__main__":
    # Ensure the package root is in the path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# Now import agents and other modules
from src.agents.chat_coordinator import ChatCoordinatorAgent
from src.agents.project_manager import ProjectManagerAgent
from src.agents.research_specialist import ResearchSpecialistAgent
from src.agents.business_analyst import BusinessAnalystAgent
from src.agents.code_developer import CodeDeveloperAgent
from src.agents.code_reviewer import CodeReviewerAgent
from src.agents.report_drafter import ReportDrafterAgent
from src.agents.report_reviewer import ReportReviewerAgent
from src.agents.report_publisher import ReportPublisherAgent
from src.web.app import app, setup_app

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ai_pm_system")

class MCPClient:
    """Handles communication with MCP servers defined in a config file."""
    
    def __init__(self, config_path: str):
        """Initialize the MCP client with configuration."""
        self.config_path = config_path
        self.config = self._load_config()
        self.active_servers = {}
        self.locks = {}  # Locks for each server to ensure thread-safety
        
    def _load_config(self) -> dict:
        """Load MCP configuration from file."""
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading MCP config: {e}")
            return {}
            
    async def start_servers(self):
        """Start all configured MCP servers."""
        if not self.config.get("mcpServers"):
            logger.warning("No MCP servers configured")
            return
            
        for name, config in self.config["mcpServers"].items():
            if config.get("disabled"):
                continue
                
            try:
                # Create lock for this server
                self.locks[name] = asyncio.Lock()
                
                # Start server process
                env = os.environ.copy()
                if config.get("env"):
                    env.update(config["env"])
                
                process = await asyncio.create_subprocess_exec(
                    config["command"],
                    *config["args"],
                    env=env,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE
                )
                self.active_servers[name] = process
                logger.info(f"Started MCP server: {name}")
            except Exception as e:
                logger.error(f"Error starting MCP server {name}: {e}")
                
    async def stop_servers(self):
        """Stop all running MCP servers."""
        for name, process in self.active_servers.items():
            try:
                process.terminate()
                await process.wait()
                logger.info(f"Stopped MCP server: {name}")
            except Exception as e:
                logger.error(f"Error stopping MCP server {name}: {e}")
                
    async def use_tool(self, server_name: str, tool_name: str, arguments: dict) -> dict:
        """Use a tool provided by an MCP server."""
        if server_name not in self.active_servers:
            return {"status": "error", "error": {"message": f"Server {server_name} not found"}}
            
        try:
            request = {
                "jsonrpc": "2.0",
                "method": tool_name,
                "params": arguments,
                "id": str(time.time())
            }
            
            process = self.active_servers[server_name]
            
            # Use lock to ensure only one request at a time to each server
            async with self.locks[server_name]:
                # Write request to stdin
                request_json = json.dumps(request)
                process.stdin.write(f"{request_json}\n".encode())
                await process.stdin.drain()
                
                # Read response from stdout
                response_line = await process.stdout.readline()
                if not response_line:
                    # Try to get error from stderr
                    error = await process.stderr.readline()
                    return {"status": "error", "error": {"message": f"Empty response from server. Error: {error.decode()}"}}
                
                try:
                    response = json.loads(response_line.decode())
                    return response
                except json.JSONDecodeError:
                    return {"status": "error", "error": {"message": f"Invalid JSON response: {response_line.decode()}"}}
        except Exception as e:
            logger.error(f"Error using tool {tool_name} on server {server_name}: {e}")
            return {"status": "error", "error": {"message": str(e), "traceback": traceback.format_exc()}}

# Global variables to store agent instances
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

async def initialize_agents():
    """Initialize all agents with the LLM and MCP client."""
    global chat_coordinator, project_manager
    
    # Load environment variables
    load_dotenv(dotenv_path=os.path.join(project_root, 'src', '.env'))
    
    # Get Ollama config
    model_name = os.getenv("OLLAMA_MODEL", "tinyllama")
    
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
    
    # Initialize Ollama LLM
    print("Initializing Ollama LLM...")
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
    print("Initializing MCP client...")
    mcp_client = MCPClient(config_path="mcp.json")
    await mcp_client.start_servers()
    
    # Initialize all specialized agents
    print("Creating specialized agents...")
    project_manager = ProjectManagerAgent(llm=llm, mcp_client=mcp_client)
    research_specialist = ResearchSpecialistAgent(llm=llm, mcp_client=mcp_client)
    business_analyst = BusinessAnalystAgent(llm=llm, mcp_client=mcp_client)
    code_developer = CodeDeveloperAgent(llm=llm, mcp_client=mcp_client)
    code_reviewer = CodeReviewerAgent(llm=llm, mcp_client=mcp_client)
    report_drafter = ReportDrafterAgent(llm=llm, mcp_client=mcp_client)
    report_reviewer = ReportReviewerAgent(llm=llm, mcp_client=mcp_client)
    report_publisher = ReportPublisherAgent(llm=llm, mcp_client=mcp_client)
    
    # Initialize chat coordinator
    print("Creating chat coordinator...")
    chat_coordinator = ChatCoordinatorAgent(llm=llm, mcp_client=mcp_client)
    
    # Register all agents with coordinator
    print("Registering specialized agents with coordinator...")
    chat_coordinator.add_agent("project_manager", project_manager)
    chat_coordinator.add_agent("research_specialist", research_specialist)
    chat_coordinator.add_agent("business_analyst", business_analyst)
    chat_coordinator.add_agent("code_developer", code_developer)
    chat_coordinator.add_agent("code_reviewer", code_reviewer)
    chat_coordinator.add_agent("report_drafter", report_drafter)
    chat_coordinator.add_agent("report_reviewer", report_reviewer)
    chat_coordinator.add_agent("report_publisher", report_publisher)
    
    print("\nAll agents initialized successfully!")
    return chat_coordinator, project_manager

async def main():
    """
    Main asynchronous entry point for the application.
    Sets up the agents and starts the FastAPI web interface.
    """
    print("\n======================================================")
    print("   AI Project Management System - Multi-Agent Edition   ")
    print("======================================================\n")
    
    # Initialize agents
    await initialize_agents()
    
    # Set up FastAPI app with agents and event handlers
    setup_app(app, chat_coordinator=chat_coordinator, project_manager=project_manager)
    print("Web interface initialized with agent event handlers")
    
    # Start FastAPI server
    config = uvicorn.Config(
        app=app,
        host="0.0.0.0",
        port=8000,
        log_level="info"
    )
    server = uvicorn.Server(config)
    await server.serve()

if __name__ == "__main__":
    asyncio.run(main())
