"""
Project Manager Agent implementation using the modern agent structure.
This agent specializes in project management tasks using Atlassian Jira.
"""

from typing import Any, Dict, List, Optional, Union
import logging
import asyncio
from datetime import datetime

from langchain_core.tools import Tool
from langchain_core.language_models import BaseLanguageModel
from pydantic import BaseModel, Field

from ..models.agent_models import AgentConfig, AgentType, AgentResponse
from .modern_base_agent import ModernBaseAgent
from ..utils.atlassian_tools import JiraTools, ConfluenceTools


class ProjectManagerAgent(ModernBaseAgent):
    """
    Project Manager agent implementation.
    Responsible for project planning, task management, and Jira integration.
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
        
        if mcp_client:
            self.jira_tools = JiraTools(mcp_client)
            self.confluence_tools = ConfluenceTools(mcp_client)
        
        # Create project management tools
        pm_tools = self._create_project_manager_tools()
        all_tools = (tools or []) + pm_tools
        
        # Create the configuration for this agent
        config = AgentConfig(
            name="Project Manager",
            description="Manages project planning, task management, and Jira integration.",
            agent_type=AgentType.PROJECT_MANAGER,
            available_tools={
                'memory-server': ['create_entities', 'create_relations', 'add_observations', 
                                 'read_graph', 'search_nodes', 'open_nodes'],
                'sequential-thinking': ['sequentialthinking'],
                'atlassian': ['get_jira_projects', 'create_jira_project', 'get_jira_issues', 'create_jira_issue',
                             'update_jira_progress']
            },
            system_prompt="""You are the Project Manager agent for the AI Project Management System.
            Your responsibilities include:
            
            1. Creating and managing projects in Jira
            2. Planning project tasks and milestones
            3. Creating and assigning issues in Jira
            4. Tracking project progress and updating stakeholders
            5. Providing status reports on ongoing projects
            6. Identifying and escalating potential project risks
            7. Resource allocation and timeline management
            
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
            
            Always provide actionable recommendations and clear next steps.
            """
        )
        
        # Initialize the base agent
        super().__init__(llm=llm, config=config, tools=all_tools, mcp_client=mcp_client)
        
        self.logger = logging.getLogger("agent.project_manager")
        self.logger.info("Project Manager agent initialized")
    
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
            
            tools.append(
                Tool(
                    name="create_sprint",
                    func=self._create_sprint,
                    description="Create a new sprint in a Jira project. Requires project_key, name, and optionally start_date, end_date."
                )
            )
            
            tools.append(
                Tool(
                    name="assign_issue",
                    func=self._assign_issue,
                    description="Assign a Jira issue to a user. Requires issue_key and assignee_id."
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
                    },
                    {
                        "risk": "Scope creep",
                        "probability": "High",
                        "impact": "High",
                        "mitigation": "Implement formal change management process"
                    },
                    {
                        "risk": "Security vulnerabilities",
                        "probability": "Medium",
                        "impact": "Very High",
                        "mitigation": "Regular security assessments and penetration testing"
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
                    },
                    {
                        "risk": "Stakeholder alignment issues",
                        "probability": "Medium",
                        "impact": "Medium",
                        "mitigation": "Regular stakeholder meetings and clear communication plan"
                    },
                    {
                        "risk": "External dependencies",
                        "probability": "Medium",
                        "impact": "High",
                        "mitigation": "Identify critical dependencies and develop contingency plans"
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
                
            if "regulatory" in description_lower or "compliance" in description_lower:
                additional_risks.append({
                    "risk": "Regulatory compliance issues",
                    "probability": "Medium",
                    "impact": "Very High",
                    "mitigation": "Early engagement with legal and compliance teams"
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
    
    async def _create_sprint(self,
                            project_key: str,
                            name: str,
                            start_date: str = None,
                            end_date: str = None) -> Dict[str, Any]:
        """Create a new sprint in a Jira project."""
        try:
            if not self.jira_tools:
                return {"status": "error", "error": "Jira tools not initialized"}
                
            # This would call a method in jira_tools, but since we didn't implement it,
            # we'll return a mock response for demonstration
            self.logger.info(f"Creating sprint {name} for project {project_key}")
            
            # This is just a mock response - in a real system, this would call a JiraTools method
            return {
                "status": "success",
                "sprint": {
                    "id": "12345",
                    "name": name,
                    "state": "FUTURE",
                    "project_key": project_key,
                    "start_date": start_date or "Not specified",
                    "end_date": end_date or "Not specified",
                    "message": f"Sprint '{name}' created successfully"
                }
            }
        except Exception as e:
            self.logger.error(f"Error creating sprint: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def _assign_issue(self, issue_key: str, assignee_id: str) -> Dict[str, Any]:
        """Assign a Jira issue to a user."""
        try:
            if not self.jira_tools:
                return {"status": "error", "error": "Jira tools not initialized"}
                
            # This would call a method in jira_tools, but since we didn't implement it,
            # we'll return a mock response for demonstration
            self.logger.info(f"Assigning issue {issue_key} to user {assignee_id}")
            
            # This is just a mock response - in a real system, this would call a JiraTools method
            return {
                "status": "success",
                "assignment": {
                    "issue_key": issue_key,
                    "assignee_id": assignee_id,
                    "message": f"Issue {issue_key} assigned to {assignee_id}"
                }
            }
        except Exception as e:
            self.logger.error(f"Error assigning issue: {str(e)}")
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
            if is_markdown:
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