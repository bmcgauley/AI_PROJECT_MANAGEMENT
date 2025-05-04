#!/usr/bin/env python3
"""
Request Processor module for the AI Project Management System.
Handles request classification, agent selection, and response processing.
"""

import asyncio
import logging
import json
from typing import Dict, List, Any, Tuple, Optional
from datetime import datetime

from crewai import Crew, Task

from src.orchestration import AgentOrchestrator
from src.mcp_client import MCPClient

logger = logging.getLogger("ai_pm_system.request_processor")

class RequestProcessor:
    """
    Processes user requests by classifying them, selecting appropriate agents,
    and coordinating the response generation.
    """
    
    def __init__(self, orchestrator: AgentOrchestrator, mcp_client: Optional[MCPClient] = None):
        """
        Initialize the request processor.
        
        Args:
            orchestrator: Agent orchestrator for creating crews and tasks
            mcp_client: Optional MCP client for tool execution
        """
        self.orchestrator = orchestrator
        self.mcp_client = mcp_client
        self.agent_states = orchestrator.get_agent_states()
    
    async def process_request(self, 
                             user_request: str, 
                             request_id: str = None,
                             event_handler: Any = None) -> Dict[str, Any]:
        """
        Process a user request through the Crew.ai system.
        
        Args:
            user_request: The user's request text
            request_id: Optional unique identifier for the request
            event_handler: Optional event handler for real-time updates
            
        Returns:
            Dict[str, Any]: Response containing the processing result
        """
        if not self.orchestrator.agents_dict:
            return {
                "status": "error",
                "processed_by": "System",
                "response": "The agent system is not initialized yet. Please try again later.",
                "request_id": request_id
            }
        
        if event_handler:
            await event_handler("workflow_step", 
                message="Analyzing request to determine required agents and workflow",
                request_id=request_id
            )
        
        # Classify the request to determine relevant agents and primary task
        classification = self._classify_request(user_request)
        primary_agent = classification["primary_agent"]
        involved_agents = classification["involved_agents"]
        is_jira_request = classification["is_jira_request"]
        
        try:
            # Handle Atlassian/Jira integration when needed
            atlassian_context = None
            if is_jira_request and self.mcp_client:
                if event_handler:
                    await event_handler("workflow_step", 
                        message="Request requires Atlassian/Jira integration, activating Atlassian MCP server",
                        request_id=request_id
                    )
                
                # Get context from Jira if the request is about existing projects
                if any(kw in user_request.lower() for kw in ["get", "list", "show"]):
                    try:
                        # Try to get projects from Atlassian MCP
                        projects_response = await self.mcp_client.use_tool("atlassian", "get_jira_projects", {})
                        if "result" in projects_response and "projects" in projects_response["result"]:
                            atlassian_context = {
                                "projects": projects_response["result"]["projects"]
                            }
                            
                            if event_handler:
                                await event_handler("workflow_step", 
                                    message=f"Retrieved {len(atlassian_context['projects'])} projects from Jira",
                                    request_id=request_id
                                )
                    except Exception as e:
                        if event_handler:
                            await event_handler("workflow_step", 
                                message=f"Unable to retrieve Jira projects: {str(e)}",
                                request_id=request_id
                            )
            
            # Update agent states for UI
            for agent in involved_agents:
                self.agent_states[agent] = "assigned"
            
            self.agent_states[primary_agent] = "active"
            
            # Notify about agent assignments
            if event_handler:
                for agent in involved_agents:
                    await event_handler("agent_assigned", 
                        agent=agent,
                        request_id=request_id
                    )
                    
                await event_handler("agent_thinking", 
                    agent=primary_agent,
                    thinking=f"Working on: '{user_request}'",
                    request_id=request_id
                )
            
            # Enhance the task description with context for Jira-related requests
            task_description = f"Handle this request: '{user_request}'"
            if is_jira_request and atlassian_context:
                project_names = ", ".join([p["name"] for p in atlassian_context["projects"][:5]])
                task_description += f"\n\nContext: User has these Jira projects: {project_names}"
                if len(atlassian_context["projects"]) > 5:
                    task_description += f" and {len(atlassian_context['projects']) - 5} more"
            
            # Create crew and task for this request
            crew, main_task = self.orchestrator.create_crew_for_request(
                primary_agent_name=primary_agent,
                task_description=task_description,
                involved_agent_names=involved_agents
            )
            
            # Execute the crew
            result = crew.kickoff()
            
            # Process Jira project creation if requested
            response = await self._process_jira_creation(
                user_request, 
                result, 
                is_jira_request, 
                event_handler, 
                request_id
            )
            
            # Notify of request completion
            if event_handler:
                await event_handler("request_complete", 
                    message="Request processing completed",
                    request_id=request_id,
                    involved_agents=involved_agents
                )
            
            # Reset agent states to idle
            for agent in involved_agents:
                self.agent_states[agent] = "idle"
            
            return {
                "status": "success",
                "processed_by": primary_agent,
                "involved_agents": involved_agents,
                "response": response,
                "request_id": request_id
            }
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            logger.error(error_msg)
            
            if event_handler:
                await event_handler("request_error", 
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
    
    def _classify_request(self, user_request: str) -> Dict[str, Any]:
        """
        Classify a user request to determine the appropriate agents and tasks.
        
        Args:
            user_request: The user's request text
            
        Returns:
            Dict[str, Any]: Classification results
        """
        # Convert to lowercase for easier keyword matching
        lower_request = user_request.lower()
        
        # Determine if this is a project management related request
        is_pm_request = any(kw in lower_request for kw in [
            "project", "jira", "task", "timeline", "schedule", "plan", "roadmap", "milestone", 
            "gantt", "progress", "status update", "sprint", "backlog"
        ])
        
        # Determine if this is specifically about creating or accessing Jira
        is_jira_request = any(kw in lower_request for kw in [
            "jira", "atlassian", "create project", "create task", "issue", "ticket"
        ])
        
        # Determine primary task category
        is_research = any(kw in lower_request for kw in [
            "research", "find", "search", "analyze", "information", "data", "discovery", "trends"
        ])
        
        is_development = any(kw in lower_request for kw in [
            "code", "develop", "implement", "programming", "script", "application", "function", 
            "class", "module", "template", "git", "repository"
        ])
        
        is_reporting = any(kw in lower_request for kw in [
            "report", "document", "paper", "summary", "documentation", "specs", "presentation"
        ])
        
        is_analysis = any(kw in lower_request for kw in [
            "analyze", "requirements", "business case", "specification", "business rules"
        ])
        
        # Define involved agents based on the request type
        involved_agents = []
        primary_agent = None
        
        # Set up the primary agent and tasks based on request classification
        if is_development:
            primary_agent = "Code Developer"
            involved_agents = ["Code Developer", "Code Reviewer"]
            
            # If it's also a project task, involve the PM
            if is_pm_request:
                involved_agents.append("Project Manager")
        
        elif is_research:
            primary_agent = "Research Specialist"
            involved_agents = ["Research Specialist"]
            
            # For project-related research, involve the PM
            if is_pm_request:
                involved_agents.append("Project Manager")
        
        elif is_reporting:
            primary_agent = "Report Drafter"
            involved_agents = ["Report Drafter", "Report Reviewer", "Report Publisher"]
            
            # For project reports, involve the PM
            if is_pm_request:
                involved_agents.append("Project Manager")
        
        elif is_analysis:
            primary_agent = "Business Analyst" 
            involved_agents = ["Business Analyst"]
            
            # For project-related analysis, involve the PM
            if is_pm_request:
                involved_agents.append("Project Manager")
        
        elif is_pm_request or is_jira_request:
            # All PM/Jira requests go through the PM
            primary_agent = "Project Manager"
            involved_agents = ["Project Manager"]
            
            # For sophisticated project needs, involve the Business Analyst too
            if "requirements" in lower_request or "scope" in lower_request:
                involved_agents.append("Business Analyst")
        
        else:
            # Default to PM for general inquiries
            primary_agent = "Project Manager" 
            involved_agents = ["Project Manager"]
        
        return {
            "primary_agent": primary_agent,
            "involved_agents": involved_agents,
            "is_pm_request": is_pm_request,
            "is_jira_request": is_jira_request,
            "is_research": is_research,
            "is_development": is_development,
            "is_reporting": is_reporting,
            "is_analysis": is_analysis
        }
    
    async def _process_jira_creation(self, 
                                    user_request: str, 
                                    result: Any, 
                                    is_jira_request: bool,
                                    event_handler: Any = None,
                                    request_id: str = None) -> str:
        """
        Process Jira project creation if the request is for that.
        
        Args:
            user_request: The user's request
            result: The result from crew execution
            is_jira_request: Whether this is a Jira-related request
            event_handler: Optional event handler for updates
            request_id: Optional request identifier
            
        Returns:
            str: The final response text
        """
        serializable_result = str(result) if hasattr(result, '__str__') else "Task completed successfully"
        
        # For Jira project creation requests, try to actually create the project
        if is_jira_request and self.mcp_client and ("create" in user_request.lower() and "project" in user_request.lower()):
            try:
                # Extract project name from the user request or result
                project_name = None
                if "project" in user_request.lower() and "named" in user_request.lower():
                    # Try to extract project name from the request
                    parts = user_request.lower().split("named")
                    if len(parts) > 1:
                        project_name = parts[1].strip().strip('"\'').split()[0]
                
                if project_name:
                    # Try to actually create the project
                    if event_handler:
                        await event_handler("workflow_step", 
                            message=f"Attempting to create Jira project: {project_name}",
                            request_id=request_id
                        )
                    
                    create_response = await self.mcp_client.use_tool("atlassian", "create_jira_project", {
                        "name": project_name,
                        "description": f"Project created by AI Project Management System on {datetime.now().strftime('%Y-%m-%d')}"
                    })
                    
                    if "result" in create_response and "project" in create_response["result"]:
                        project_info = create_response["result"]["project"]
                        
                        # Add project creation confirmation to the result
                        serializable_result += f"\n\nI've created the Jira project '{project_name}' with key '{project_info.get('key', 'UNKNOWN')}' for you."
                    else:
                        serializable_result += "\n\nI tried to create the Jira project for you, but encountered an issue. Please check your Atlassian credentials and try again."
            except Exception as e:
                # Just log the error but continue with the result from the crew
                if event_handler:
                    await event_handler("workflow_step", 
                        message=f"Error creating Jira project: {str(e)}",
                        request_id=request_id
                    )
        
        return serializable_result
