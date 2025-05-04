#!/usr/bin/env python3
"""
Crew.ai implementation of the AI Project Management System.
Sets up the agents and tasks using Crew.ai for better multi-agent orchestration.
"""

# Configure SQLite and CrewAI patches
import sys
import os
from unittest.mock import MagicMock

# Configure pysqlite3 binary
__import__('pysqlite3')
sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

# Create a complete mock ChromaDB structure
class ChromaDBMock:
    def __init__(self):
        self.api = MagicMock()
        self.api.types = MagicMock()
        self.api.types.Documents = MagicMock()
        self.api.types.EmbeddingFunction = MagicMock()
        self.api.types.Embeddings = MagicMock()
        self.api.types.validate_embedding_function = MagicMock(return_value=True)
        
        self.config = MagicMock()
        self.config.Settings = MagicMock()
        
        self.errors = MagicMock()
        self.errors.ChromaError = type('ChromaError', (Exception,), {})
        self.errors.NoDatapointsError = type('NoDatapointsError', (self.errors.ChromaError,), {})
        self.errors.InvalidDimensionException = type('InvalidDimensionException', (self.errors.ChromaError,), {})
        
        # Add any other attributes that might be accessed
        self.Client = MagicMock()
        self.PersistentClient = MagicMock()
        self.Collection = MagicMock()
        self.Documents = self.api.types.Documents
        self.EmbeddingFunction = self.api.types.EmbeddingFunction
        self.Embeddings = self.api.types.Embeddings

chromadb_mock = ChromaDBMock()

# Install the mock
sys.modules['chromadb'] = chromadb_mock
sys.modules['chromadb.api'] = chromadb_mock.api
sys.modules['chromadb.api.types'] = chromadb_mock.api.types
sys.modules['chromadb.config'] = chromadb_mock.config
sys.modules['chromadb.errors'] = chromadb_mock.errors

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
from crewai import Agent, Task, Crew, Process
from langchain_ollama import OllamaLLM

# Fix import path for running directly
if __name__ == "__main__":
    # Ensure the package root is in the path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '.'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

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

# Import FastAPI components
from fastapi import FastAPI, WebSocket, HTTPException
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.responses import HTMLResponse
from fastapi.middleware.cors import CORSMiddleware
from fastapi import Request

# Create FastAPI app
app = FastAPI(title="AI Project Management System")

# Enable CORS
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
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

# Global variables to store agent instances
agents_dict = {}
agent_descriptions = {}
crew_instance = None
mcp_client = None

# Handler for agent events
async def handle_agent_event(event_type: str, **kwargs):
    """Handle agent events and broadcast to all connected clients."""
    # Update agent state if applicable
    if event_type == "agent_handoff" and "to_agent" in kwargs:
        agent_states[kwargs["to_agent"]] = "active"
    
    # Create WebSocket message
    message = {
        "type": event_type,
        **kwargs
    }
    
    # Broadcast to all connected clients
    for connection in active_connections:
        await connection.send_json(message)
    
    # If this is the end of a request, update agent states
    if event_type == "request_complete":
        # Reset all agent states to idle
        for agent in agent_states:
            agent_states[agent] = "idle"
        
        # Broadcast agent status updates
        for agent, status in agent_states.items():
            for connection in active_connections:
                await connection.send_json({
                    "type": "agent_update",
                    "agent": agent,
                    "status": status
                })

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
                # Generate a unique request ID
                request_id = message.get("request_id", f"req_{len(active_connections)}_{id(message)}")
                
                # Send request_start event
                await websocket.send_json({
                    "type": "request_start",
                    "request_id": request_id
                })
                
                # Forward request to crew processor
                response = await process_request(
                    message["content"], 
                    request_id=request_id
                )
                
                # Send final response
                await websocket.send_json({
                    "type": "response",
                    "content": response
                })
    except Exception as e:
        print(f"WebSocket error: {e}")
    finally:
        active_connections.remove(websocket)

@app.get("/api/agents")
async def get_agents():
    """Get status of all agents."""
    if not agents_dict:
        return {"agents": []}
        
    return {
        "agents": [
            {
                "name": agent_name,
                "status": agent_states.get(agent_name, "idle"),
                "description": agent_descriptions.get(agent_name, "")
            }
            for agent_name in agent_states
        ]
    }

