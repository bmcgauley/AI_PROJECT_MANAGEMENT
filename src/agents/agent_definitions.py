"""
Agent definitions and factory functions for creating specialized agents.
Both legacy and modern Pydantic/LangGraph agents are supported.
"""

from typing import Dict, Any, Optional
from langchain_core.language_models import BaseLLM

# Legacy agent imports
from src.agents.business_analyst import BusinessAnalystAgent
from src.agents.code_developer import CodeDeveloperAgent
from src.agents.code_reviewer import CodeReviewerAgent
from src.agents.research_specialist import ResearchSpecialistAgent
from src.agents.report_drafter import ReportDrafterAgent
from src.agents.report_reviewer import ReportReviewerAgent
from src.agents.report_publisher import ReportPublisherAgent

# Modern agent imports
from src.agents.modern_project_manager import ProjectManagerAgent as ModernProjectManagerAgent

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