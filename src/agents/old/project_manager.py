"""
Project Manager Agent for the AI Project Management System.
PMBOK/PMP certified agent for project planning, task management, and Jira integration.
"""

import json
import asyncio
from typing import Any, Dict, Optional, List # Added List
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough
import logging

from src.agents.base_agent import BaseAgent

class ProjectManagerAgent(BaseAgent):
    """
    Agent acting as a PMBOK certified PMP professional who handles
    project management related requests, potentially using Jira or Confluence tools.
    """
    
    def __init__(self, llm, mcp_client: Optional[Any] = None):
        """
        Initialize the project manager agent.
        
        Args:
            llm: Language model to use for generating responses
            mcp_client: Optional client for interacting with MCP servers (e.g., Atlassian).
        """
        super().__init__(
            llm=llm,
            name="Project Manager",
            description="PMBOK/PMP certified agent for project planning, task management, and potentially Jira/Confluence integration via MCP.",
            mcp_client=mcp_client
        )
        
        # Define the prompt template for the project manager
        self.pm_prompt = PromptTemplate(
            input_variables=["request", "context", "category", "details", "supporting_responses"],
            template="""
            You are a PMBOK certified Project Management Professional (PMP) AI assistant.
            Your expertise is in project management best practices, methodologies, and tools.
            
            You can help with:
            - Project planning and scheduling
            - Task breakdown and management
            - Risk assessment and mitigation
            - Resource allocation
            - Stakeholder management
            - Project reporting and documentation
            - Jira integration for task tracking
            
            Context from previous interactions:
            {context}
            
            The user's request is categorized as: {category}
            Additional details: {details}
            
            The original request is:
            {request}
            
            Supporting agent responses (if any):
            {supporting_responses}
            
            Based on your expertise in PMBOK standards and project management best practices,
            provide a detailed, professional response addressing the request. Include:
            
            1. A brief acknowledgment of the request
            2. Your expert analysis or recommendation
            3. Next steps or action items if applicable
            4. Any relevant PMBOK framework references
            
            If supporting agent responses are provided, integrate their insights into your response.
            
            Remember to maintain a professional tone and focus on delivering actionable insights.
            """
        )
        
        # Create the chain for project management responses using the newer approach
        self.pm_chain = self.pm_prompt | llm
        
        # For handling Jira integration
        self.jira_enabled = False
        
        # Check if MCP client is available and set Jira integration status
        if mcp_client and mcp_client.is_server_active("atlassian"):
            self.jira_enabled = True
            self.logger.info("Jira integration enabled via Atlassian MCP server")
        else:
            self.logger.warning("Jira integration not available: MCP client not configured or Atlassian server not active")
    
    async def get_jira_projects(self) -> List[Dict[str, Any]]:
        """
        Get all Jira projects accessible to the user.
        
        Returns:
            List[Dict[str, Any]]: A list of projects or empty list if error occurs
        """
        if not self.jira_enabled or not self.mcp_client:
            self.logger.warning("Cannot get Jira projects - Jira integration not enabled")
            return []
            
        try:
            # Use the Atlassian MCP server to get projects
            response = await self.use_tool("atlassian", "get_jira_projects", {})
            
            if "result" in response and "projects" in response["result"]:
                projects = response["result"]["projects"]
                self.logger.info(f"Retrieved {len(projects)} Jira projects")
                return projects
            else:
                error_msg = response.get("error", {}).get("message", "Unknown error")
                self.logger.error(f"Failed to get Jira projects: {error_msg}")
                return []
                
        except Exception as e:
            self.logger.error(f"Exception getting Jira projects: {str(e)}")
            return []
    
    async def get_jira_issues(self, project_key: str) -> List[Dict[str, Any]]:
        """
        Get issues (tasks) for a specific Jira project.
        
        Args:
            project_key: The project key to get issues from
            
        Returns:
            List[Dict[str, Any]]: A list of issues or empty list if error occurs
        """
        if not self.jira_enabled or not self.mcp_client:
            self.logger.warning(f"Cannot get issues for project {project_key} - Jira integration not enabled")
            return []
            
        try:
            # Use the Atlassian MCP server to get issues
            response = await self.use_tool("atlassian", "get_jira_issues", {"project_key": project_key})
            
            if "result" in response and "issues" in response["result"]:
                issues = response["result"]["issues"]
                self.logger.info(f"Retrieved {len(issues)} Jira issues for project {project_key}")
                return issues
            else:
                error_msg = response.get("error", {}).get("message", "Unknown error")
                self.logger.error(f"Failed to get issues for project {project_key}: {error_msg}")
                return []
                
        except Exception as e:
            self.logger.error(f"Exception getting Jira issues: {str(e)}")
            return []
    
    async def create_jira_issue(self, project_key: str, summary: str, 
                              description: str = None, issue_type: str = "Task", 
                              priority: str = "Medium") -> Dict[str, Any]:
        """
        Create a new issue (task) in a Jira project.
        
        Args:
            project_key: The project key
            summary: Issue summary
            description: Issue description (optional)
            issue_type: Issue type (Task, Bug, Story, etc.)
            priority: Issue priority (Lowest, Low, Medium, High, Highest)
            
        Returns:
            Dict[str, Any]: Created issue data or error information
        """
        if not self.jira_enabled or not self.mcp_client:
            self.logger.warning(f"Cannot create issue in project {project_key} - Jira integration not enabled")
            return {"success": False, "error": "Jira integration not enabled"}
            
        try:
            # Use the Atlassian MCP server to create an issue
            params = {
                "project_key": project_key,
                "summary": summary,
                "issue_type": issue_type,
                "priority": priority
            }
            
            # Add description if provided
            if description:
                params["description"] = description
                
            response = await self.use_tool("atlassian", "create_jira_issue", params)
            
            if "result" in response and "issue" in response["result"]:
                issue_data = response["result"]["issue"]
                if issue_data.get("success", False):
                    self.logger.info(f"Created Jira issue in project {project_key}: {summary}")
                    return issue_data
                else:
                    error_msg = issue_data.get("error", "Unknown error")
                    self.logger.error(f"Failed to create issue in project {project_key}: {error_msg}")
                    return issue_data
            else:
                error_msg = response.get("error", {}).get("message", "Unknown error")
                self.logger.error(f"Failed to create issue in project {project_key}: {error_msg}")
                return {"success": False, "error": error_msg}
                
        except Exception as e:
            self.logger.error(f"Exception creating Jira issue: {str(e)}")
            return {"success": False, "error": str(e)}
    
    async def process_jira_request(self, request_text: str, details: Dict[str, Any] = None) -> str:
        """
        Process a Jira-specific request and take appropriate actions.
        
        Args:
            request_text: The original request text
            details: Additional details about the request
            
        Returns:
            str: Response with results of Jira operations
        """
        details = details or {}
        request_lower = request_text.lower()
        
        # Track Jira operations for forming a response
        operations = []
        
        try:
            # Check what kind of Jira operation is requested
            if "list" in request_lower and ("project" in request_lower or "projects" in request_lower):
                # List Jira projects
                self.logger.info("Processing request to list Jira projects")
                projects = await self.get_jira_projects()
                
                if projects:
                    operations.append(f"I found {len(projects)} projects in your Jira account:")
                    for i, project in enumerate(projects[:10], 1):
                        project_name = project.get("name", "Unknown")
                        project_key = project.get("key", "Unknown")
                        operations.append(f"{i}. {project_name} (Key: {project_key})")
                        
                    if len(projects) > 10:
                        operations.append(f"...and {len(projects) - 10} more projects.")
                else:
                    operations.append("I couldn't find any projects in your Jira account or encountered an error.")
                    
            elif "list" in request_lower and ("task" in request_lower or "issue" in request_lower):
                # Extract project key if mentioned
                project_key = None
                
                # Try to find project key in the request
                words = request_lower.split()
                for i, word in enumerate(words):
                    if word in ["project", "projects"] and i+1 < len(words):
                        # Check if next word might be a project key
                        potential_key = words[i+1].strip(",:;.'\"")
                        if potential_key.isupper() and len(potential_key) <= 10:
                            project_key = potential_key
                            break
                
                # If we couldn't find a project key, list all projects first
                if not project_key:
                    projects = await self.get_jira_projects()
                    if not projects:
                        return "I couldn't find any projects in your Jira account. Please specify a project key to list tasks from."
                    
                    # Take the first project if available
                    project_key = projects[0].get("key")
                    operations.append(f"You didn't specify a project, so I'll list tasks from the {project_key} project.")
                
                # Now get issues for this project
                self.logger.info(f"Processing request to list tasks from project {project_key}")
                issues = await self.get_jira_issues(project_key)
                
                if issues:
                    operations.append(f"I found {len(issues)} tasks in the {project_key} project:")
                    for i, issue in enumerate(issues[:10], 1):
                        key = issue.get("key", "N/A")
                        summary = issue.get("summary", "No summary")
                        status = issue.get("status", "Unknown")
                        operations.append(f"{i}. [{key}] {summary} (Status: {status})")
                        
                    if len(issues) > 10:
                        operations.append(f"...and {len(issues) - 10} more tasks.")
                else:
                    operations.append(f"I couldn't find any tasks in the {project_key} project or encountered an error.")
                    
            elif "create" in request_lower and ("task" in request_lower or "issue" in request_lower):
                # Extract project key, summary, and other details
                project_key = None
                summary = None
                description = None
                issue_type = "Task"  # Default
                
                # Try to extract project key
                words = request_lower.split()
                for i, word in enumerate(words):
                    if word in ["project", "projects"] and i+1 < len(words):
                        # Check if next word might be a project key
                        potential_key = words[i+1].strip(",:;.'\"")
                        if potential_key.isupper() and len(potential_key) <= 10:
                            project_key = potential_key
                            break
                
                # If project key wasn't found, get from first project
                if not project_key:
                    projects = await self.get_jira_projects()
                    if projects:
                        project_key = projects[0].get("key")
                        operations.append(f"You didn't specify a project, so I'll create a task in the {project_key} project.")
                    else:
                        return "I couldn't find any projects in your Jira account. Please specify a project key to create a task."
                
                # Extract task summary (everything after "with summary" or similar phrases)
                summary_indicators = [
                    "with summary", "titled", "with title", "called", "named"
                ]
                
                for indicator in summary_indicators:
                    if indicator in request_lower:
                        parts = request_text.split(indicator, 1)
                        if len(parts) > 1:
                            # Extract until next sentence or end
                            potential_summary = parts[1].strip()
                            end_markers = ['. ', '! ', '? ', '\n']
                            for marker in end_markers:
                                if marker in potential_summary:
                                    potential_summary = potential_summary.split(marker)[0].strip()
                            
                            # Clean up any quotes
                            summary = potential_summary.strip('"\'')
                            break
                
                # If still no summary, use a generic one
                if not summary:
                    summary = "Task created via AI Project Manager"
                
                # Extract description if present
                description_indicators = [
                    "with description", "described as", "with details"
                ]
                
                for indicator in description_indicators:
                    if indicator in request_lower:
                        parts = request_text.split(indicator, 1)
                        if len(parts) > 1:
                            description = parts[1].strip().strip('"\'')
                            break
                
                # Extract task type if specified
                task_types = ["Task", "Bug", "Story", "Epic"]
                for task_type in task_types:
                    if task_type.lower() in request_lower:
                        issue_type = task_type
                        break
                
                # Create the issue
                self.logger.info(f"Creating Jira issue in project {project_key}: {summary}")
                result = await self.create_jira_issue(
                    project_key=project_key,
                    summary=summary,
                    description=description,
                    issue_type=issue_type
                )
                
                if result.get("success", False):
                    issue = result.get("issue", {})
                    issue_key = issue.get("key", "Unknown")
                    operations.append(f"✅ Successfully created {issue_type} [{issue_key}]: {summary}")
                    operations.append(f"You can access it at: {self.get_jira_issue_url(issue_key)}")
                else:
                    error = result.get("error", "Unknown error")
                    operations.append(f"❌ Failed to create task: {error}")
            
            else:
                # Generic Jira request not matching specific patterns
                return self._generate_jira_help_response(request_text)
                
            # Combine all operations into a response
            return self._format_jira_response(operations)
            
        except Exception as e:
            self.logger.error(f"Error processing Jira request: {str(e)}")
            return f"I encountered an error while processing your Jira request: {str(e)}\n\nPlease try again with a more specific request or contact your system administrator if the issue persists."
    
    def _format_jira_response(self, operations: List[str]) -> str:
        """Format a list of Jira operations into a cohesive response."""
        if not operations:
            return "I processed your Jira request, but no specific actions were taken."
            
        # Build the response
        response = ["I've processed your Jira request:"]
        response.extend(operations)
        response.append("\nIs there anything else you'd like me to help you with regarding your Jira projects?")
        
        return "\n\n".join(response)
    
    def _generate_jira_help_response(self, request_text: str) -> str:
        """Generate a helpful response for generic Jira requests."""
        return f"""I understand you're asking about Jira, but I need more specific instructions.

Here are some things I can help you with:

1. List all projects in your Jira account
2. List tasks/issues in a specific project (e.g., "list tasks in project KEY")
3. Create a new task/issue in a project (e.g., "create a task in project KEY with summary Fix login bug")

Please let me know which of these actions you'd like me to perform."""
    
    def get_jira_issue_url(self, issue_key: str) -> str:
        """Generate a URL for a Jira issue based on configuration."""
        # This would ideally come from configuration, but we'll use a placeholder
        jira_base_url = "https://central-authority.atlassian.net/browse/"
        return f"{jira_base_url}{issue_key}"
    
    def process(self, request: Dict[str, Any]) -> str:
        """
        Process a categorized request to generate a project management response.
        
        Args:
            request: Dictionary containing the parsed request details
            
        Returns:
            str: The project manager's response
        """
        try:
            # Extract information from the request
            if 'original_text' in request:
                original_request = request['original_text']
            elif 'original_request' in request:
                original_request = request['original_request']
            else:
                original_request = str(request)
            
            # Get parsed information if available
            if 'parsed_request' in request:
                parsed_request = request['parsed_request']
                category = parsed_request.get("category", "General Project Inquiry")
                details = parsed_request.get("details", "No specific details provided")
            else:
                category = "General Project Inquiry"
                details = "No specific details provided"
            
            # Get context if available
            context = request.get('context', "No previous context available.")
            
            # Check if coordination plan is present
            coordination_plan = request.get('coordination_plan', None)
            supporting_responses = request.get('supporting_responses', {})
            
            # Format supporting responses if they exist
            formatted_supporting_responses = ""
            if supporting_responses:
                for agent, response in supporting_responses.items():
                    formatted_supporting_responses += f"\n--- {agent} Response ---\n{response}\n"
            else:
                formatted_supporting_responses = "No supporting agent responses available."
            
            # Check if this is a Jira-specific request
            is_jira_request = 'jira' in original_request.lower() or 'ticket' in original_request.lower()
            
            # Handle Jira-specific requests if Jira is enabled
            # NOTE: Instead of using asyncio.run(), we return a message indicating that the request
            # should be processed using the asynchronous method
            if is_jira_request and self.jira_enabled:
                self.logger.info("Detected Jira-specific request, but async processing is required")
                # For synchronous contexts, return a message indicating the request should be
                # processed via the async method
                return "This is a Jira-specific request that requires asynchronous processing. Please use the async version of this agent."
            else:
                # Generate response using the PM chain with invoke instead of run
                response = self.pm_chain.invoke({
                    "request": original_request,
                    "context": context,
                    "category": category,
                    "details": details,
                    "supporting_responses": formatted_supporting_responses
                })
            
            # Store this interaction
            self.store_memory({
                "request": original_request,
                "response": response,
                "category": category
            })
            
            return response.strip()
        except Exception as e:
            error_message = f"Error generating PM response: {str(e)}"
            self.logger.error(error_message)
            return f"I apologize, but I encountered an error while processing your request: {str(e)}"
            
    async def aprocess(self, request: Dict[str, Any]) -> str:
        """
        Process a categorized request asynchronously to generate a project management response.
        This is the async version of the process method, which can handle Jira requests.
        
        Args:
            request: Dictionary containing the parsed request details
            
        Returns:
            str: The project manager's response
        """
        try:
            # Extract information from the request
            if 'original_text' in request:
                original_request = request['original_text']
            elif 'original_request' in request:
                original_request = request['original_request']
            else:
                original_request = str(request)
            
            # Get parsed information if available
            if 'parsed_request' in request:
                parsed_request = request['parsed_request']
                category = parsed_request.get("category", "General Project Inquiry")
                details = parsed_request.get("details", "No specific details provided")
            else:
                category = "General Project Inquiry"
                details = "No specific details provided"
            
            # Get context if available
            context = request.get('context', "No previous context available.")
            
            # Check if coordination plan is present
            coordination_plan = request.get('coordination_plan', None)
            supporting_responses = request.get('supporting_responses', {})
            
            # Format supporting responses if they exist
            formatted_supporting_responses = ""
            if supporting_responses:
                for agent, response in supporting_responses.items():
                    formatted_supporting_responses += f"\n--- {agent} Response ---\n{response}\n"
            else:
                formatted_supporting_responses = "No supporting agent responses available."
            
            # Check if this is a Jira-specific request
            is_jira_request = 'jira' in original_request.lower() or 'ticket' in original_request.lower()
            
            # Handle Jira-specific requests if Jira is enabled
            if is_jira_request and self.jira_enabled:
                self.logger.info("Processing Jira-specific request asynchronously")
                # Properly await the async method
                response = await self.process_jira_request(original_request, parsed_request if 'parsed_request' in request else None)
            else:
                # Generate response using the PM chain with invoke instead of run
                response = self.pm_chain.invoke({
                    "request": original_request,
                    "context": context,
                    "category": category,
                    "details": details,
                    "supporting_responses": formatted_supporting_responses
                })
            
            # Store this interaction
            self.store_memory({
                "request": original_request,
                "response": response,
                "category": category
            })
            
            return response.strip()
        except Exception as e:
            error_message = f"Error generating PM response: {str(e)}"
            self.logger.error(error_message)
            return f"I apologize, but I encountered an error while processing your request: {str(e)}"
