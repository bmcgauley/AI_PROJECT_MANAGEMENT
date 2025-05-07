"""
Project Manager agent implementation using the modern agent structure with Pydantic and LangGraph.
"""

from typing import Any, Dict, List, Optional, Union
import logging
import uuid
from datetime import datetime

from langchain_core.tools import Tool
from ..models.agent_models import AgentConfig, AgentType, ProjectSummary
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

class ModernProjectManager:
    """
    Modern Project Manager for handling project data operations.
    
    This class is responsible for managing project data, including creation,
    updates, and analysis. It works alongside the ProjectManagerAgent which
    handles the conversational and tool execution aspects.
    """
    
    def __init__(self, agent: ProjectManagerAgent):
        """
        Initialize the Project Manager.
        
        Args:
            agent: The ProjectManagerAgent that will assist with tool execution
        """
        self.agent = agent
        self.logger = logging.getLogger("modern_project_manager")
        # In a real implementation, this would be replaced with a database
        self.projects: Dict[str, ProjectSummary] = {}
        
    async def create_project(self, project_details: Dict[str, Any]) -> ProjectSummary:
        """
        Create a new project with the provided details.
        
        Args:
            project_details: Dictionary containing project details
            
        Returns:
            ProjectSummary representing the created project
        """
        self.logger.info(f"Creating new project: {project_details.get('name', 'Unnamed')}")
        
        project_id = str(uuid.uuid4())
        project = ProjectSummary(
            project_id=project_id,
            name=project_details.get("name", "Unnamed Project"),
            description=project_details.get("description", ""),
            team_members=project_details.get("team_members", []),
            metadata=project_details.get("metadata", {})
        )
        
        # Store the project
        self.projects[project_id] = project
        
        # Create a Jira issue for the project if configured
        if project_details.get("create_jira", False):
            try:
                jira_result = await self.agent._create_jira_issue(
                    title=f"Project: {project.name}",
                    description=project.description,
                    issue_type="Project"
                )
                project.metadata["jira_key"] = jira_result.get("key")
                project.metadata["jira_url"] = jira_result.get("url")
            except Exception as e:
                self.logger.error(f"Failed to create Jira issue for project {project_id}: {str(e)}")
        
        self.logger.info(f"Project created successfully with ID: {project_id}")
        return project
    
    async def update_project(self, project_id: str, updates: Dict[str, Any]) -> ProjectSummary:
        """
        Update an existing project.
        
        Args:
            project_id: ID of the project to update
            updates: Dictionary of fields to update
            
        Returns:
            Updated ProjectSummary
            
        Raises:
            ValueError: If project_id is not found
        """
        if project_id not in self.projects:
            self.logger.error(f"Project not found: {project_id}")
            raise ValueError(f"Project with ID {project_id} not found")
            
        project = self.projects[project_id]
        
        # Update project fields
        if "name" in updates:
            project.name = updates["name"]
        if "description" in updates:
            project.description = updates["description"]
        if "status" in updates:
            project.status = updates["status"]
        if "team_members" in updates:
            project.team_members = updates["team_members"]
        if "tasks" in updates:
            project.tasks = updates["tasks"]
        if "milestones" in updates:
            project.milestones = updates["milestones"]
        if "metadata" in updates:
            project.metadata.update(updates["metadata"])
            
        # Update last_updated timestamp
        project.last_updated = datetime.now()
        
        # Update Jira if connected
        if project.metadata.get("jira_key") and updates.get("update_jira", True):
            try:
                jira_fields = {}
                if "name" in updates:
                    jira_fields["summary"] = updates["name"]
                if "description" in updates:
                    jira_fields["description"] = updates["description"]
                if "status" in updates:
                    jira_fields["status"] = updates["status"]
                    
                await self.agent._update_jira_issue(
                    issue_key=project.metadata["jira_key"],
                    fields=jira_fields
                )
            except Exception as e:
                self.logger.error(f"Failed to update Jira for project {project_id}: {str(e)}")
                
        self.logger.info(f"Project {project_id} updated successfully")
        return project
    
    async def analyze_project(self, project_id: str, analysis_type: str = "general") -> Dict[str, Any]:
        """
        Perform analysis on a project.
        
        Args:
            project_id: ID of the project to analyze
            analysis_type: Type of analysis to perform (general, risk, timeline, etc.)
            
        Returns:
            Dictionary with analysis results
            
        Raises:
            ValueError: If project_id is not found
        """
        if project_id not in self.projects:
            self.logger.error(f"Project not found: {project_id}")
            raise ValueError(f"Project with ID {project_id} not found")
            
        project = self.projects[project_id]
        
        # Perform different types of analysis based on analysis_type
        if analysis_type == "general":
            return self._analyze_general(project)
        elif analysis_type == "risk":
            return self._analyze_risks(project)
        elif analysis_type == "timeline":
            return self._analyze_timeline(project)
        else:
            self.logger.warning(f"Unknown analysis type: {analysis_type}, falling back to general analysis")
            return self._analyze_general(project)
    
    def _analyze_general(self, project: ProjectSummary) -> Dict[str, Any]:
        """Perform general analysis on a project."""
        tasks_total = len(project.tasks)
        tasks_completed = sum(1 for task in project.tasks if task.get("status") == "completed")
        
        milestones_total = len(project.milestones)
        milestones_completed = sum(1 for milestone in project.milestones if milestone.get("status") == "completed")
        
        return {
            "project_id": project.project_id,
            "project_name": project.name,
            "status": project.status,
            "completion_percentage": round((tasks_completed / tasks_total * 100) if tasks_total > 0 else 0, 2),
            "tasks": {
                "total": tasks_total,
                "completed": tasks_completed,
                "in_progress": sum(1 for task in project.tasks if task.get("status") == "in_progress"),
                "not_started": sum(1 for task in project.tasks if task.get("status") == "not_started")
            },
            "milestones": {
                "total": milestones_total,
                "completed": milestones_completed,
                "upcoming": milestones_total - milestones_completed
            },
            "team_size": len(project.team_members),
            "last_updated": project.last_updated.isoformat()
        }
    
    def _analyze_risks(self, project: ProjectSummary) -> Dict[str, Any]:
        """Analyze risks associated with a project."""
        # Risk analysis logic would go here
        # For now, just return a placeholder
        return {
            "project_id": project.project_id,
            "project_name": project.name,
            "risks": []
        }
    
    def _analyze_timeline(self, project: ProjectSummary) -> Dict[str, Any]:
        """Analyze timeline and delivery dates for a project."""
        # Timeline analysis logic would go here
        # For now, just return a placeholder
        return {
            "project_id": project.project_id,
            "project_name": project.name,
            "timeline": {
                "start_date": project.creation_date.isoformat(),
                "estimated_end_date": None,
                "milestones": []
            }
        }
