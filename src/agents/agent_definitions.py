"""
Agent definitions and factory functions for creating specialized agents.
This simplified implementation follows the consolidated pattern.
"""

from typing import Dict, Any, Optional
from langchain_core.language_models import BaseLLM
import importlib
from pydantic import BaseModel, Field

# Import the consolidated agent implementation
from src.agents.project_manager import ProjectManagerAgent
from src.agents.base_agent import BaseAgent

# Try to import LangGraph components
try:
    from langgraph.graph import StateGraph, END
    from langgraph.graph.message import MessageGraph
    LANGGRAPH_AVAILABLE = True
except ImportError:
    LANGGRAPH_AVAILABLE = False
    print("Warning: LangGraph not available. Modern agent capabilities will be limited.")

def create_agents(llm: BaseLLM, mcp_client: Optional[Any] = None) -> Dict[str, BaseAgent]:
    """
    Create all agents for the system using the consolidated implementation.
    
    Args:
        llm: The language model to use for the agents
        mcp_client: Optional MCP client for external tool integration
    
    Returns:
        Dict mapping agent names to their instances
    """
    # Create specialized agents with the consolidated implementation
    agents = {
        "project_manager": ProjectManagerAgent(
            llm=llm,
            mcp_client=mcp_client
        )
    }
    
    # Add other specialized agents as they are implemented
    # (all following the consolidated pattern)
    
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

def create_agent_workflow(agents: Dict[str, BaseAgent], initial_state: Optional[BaseModel] = None) -> Any:
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
        # Assuming all agents have a process method with a similar signature
        if hasattr(agent, 'process'):
            workflow.add_node(name, agent.process)
    
    # Add an end node
    workflow.add_node("end", lambda state: state)
    
    # Set up conditional routing between agents
    # This is a simplified example - should be customized based on your workflow needs
    for name in agents:
        workflow.add_edge(name, "end")
        
    # Set entry point to the project manager by default
    if "project_manager" in agents:
        workflow.set_entry_point("project_manager")
    else:
        # Use the first agent as entry point if project manager is not available
        workflow.set_entry_point(next(iter(agents.keys())))
    
    return workflow.compile()