"""
Agent definitions and factory functions for creating specialized agents.
Both legacy and modern Pydantic/LangGraph agents are supported.
"""

from typing import Dict, Any, Optional
from langchain_core.language_models import BaseLLM
import importlib
from pydantic import BaseModel, Field

# Modern agent imports
from src.agents.modern_project_manager import ProjectManagerAgent as ModernProjectManagerAgent
from src.agents.modern_base_agent import ModernBaseAgent

# Try to import LangGraph components
try:
    from langgraph.graph import StateGraph, END
    from langgraph.graph.message import MessageGraph
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    print("Warning: LangGraph not available. Modern agent capabilities will be limited.")

def create_all_agents(llm: BaseLLM, mcp_client: Optional[Any] = None) -> Dict[str, Any]:
    """
    Create all specialized agents for the system.
    
    Args:
        llm: The language model to use for the agents
        mcp_client: Optional MCP client for external tool integration
    
    Returns:
        Dict mapping agent names to their instances
    """
    # Create specialized agents
    agents = {
        "research specialist": ResearchSpecialistAgent(
            llm=llm,
            mcp_client=mcp_client
        ),
        "business analyst": BusinessAnalystAgent(
            llm=llm,
            mcp_client=mcp_client
        ),
        "code developer": CodeDeveloperAgent(
            llm=llm,
            mcp_client=mcp_client
        ),
        "code reviewer": CodeReviewerAgent(
            llm=llm,
            mcp_client=mcp_client
        ),
        "report drafter": ReportDrafterAgent(
            llm=llm,
            mcp_client=mcp_client
        ),
        "report reviewer": ReportReviewerAgent(
            llm=llm,
            mcp_client=mcp_client
        ),
        "report publisher": ReportPublisherAgent(
            llm=llm,
            mcp_client=mcp_client
        )
    }
    
    return agents

def create_modern_agents(llm: BaseLLM, mcp_client: Optional[Any] = None) -> Dict[str, Any]:
    """
    Create all modern agents using the Pydantic and LangGraph architecture.
    
    Args:
        llm: The language model to use for the agents
        mcp_client: Optional MCP client for external tool integration
    
    Returns:
        Dict mapping agent names to their instances
    """
    # Create modern agents with Pydantic and LangGraph
    agents = {
        "project_manager": ModernProjectManagerAgent(
            llm=llm,
            mcp_client=mcp_client
        )
    }
    
    # Add more modern agents as they are implemented
    
    return agents

class AgentState(BaseModel):
    """
    Base state model for LangGraph agent workflows.
    
    This class defines the basic structure of state that flows through 
    the LangGraph state machine. Extend this class for specific agent needs.
    """
    messages: list = Field(default_factory=list, description="Message history")
    current_agent: str = Field(default="", description="Currently active agent")
    task: str = Field(default="", description="Current task being worked on")
    status: str = Field(default="pending", description="Status of the workflow")
    
    class Config:
        arbitrary_types_allowed = True

def create_agent_workflow(agents: Dict[str, ModernBaseAgent], initial_state: Optional[BaseModel] = None) -> Any:
    """
    Create a LangGraph workflow connecting multiple agents.
    
    Args:
        agents: Dictionary of agent instances
        initial_state: Optional initial state for the workflow
        
    Returns:
        A LangGraph workflow or None if LangGraph is not available
    """
    if not LANGGRAPH_AVAILABLE:
        return None
        
    if initial_state is None:
        initial_state = AgentState()
    
    # Create a basic workflow graph connecting the agents
    workflow = StateGraph(AgentState)
    
    # Add nodes for each agent
    for name, agent in agents.items():
        workflow.add_node(name, agent.process)
    
    # Add an end node
    workflow.add_node("end", lambda state: state)
    
    # Set up conditional routing between agents
    # This is a simplified example - should be customized based on your workflow needs
    for name in agents:
        workflow.add_edge(name, "end")
        
    workflow.set_entry_point("project_manager")
    
    return workflow.compile()