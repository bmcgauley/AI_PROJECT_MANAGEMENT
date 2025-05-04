#!/usr/bin/env python3
"""
Request Processor module for the AI Project Management System.
Handles request classification, agent selection, and response processing.
"""

import asyncio
import logging
import json
import inspect
from typing import Dict, List, Any, Tuple, Optional, Callable
from datetime import datetime

from crewai import Crew, Task

from src.orchestration import AgentOrchestrator
from src.mcp_client import MCPClient
from src.agents.chat_coordinator import ChatCoordinatorAgent

logger = logging.getLogger("ai_pm_system.request_processor")

class RequestProcessor:
    """
    Processes user requests by classifying them, selecting appropriate agents,
    and coordinating the response generation using the ChatCoordinatorAgent.
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
        self.coordinator = None  # Will be set in initialize()
        
    async def initialize(self, event_handler: Optional[Callable] = None):
        """
        Initialize the request processor with the ChatCoordinatorAgent.
        
        Args:
            event_handler: Optional event handler for WebSocket updates
        """
        # Initialize the system with ChatCoordinatorAgent as the main interface
        system_components = await self.orchestrator.initialize_system(event_handler)
        self.coordinator = system_components["coordinator"]
        
        logger.info("RequestProcessor initialized with ChatCoordinatorAgent interface")
    
    async def process_request(self, 
                             user_request: str, 
                             request_id: str = None,
                             event_handler: Any = None) -> Dict[str, Any]:
        """
        Process a user request through the ChatCoordinatorAgent interface.
        
        Args:
            user_request: The user's request text
            request_id: Optional unique identifier for the request
            event_handler: Optional event handler for real-time updates
            
        Returns:
            Dict[str, Any]: Response containing the processing result
        """
        if not self.coordinator:
            return {
                "status": "error",
                "processed_by": "System",
                "response": "The agent system is not initialized yet. Please try again later.",
                "request_id": request_id
            }
        
        try:
            # Process the request through the ChatCoordinatorAgent
            result = await self.coordinator.process_message(user_request)
            return result
            
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
    
    # Legacy methods preserved for backward compatibility
    def _classify_request(self, user_request: str) -> Dict[str, Any]:
        """
        Legacy method to classify a user request.
        Now redirects to the ChatCoordinatorAgent's classification logic.
        """
        logger.warning("Using legacy _classify_request method - consider using ChatCoordinatorAgent instead")
        
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
