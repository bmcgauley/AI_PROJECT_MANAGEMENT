"""
Project Manager agent implementation using the modern agent structure with Pydantic and LangGraph.
"""

from typing import Any, Dict, List, Optional, Union
import logging
from datetime import datetime

from langchain_core.tools import Tool
from ..models.agent_models import AgentConfig, AgentType
from .modern_base_agent import ModernBaseAgent

class ProjectManagerAgent(ModernBaseAgent):
    """
    Project Manager agent implementation.
    Specializes in project planning, organization, and management tasks.
    """
    
    def __init__(self, llm: Any, mcp_client: Optional[Any] = None, tools: Optional[List[Tool]] = None):
        """
        Initialize the Project Manager agent.
        
        Args:
            llm: Language model to use
            mcp_client: Optional client for MCP interactions
            tools: Optional list of additional tools
        """
        # Create Jira-related tools
        jira_tools = self._create_jira_tools()
        all_tools = (tools or []) + jira_tools
        
        # Create the configuration for this agent
        config = AgentConfig(
            name="Project Manager",
            description="Specializes in project planning, task management, and resource allocation.",
            agent_type=AgentType.PROJECT_MANAGER,
            available_tools={
                'memory-server': ['create_entities', 'create_relations', 'add_observations', 
                                 'read_graph', 'search_nodes', 'open_nodes'],
                'sequential-thinking': ['sequentialthinking'],
                'atlassian': ['create_jira_issue', 'update_jira_issue', 'search_jira_issues',
                             'create_confluence_page', 'update_confluence_page']
            },
            system_prompt="""You are the Project Manager for the AI Project Management System.
            Your responsibilities include:
            
            1. Planning and organizing projects
            2. Creating and managing tasks in Jira
            3. Tracking project progress and timelines
            4. Resource allocation and risk assessment
            5. Creating and maintaining project documentation
            
            Be proactive, organized, and detail-oriented in your approach.
            When making decisions, consider project constraints, priorities, and dependencies.
            """
        )
        
        # Initialize the base agent
        super().__init__(llm=llm, config=config, tools=all_tools, mcp_client=mcp_client)
    
    def _create_jira_tools(self) -> List[Tool]:
        """
        Create tools for Jira integration.
        
        Returns:
            List of LangChain tools for Jira integration
        """
        tools = []
        
        # Create Jira issue tool
        tools.append(
            Tool(
                name="create_jira_issue",
                func=self._create_jira_issue,
                description="Create a new issue in Jira. Requires title, description, and optional issue_type and priority."
            )
        )
        
        # Search Jira issues tool
        tools.append(
            Tool(
                name="search_jira_issues",
                func=self._search_jira_issues,
                description="Search for issues in Jira. Requires a query string."
            )
        )
        
        # Update Jira issue tool
        tools.append(
            Tool(
                name="update_jira_issue",
                func=self._update_jira_issue,
                description="Update an existing issue in Jira. Requires the issue key and the fields to update."
            )
        )
        
        return tools
    
    async def _create_jira_issue(self, title: str, description: str, 
                              issue_type: str = "Task", priority: str = "Medium") -> Dict[str, Any]:
        """
        Create a Jira issue.
        
        Args:
            title: Issue title
            description: Issue description
            issue_type: Type of issue (Task, Bug, Story, etc.)
            priority: Issue priority
            
        Returns:
            Result of the operation
        """
        return await self.use_tool('atlassian', 'create_jira_issue', {
            "title": title,
            "description": description,
            "issue_type": issue_type,
            "priority": priority
        })
    
    async def _search_jira_issues(self, query: str) -> Dict[str, Any]:
        """
        Search for issues in Jira.
        
        Args:
            query: Search query
            
        Returns:
            Search results
        """
        return await self.use_tool('atlassian', 'search_jira_issues', {
            "query": query
        })
    
    async def _update_jira_issue(self, issue_key: str, fields: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update a Jira issue.
        
        Args:
            issue_key: The key of the issue to update
            fields: Fields to update
            
        Returns:
            Result of the operation
        """
        return await self.use_tool('atlassian', 'update_jira_issue', {
            "issue_key": issue_key,
            "fields": fields
        })