def check_ollama_availability(base_url="http://127.0.0.1:11434"):
    """Check if Ollama is available at the given base URL."""
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        response.raise_for_status()
        print(f"✓ Ollama is available at {base_url}")
        return True, base_url
    except (requests.RequestException, httpx.HTTPError) as e:
        print(f"✗ Ollama not available at {base_url}: {e}")
        return False, base_url

async def initialize_crew():
    """Initialize the Crew.ai setup with agents."""
    global agents_dict, agent_descriptions, crew_instance, mcp_client
    
    # Load environment variables
    load_dotenv()
    
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
        base_url=base_url,
        model=f"ollama/{model_name}",  # Using ollama/ prefix to specify the provider
        temperature=0.7,
        request_timeout=120.0,
        model_kwargs={
            "system": "You are a helpful AI assistant skilled in project management and software development."
        }
    )
    
    # Initialize MCP client
    print("Initializing MCP client...")
    mcp_client = MCPClient(config_path="mcp.json")
    await mcp_client.start_servers()
    
    # Create specialized agents with crew.ai's Agent class
    print("Creating specialized agents...")
    
    # Project Manager Agent
    project_manager = Agent(
        role="Project Manager",
        goal="Manage projects efficiently and coordinate team efforts",
        backstory="""You are an experienced project manager with PMBOK/PMP certification, 
        proficient in project planning, task management, and requirements analysis. 
        You coordinate team efforts and create project documentation and reports.""",
        verbose=True,
        allow_delegation=True,
        llm=llm
    )
    
    # Research Specialist Agent
    research_specialist = Agent(
        role="Research Specialist",
        goal="Find and analyze information from various sources to support project decisions",
        backstory="""You are a research expert who can find and analyze information from 
        various sources, including the web. You provide comprehensive research reports 
        and can analyze trends, competitors, and industry developments.""",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
    
    # Business Analyst Agent
    business_analyst = Agent(
        role="Business Analyst",
        goal="Analyze requirements and create specifications based on project needs",
        backstory="""You are a skilled business analyst who excels at gathering and 
        analyzing requirements, creating specifications, and helping translate business needs 
        into technical solutions.""",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
    
    # Code Developer Agent
    code_developer = Agent(
        role="Code Developer",
        goal="Write efficient, clean code based on specifications",
        backstory="""You are a software developer with expertise in multiple programming languages 
        and frameworks. You write clean, efficient code following best practices and can implement 
        features based on specifications.""",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
    
    # Code Reviewer Agent
    code_reviewer = Agent(
        role="Code Reviewer",
        goal="Review code for quality, security, and best practices",
        backstory="""You are a senior developer specialized in code review. You evaluate code for 
        quality, security issues, and adherence to best practices, providing constructive feedback 
        for improvements.""",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
    
    # Report Drafter Agent
    report_drafter = Agent(
        role="Report Drafter",
        goal="Create clear, comprehensive reports and documentation",
        backstory="""You are skilled at creating various types of reports and documentation for projects.
        You can structure information clearly and create professional documents that effectively 
        communicate project details.""",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
    
    # Report Reviewer Agent
    report_reviewer = Agent(
        role="Report Reviewer",
        goal="Review reports for accuracy, clarity, and completeness",
        backstory="""You are a detail-oriented report reviewer with expertise in technical writing and 
        documentation standards. You ensure reports are accurate, clear, and complete before publication.""",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
    
    # Report Publisher Agent
    report_publisher = Agent(
        role="Report Publisher",
        goal="Format and distribute reports to stakeholders",
        backstory="""You are responsible for the final formatting, packaging, and distribution of 
        reports to various stakeholders. You ensure reports meet organizational standards and reach 
        the intended audience.""",
        verbose=True,
        allow_delegation=False,
        llm=llm
    )
    
    # Store agents in dictionary for later use
    agents_dict = {
        "Project Manager": project_manager,
        "Research Specialist": research_specialist,
        "Business Analyst": business_analyst,
        "Code Developer": code_developer,
        "Code Reviewer": code_reviewer,
        "Report Drafter": report_drafter,
        "Report Reviewer": report_reviewer,
        "Report Publisher": report_publisher
    }
    
    # Store agent descriptions for the API
    agent_descriptions = {
        "Project Manager": "Manages projects efficiently and coordinates team efforts",
        "Research Specialist": "Finds and analyzes information from various sources to support project decisions",
        "Business Analyst": "Analyzes requirements and creates specifications based on project needs",
        "Code Developer": "Writes efficient, clean code based on specifications",
        "Code Reviewer": "Reviews code for quality, security, and best practices",
        "Report Drafter": "Creates clear, comprehensive reports and documentation",
        "Report Reviewer": "Reviews reports for accuracy, clarity, and completeness",
        "Report Publisher": "Formats and distributes reports to stakeholders"
    }
    
    # Update agent states for UI
    for agent_name in agents_dict.keys():
        agent_states[agent_name] = "idle"
    
    # Create Crew instance with default task
    general_task = Task(
        description="Handle general project management inquiries and coordinate responses",
        expected_output="A complete and helpful response to the user's inquiry",
        agent=project_manager
    )
    
    crew_instance = Crew(
        agents=[agent for agent in agents_dict.values()],
        tasks=[general_task],  # Default task
        verbose=True,  # Using boolean instead of integer
        process=Process.sequential,  # Tasks executed in sequence
        manager_llm=llm,  # Using the same LLM for the manager
    )

    print("\nAll agents initialized successfully!")
    return agents_dict, crew_instance

# Function to process requests using Crew.ai
async def process_request(user_request: str, request_id: str = None) -> dict:
    """Process a user request through the Crew.ai system."""
    global agents_dict, crew_instance
    
    if not agents_dict or not crew_instance:
        return {
            "status": "error",
            "processed_by": "System",
            "response": "The agent system is not initialized yet. Please try again later.",
            "request_id": request_id
        }
    
    # Emit event for request start
    await handle_agent_event("workflow_step", 
        message="Analyzing request to determine required agents and tasks",
        request_id=request_id
    )
    
    # Determine which task to use based on the user's request
    task = None
    primary_agent = "Project Manager"
    
    # Simplified request categorization
    if "jira" in user_request.lower() or "task" in user_request.lower():
        primary_agent = "Project Manager"
        task = Task(
            description=f"Check Jira for tasks related to: '{user_request}'",
            expected_output="A summary of relevant Jira tasks and their status",
            agent=agents_dict["Project Manager"]
        )
    elif "research" in user_request.lower() or "find" in user_request.lower():
        primary_agent = "Research Specialist"
        task = Task(
            description=f"Research the following topic: '{user_request}'",
            expected_output="A comprehensive research report with relevant information",
            agent=agents_dict["Research Specialist"]
        )
    elif "code" in user_request.lower() or "develop" in user_request.lower():
        primary_agent = "Code Developer"
        task = Task(
            description=f"Develop code for: '{user_request}'",
            expected_output="Working code that meets the requirements",
            agent=agents_dict["Code Developer"]
        )
    else:
        primary_agent = "Project Manager"
        task = Task(
            description=f"Handle this user request: '{user_request}'",
            expected_output="A helpful response that addresses the user's query",
            agent=agents_dict["Project Manager"]
        )
    
    try:
        # Update agent states for UI
        agent_states[primary_agent] = "active"
        
        # Emit event for agent thinking
        await handle_agent_event("agent_thinking", 
            agent=primary_agent,
            thinking=f"Working on: '{user_request}'",
            request_id=request_id
        )
        
        # Create a crew for this specific request
        request_crew = Crew(
            agents=[agents_dict[primary_agent]],
            tasks=[task],
            verbose=True,  # Using boolean instead of integer
            process=Process.sequential,
        )
        
        # Execute the crew
        result = request_crew.kickoff()
        
        # Emit event for request completion
        await handle_agent_event("request_complete", 
            message="Request processing completed",
            request_id=request_id
        )
        
        return {
            "status": "success",
            "processed_by": primary_agent,
            "response": result,
            "request_id": request_id
        }
    except Exception as e:
        error_msg = f"Error processing request: {str(e)}"
        print(error_msg)
        await handle_agent_event("request_error", 
            message=error_msg,
            request_id=request_id
        )
        return {
            "status": "error",
            "processed_by": "System",
            "response": f"I apologize, but there was an error processing your request: {str(e)}",
            "error": str(e),
            "request_id": request_id
        }

async def main():
    """
    Main asynchronous entry point for the application.
    Sets up the agents and starts the FastAPI web interface.
    """
    print("\n======================================================")
    print("   AI Project Management System - Crew.ai Edition   ")
    print("======================================================\n")
    
    # Initialize agents with Crew.ai
    await initialize_crew()
    
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