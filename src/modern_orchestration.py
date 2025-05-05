"""
Orchestration module for the AI Project Management System.
Manages agent creation and communication using the modern agent structure.
"""

from typing import Dict, Any, List, Optional, Union
import logging
from langchain_core.language_models.base import BaseLanguageModel

from .models.agent_models import AgentConfig, AgentResponse, AgentType
from .agents.modern_base_agent import ModernBaseAgent
from .agents.modern_project_manager import ProjectManagerAgent
# Import other specialized agents as needed

# Configure logging
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
        
        # Initialize agents
        self._initialize_agents()
    
    def _initialize_agents(self) -> None:
        """Initialize all required agents."""
        # Create Project Manager agent
        self.agents["project_manager"] = ProjectManagerAgent(
            llm=self.llm,
            mcp_client=self.mcp_client
        )
        
        # Add more agents as needed using the modern structure
        # You'll need to create modern versions of these agents
        # self.agents["researcher"] = ModernResearchAgent(...)
        # self.agents["code_developer"] = ModernCodeDeveloperAgent(...)
        
        self.logger.info(f"Initialized {len(self.agents)} modern agents")
    
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
