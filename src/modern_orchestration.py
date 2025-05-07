"""
Orchestration module for the AI Project Management System.
Manages agent creation and communication using the modern agent structure.
"""

import os
import sys
import platform
import logging
from typing import Dict, Any, List, Optional, Union
from langchain_core.language_models.base import BaseLanguageModel

# Apply SQLite patch based on platform
if platform.system() == "Windows":
    # On Windows, use Windows-specific patch
    from .sqlite_patch_windows import apply_sqlite_patch
else:
    # On Linux/Container, use standard patch
    from .sqlite_patch import apply_sqlite_patch

# Apply SQLite patch early
apply_sqlite_patch()

from .models.agent_models import AgentConfig, AgentResponse, AgentType, ProjectSummary
from .agents.modern_base_agent import ModernBaseAgent
from .agents.modern_project_manager import ProjectManagerAgent, ModernProjectManager
from .utils.llm_wrapper import CompatibleOllamaLLM  # Import our custom wrapper
# Import other specialized agents as needed

# Configure logging
logging.basicConfig(level=os.environ.get("LOG_LEVEL", "INFO"))
logger = logging.getLogger("modern_orchestration")

class ModernOrchestrator:
    """
    Orchestrator class for managing modern agents and their interactions.
    Uses Pydantic models and LangGraph for reliable agent execution.
    """
    
    def __init__(self, llm: BaseLanguageModel, mcp_client: Optional[Any] = None):
        """
        Initialize the orchestrator.
        
        Args:
            llm: Language model to use for agents
            mcp_client: Optional MCP client for tool access
        """
        self.llm = llm
        self.mcp_client = mcp_client
        self.agents: Dict[str, ModernBaseAgent] = {}
        self.logger = logger
        self.project_manager = None  # Will be initialized in _initialize_agents
        
        # Initialize agents
        try:
            self._initialize_agents()
        except Exception as e:
            self.logger.error(f"Error initializing agents: {str(e)}")
            # Continue with an empty agents dictionary rather than failing completely
            self.logger.warning("Continuing with minimal orchestrator functionality")
    
    def register_agent(self, agent_name: str, agent: ModernBaseAgent) -> None:
        """
        Register an agent with the orchestrator.
        
        Args:
            agent_name: Name to register the agent under
            agent: The agent instance to register
        """
        self.logger.info(f"Registering agent: {agent_name}")
        self.agents[agent_name] = agent
        
        # If this is a project manager agent, also set the project_manager reference
        if agent_name == "project_manager" and self.project_manager is None:
            self.logger.info("Setting project_manager reference")
            if hasattr(agent, 'get_manager_interface'):
                self.project_manager = agent.get_manager_interface()
            else:
                self.project_manager = agent
    
    def _initialize_agents(self) -> None:
        """Initialize all required agents."""
        try:
            # Create Project Manager agent
            self.logger.info("Creating Project Manager agent...")
            project_manager_agent = ProjectManagerAgent(
                llm=self.llm,
                mcp_client=self.mcp_client
            )
            self.agents["project_manager"] = project_manager_agent
            
            # Initialize the ModernProjectManager with the agent
            self.logger.info("Initializing ModernProjectManager...")
            self.project_manager = ModernProjectManager(agent=project_manager_agent)
            
            self.logger.info("Project Manager agent created successfully")
            
            # Add more agents as needed using the modern structure
            # You'll need to create modern versions of these agents
            # self.agents["researcher"] = ModernResearchAgent(...)
            # self.agents["code_developer"] = ModernCodeDeveloperAgent(...)
            
            self.logger.info(f"Initialized {len(self.agents)} modern agents")
        except Exception as e:
            self.logger.error(f"Error in _initialize_agents: {str(e)}")
            import traceback
            self.logger.error(f"Detailed initialization error traceback: {traceback.format_exc()}")
            raise
    
    async def process_request(self, request: str, agent_name: str = "project_manager") -> AgentResponse:
        """
        Process a request using the specified agent.
        
        Args:
            request: The request to process
            agent_name: Name of the agent to use (default: project_manager)
            
        Returns:
            The agent's response
        """
        if agent_name not in self.agents:
            error_msg = f"Agent '{agent_name}' not found"
            self.logger.error(error_msg)
            return AgentResponse(
                agent_name="orchestrator",
                content="",
                error=error_msg
            )
        
        agent = self.agents[agent_name]
        self.logger.info(f"Processing request with {agent_name} agent")
        
        try:
            response = await agent.process(request)
            return response
        except Exception as e:
            error_msg = f"Error processing request with {agent_name}: {str(e)}"
            self.logger.error(error_msg)
            return AgentResponse(
                agent_name=agent_name,
                content="",
                error=error_msg
            )
    
    def get_agent(self, agent_name: str) -> Optional[ModernBaseAgent]:
        """
        Get an agent by name.
        
        Args:
            agent_name: Name of the agent to get
            
        Returns:
            The agent if found, None otherwise
        """
        return self.agents.get(agent_name)
    
    def list_agents(self) -> List[str]:
        """
        List all available agents.
        
        Returns:
            List of agent names
        """
        return list(self.agents.keys())
    
    def _initialize_llm(self) -> CompatibleOllamaLLM:
        """Initialize the LLM with appropriate configuration."""
        model_name = os.environ.get("OLLAMA_MODEL", "tinyllama")
        base_url = os.environ.get("OLLAMA_BASE_URL", "http://localhost:11434")
        
        logger.info(f"Initializing LLM with model: {model_name}, base_url: {base_url}")
        
        return CompatibleOllamaLLM(
            model=model_name,
            base_url=base_url,
            temperature=0.5,
            repeat_penalty=1.2,
            top_p=0.9
        )
    
    async def process_action_request(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a user action request and return a response.
        
        Args:
            request: A dictionary containing the request details
            
        Returns:
            A dictionary containing the response details
        """
        logger.info(f"Processing action request: {request.get('action', 'unknown')}")
        
        # Process based on action type
        action = request.get("action", "")
        
        if action == "create_project":
            return await self._handle_create_project(request)
        elif action == "update_project":
            return await self._handle_update_project(request)
        elif action == "analyze_project":
            return await self._handle_analyze_project(request)
        else:
            logger.warning(f"Unknown action requested: {action}")
            return {
                "success": False,
                "error": f"Unknown action: {action}",
                "action": action
            }
    
    async def _handle_create_project(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle project creation requests."""
        logger.info("Creating a new project")
        
        project_details = request.get("details", {})
        response = await self.project_manager.create_project(project_details)
        
        return {
            "success": True,
            "action": "create_project",
            "project": response
        }
    
    async def _handle_update_project(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle project update requests."""
        logger.info("Updating existing project")
        
        project_id = request.get("project_id")
        updates = request.get("updates", {})
        
        if not project_id:
            return {"success": False, "error": "Missing project_id for update"}
        
        response = await self.project_manager.update_project(project_id, updates)
        
        return {
            "success": True,
            "action": "update_project",
            "project": response
        }
    
    async def _handle_analyze_project(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Handle project analysis requests."""
        logger.info("Analyzing project")
        
        project_id = request.get("project_id")
        analysis_type = request.get("analysis_type", "general")
        
        if not project_id:
            return {"success": False, "error": "Missing project_id for analysis"}
        
        response = await self.project_manager.analyze_project(project_id, analysis_type)
        
        return {
            "success": True,
            "action": "analyze_project",
            "analysis": response
        }
