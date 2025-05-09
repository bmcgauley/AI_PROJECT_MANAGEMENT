"""
Project Manager agent implementation using Pydantic and LangGraph architecture.
This agent specializes in project management tasks, Jira integration, and resource planning.
"""

from typing import Any, Dict, List, Optional, Union
import logging
import asyncio
import uuid
from datetime import datetime

from langchain_core.tools import Tool
from langchain_core.language_models import BaseLanguageModel
from pydantic import BaseModel, Field

from ..models.agent_models import AgentConfig, AgentType, ProjectSummary, AgentResponse
from .base_agent import BaseAgent
from ..utils.atlassian_tools import JiraTools, ConfluenceTools


class ProjectManagerAgent(BaseAgent):
    """
    Project Manager agent implementation.
    Specializes in project planning, organization, and management tasks.
    """
    
    def __init__(self, llm: BaseLanguageModel, mcp_client: Optional[Any] = None, tools: Optional[List[Tool]] = None):
        """
        Initialize the Project Manager agent.
        
        Args:
            llm: Language model to use
            mcp_client: Optional client for MCP interactions
            tools: Optional list of additional tools
        """
        # Initialize Atlassian tools if MCP client is provided
        self.jira_tools = None
        self.confluence_tools = None
        self.llm = llm
        self._name = "Project Manager"
        self._description = "Specializes in project planning, task management, and resource allocation."
        self.memory = []
        
        if mcp_client:
            self.jira_tools = JiraTools(mcp_client)
            self.confluence_tools = ConfluenceTools(mcp_client)
        
        # Create project management tools
        pm_tools = self._create_project_manager_tools()
        all_tools = (tools or []) + pm_tools
        
        # Create the configuration for this agent
        self.config = AgentConfig(
            name=self._name,
            description=self._description,
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
            
            When managing projects:
            - Create structured project plans with clear milestones
            - Break down complex tasks into manageable sub-tasks
            - Assign appropriate priorities to tasks
            - Track progress against deadlines
            - Recommend adjustments to project scope or timeline as needed
            - Document project decisions and status updates
            
            When using Jira:
            - Create well-organized projects with meaningful keys
            - Create issues with clear descriptions and acceptance criteria
            - Use appropriate issue types (Epic, Story, Task, Bug)
            - Apply consistent labeling and categorization
            - Update issue status and progress regularly
            - Link related issues together for better tracking
            
            Be proactive, organized, and detail-oriented in your approach.
            When making decisions, consider project constraints, priorities, and dependencies.
            Always provide actionable recommendations and clear next steps.
            """
        )
        
        self.tools = all_tools
        self.mcp_client = mcp_client
        
        # Set up logging
        self.logger = logging.getLogger("agent.project_manager")
        self.logger.info("Project Manager agent initialized")
    
    def initialize(self) -> None:
        """
        Initialize the agent with any necessary setup.
        Should be called before the first run.
        """
        self.logger.info(f"Agent {self.name} initialized")
    
    @property
    def name(self) -> str:
        """Get the agent's name."""
        return self._name
    
    @property
    def description(self) -> str:
        """Get the agent's description."""
        return self._description
    
    def run(self, request: str) -> Dict[str, Any]:
        """
        Run the agent with the given request.
        
        Args:
            request: The request to process
            
        Returns:
            Dictionary with response and other metadata
        """
        # Create an event loop to run the async process method synchronously
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        response = loop.run_until_complete(self.process(request))
        
        # Convert response to dictionary
        return {
            "name": response.agent_name,
            "response": response.content,
            "error": response.error,
            "timestamp": str(response.timestamp),
            "tool_calls": response.tool_calls
        }
    
    def _create_project_manager_tools(self) -> List[Tool]:
        """
        Create tools for project management capabilities.
        
        Returns:
            List of LangChain tools for project management
        """
        tools = []
        
        # Add general project management tools that don't require Jira
        tools.append(
            Tool(
                name="create_project_plan",
                func=self._create_project_plan,
                description="Create a detailed project plan with timeline, tasks, and resource allocation."
            )
        )
        
        tools.append(
            Tool(
                name="estimate_project_timeline",
                func=self._estimate_project_timeline,
                description="Estimate a project timeline based on scope and resource availability."
            )
        )
        
        tools.append(
            Tool(
                name="risk_assessment",
                func=self._risk_assessment,
                description="Identify and assess potential risks to a project."
            )
        )
        
        # Add Jira tools if available
        if self.jira_tools:
            tools.append(
                Tool(
                    name="get_jira_projects",
                    func=self._get_jira_projects,
                    description="Get all available Jira projects."
                )
            )
            
            tools.append(
                Tool(
                    name="create_jira_project",
                    func=self._create_jira_project,
                    description="Create a new Jira project. Requires name, and optionally key, description."
                )
            )
            
            tools.append(
                Tool(
                    name="get_jira_issues",
                    func=self._get_jira_issues,
                    description="Get Jira issues by project key or JQL query. Requires either project_key or jql parameter."
                )
            )
            
            tools.append(
                Tool(
                    name="create_jira_issue",
                    func=self._create_jira_issue,
                    description="Create a new Jira issue. Requires project_key, summary, and optionally description, issue_type, priority."
                )
            )
            
            tools.append(
                Tool(
                    name="update_jira_progress",
                    func=self._update_jira_progress,
                    description="Update the progress of a Jira issue. Requires issue_key, progress percentage, and optionally a note."
                )
            )
        
        # Add Confluence tools if available (for project documentation)
        if self.confluence_tools:
            tools.append(
                Tool(
                    name="create_project_documentation",
                    func=self._create_project_documentation,
                    description="Create project documentation in Confluence. Requires space_key, title, and content."
                )
            )
        
        return tools
    
    def _create_project_plan(self, 
                            project_name: str, 
                            description: str, 
                            team_size: int = 5,
                            duration_weeks: int = 12) -> Dict[str, Any]:
        """Create a detailed project plan."""
        try:
            self.logger.info(f"Creating project plan for {project_name}")
            
            # This is a simplified example - in a real system, this would be more sophisticated
            phases = [
                {
                    "name": "Planning",
                    "duration": max(1, int(duration_weeks * 0.2)),
                    "tasks": [
                        "Define project scope and objectives",
                        "Identify stakeholders",
                        "Create initial risk assessment",
                        "Develop resource allocation plan",
                        "Set up project in Jira"
                    ]
                },
                {
                    "name": "Execution",
                    "duration": max(1, int(duration_weeks * 0.6)),
                    "tasks": [
                        "Execute project tasks according to plan",
                        "Regular status updates and meetings",
                        "Track progress against milestones",
                        "Manage resources and dependencies",
                        "Address issues and obstacles"
                    ]
                },
                {
                    "name": "Monitoring & Control",
                    "duration": max(1, int(duration_weeks * 0.15)),
                    "tasks": [
                        "Monitor project progress",
                        "Compare actual vs planned performance",
                        "Implement corrective actions if needed",
                        "Update stakeholders on progress",
                        "Adjust plan based on feedback and progress"
                    ]
                },
                {
                    "name": "Closure",
                    "duration": max(1, int(duration_weeks * 0.05)),
                    "tasks": [
                        "Formal project closure",
                        "Lessons learned documentation",
                        "Handover documentation",
                        "Final project report",
                        "Celebration and team recognition"
                    ]
                }
            ]
            
            # Calculate resource allocation based on team size
            developers = max(1, int(team_size * 0.7))
            qa = max(1, int(team_size * 0.2))
            pm = 1
            
            resources = {
                "developers": developers,
                "qa_engineers": qa,
                "project_manager": pm,
                "other_roles": team_size - (developers + qa + pm)
            }
            
            return {
                "status": "success",
                "project_plan": {
                    "name": project_name,
                    "description": description,
                    "team_size": team_size,
                    "duration_weeks": duration_weeks,
                    "phases": phases,
                    "resources": resources,
                    "estimated_completion_time": f"{duration_weeks} weeks"
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error creating project plan: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def _estimate_project_timeline(self, 
                                  task_list: List[str],
                                  team_size: int = 3,
                                  complexity: str = "medium") -> Dict[str, Any]:
        """Estimate a project timeline based on scope and resources."""
        try:
            self.logger.info("Estimating project timeline")
            
            # Complexity factors
            complexity_factor = {
                "low": 0.8,
                "medium": 1.0,
                "high": 1.5,
                "very high": 2.0
            }.get(complexity.lower(), 1.0)
            
            # Very simple estimation model
            task_count = len(task_list)
            avg_days_per_task = 2 * complexity_factor
            
            # Team efficiency factor (diminishing returns with larger teams)
            team_efficiency = 0.8 if team_size > 5 else 1.0
            
            # Calculate total days needed
            total_days = (task_count * avg_days_per_task) / (team_size * team_efficiency)
            
            # Add buffer for meetings, communication overhead
            total_days_with_buffer = total_days * 1.2
            
            # Convert to weeks
            estimated_weeks = round(total_days_with_buffer / 5, 1)  # Assuming 5-day workweeks
            
            return {
                "status": "success",
                "timeline": {
                    "task_count": task_count,
                    "team_size": team_size,
                    "complexity": complexity,
                    "estimated_days": round(total_days_with_buffer, 1),
                    "estimated_weeks": estimated_weeks,
                    "estimated_completion_date": f"~{estimated_weeks} weeks from start date"
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error estimating timeline: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def _risk_assessment(self, project_description: str, industry: str = "technology") -> Dict[str, Any]:
        """Identify and assess potential risks to a project."""
        try:
            self.logger.info(f"Performing risk assessment for a {industry} project")
            
            # Common project risks based on industry and description keywords
            # This is a simplified example - in a real system, this would use more sophisticated analysis
            common_risks = []
            
            # Technology industry specific risks
            if industry.lower() == "technology":
                common_risks = [
                    {
                        "risk": "Technical complexity underestimation",
                        "probability": "Medium",
                        "impact": "High",
                        "mitigation": "Conduct detailed technical assessment during planning phase"
                    },
                    {
                        "risk": "Integration challenges with existing systems",
                        "probability": "Medium",
                        "impact": "High",
                        "mitigation": "Perform early integration testing and establish fallback options"
                    },
                    {
                        "risk": "Resource availability constraints",
                        "probability": "Medium",
                        "impact": "Medium",
                        "mitigation": "Identify critical resource needs and secure commitments early"
                    }
                ]
            else:
                # Generic risks for other industries
                common_risks = [
                    {
                        "risk": "Budget constraints",
                        "probability": "Medium",
                        "impact": "High",
                        "mitigation": "Regular budget reviews and contingency planning"
                    },
                    {
                        "risk": "Schedule delays",
                        "probability": "High",
                        "impact": "Medium",
                        "mitigation": "Buffer time in critical path and regular schedule reviews"
                    }
                ]
            
            # Simple keyword-based risk identification from project description
            description_lower = project_description.lower()
            additional_risks = []
            
            if "new technology" in description_lower or "innovative" in description_lower:
                additional_risks.append({
                    "risk": "Technology maturity risk",
                    "probability": "High",
                    "impact": "High",
                    "mitigation": "Conduct proof of concepts and secure expert resources"
                })
                
            if "global" in description_lower or "international" in description_lower:
                additional_risks.append({
                    "risk": "Cross-cultural communication challenges",
                    "probability": "Medium",
                    "impact": "Medium",
                    "mitigation": "Cultural awareness training and localized communication plans"
                })
            
            # Combine risks
            all_risks = common_risks + additional_risks
            
            return {
                "status": "success",
                "risk_assessment": {
                    "project_type": industry,
                    "total_risks_identified": len(all_risks),
                    "risks": all_risks,
                    "recommendation": "Regular risk reviews should be conducted throughout the project lifecycle."
                }
            }
            
        except Exception as e:
            self.logger.error(f"Error performing risk assessment: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def _get_jira_projects(self) -> Dict[str, Any]:
        """Get all available Jira projects."""
        try:
            if not self.jira_tools:
                return {"status": "error", "error": "Jira tools not initialized"}
                
            projects = await self.jira_tools.get_projects()
            return {
                "status": "success",
                "projects": projects
            }
        except Exception as e:
            self.logger.error(f"Error getting Jira projects: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def _create_jira_project(self, 
                                  name: str, 
                                  key: str = None, 
                                  description: str = None) -> Dict[str, Any]:
        """Create a new Jira project."""
        try:
            if not self.jira_tools:
                return {"status": "error", "error": "Jira tools not initialized"}
                
            result = await self.jira_tools.create_project(
                name=name,
                key=key,
                description=description
            )
            return {
                "status": "success",
                "project": result
            }
        except Exception as e:
            self.logger.error(f"Error creating Jira project: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def _get_jira_issues(self, 
                              project_key: str = None, 
                              jql: str = None) -> Dict[str, Any]:
        """Get Jira issues by project key or JQL query."""
        try:
            if not self.jira_tools:
                return {"status": "error", "error": "Jira tools not initialized"}
                
            issues = await self.jira_tools.get_issues(
                project_key=project_key,
                jql=jql
            )
            return {
                "status": "success",
                "issues": issues
            }
        except Exception as e:
            self.logger.error(f"Error getting Jira issues: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def _create_jira_issue(self, 
                                project_key: str, 
                                summary: str, 
                                description: str = None,
                                issue_type: str = "Task", 
                                priority: str = "Medium") -> Dict[str, Any]:
        """Create a new Jira issue."""
        try:
            if not self.jira_tools:
                return {"status": "error", "error": "Jira tools not initialized"}
                
            result = await self.jira_tools.create_issue(
                project_key=project_key,
                summary=summary,
                description=description,
                issue_type=issue_type,
                priority=priority
            )
            return {
                "status": "success",
                "issue": result
            }
        except Exception as e:
            self.logger.error(f"Error creating Jira issue: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def _update_jira_progress(self, 
                                   issue_key: str, 
                                   progress: int, 
                                   note: str = None) -> Dict[str, Any]:
        """Update the progress of a Jira issue."""
        try:
            if not self.jira_tools:
                return {"status": "error", "error": "Jira tools not initialized"}
                
            result = await self.jira_tools.update_progress(
                issue_key=issue_key,
                progress=progress,
                note=note
            )
            return {
                "status": "success",
                "result": result
            }
        except Exception as e:
            self.logger.error(f"Error updating Jira progress: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def _create_project_documentation(self, 
                                           space_key: str, 
                                           title: str, 
                                           content: str,
                                           is_markdown: bool = False) -> Dict[str, Any]:
        """Create project documentation in Confluence."""
        try:
            if not self.confluence_tools:
                return {"status": "error", "error": "Confluence tools not initialized"}
            
            # Convert markdown content if specified
            if is_markdown and hasattr(self.confluence_tools, 'markdown_to_confluence_storage_format'):
                content = self.confluence_tools.markdown_to_confluence_storage_format(content)
            
            result = await self.confluence_tools.create_page(
                space_key=space_key,
                title=title,
                content=content
            )
            return {
                "status": "success",
                "page": result
            }
        except Exception as e:
            self.logger.error(f"Error creating project documentation: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def process(self, request: str) -> AgentResponse:
        """
        Process a request and generate a response.
        This simplified implementation will be enhanced later.
        
        Args:
            request: The request to process
            
        Returns:
            The agent's response
        """
        try:
            # Simple implementation for now
            response_content = f"Project Manager received: {request}"
            
            # Will be replaced with actual processing logic
            return AgentResponse(
                agent_name=self.name,
                content=response_content,
                timestamp=datetime.now()
            )
        except Exception as e:
            error = f"Error processing request: {str(e)}"
            self.logger.error(error)
            return AgentResponse(
                agent_name=self.name,
                content="",
                error=error,
                timestamp=datetime.now()
            )


class ProjectManager:
    """
    Project Manager for handling project data operations.
    
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
        self.logger = logging.getLogger("project_manager")
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
                    project_key=project_details.get("jira_project_key", "PROJ"),
                    summary=f"Project: {project.name}",
                    description=project.description,
                    issue_type="Project"
                )
                if isinstance(jira_result, dict) and "issue" in jira_result:
                    project.metadata["jira_key"] = jira_result["issue"].get("key")
                    project.metadata["jira_url"] = jira_result["issue"].get("url")
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