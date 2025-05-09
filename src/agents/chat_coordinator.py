"""
Chat Coordinator agent implementation using the modern agent structure with Pydantic and LangGraph.
This agent is responsible for routing requests to specialized agents and coordinating their responses.
"""

from typing import Any, Dict, List, Optional, Union, Set
import logging
import asyncio
import json
from datetime import datetime

from langchain_core.tools import Tool
from langchain_core.language_models import BaseLanguageModel
from pydantic import BaseModel, Field

from ..models.agent_models import AgentConfig, AgentType, AgentResponse
from .modern_base_agent import ModernBaseAgent

# Import Atlassian-related utilities
from ..utils.atlassian_tools import JiraTools, ConfluenceTools


class ChatCoordinatorAgent(ModernBaseAgent):
    """
    Chat Coordinator agent implementation.
    Responsible for managing conversations and routing requests to specialized agents.
    """
    
    def __init__(self, llm: BaseLanguageModel, mcp_client: Optional[Any] = None, tools: Optional[List[Tool]] = None):
        """
        Initialize the Chat Coordinator agent.
        
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
        
        # Create coordination tools
        coordinator_tools = self._create_coordinator_tools()
        all_tools = (tools or []) + coordinator_tools
        
        # Create the configuration for this agent
        config = AgentConfig(
            name="Chat Coordinator",
            description="Coordinates communication and routes requests to specialized agents.",
            agent_type=AgentType.CHAT_COORDINATOR,
            available_tools={
                'memory-server': ['create_entities', 'create_relations', 'add_observations', 
                                 'read_graph', 'search_nodes', 'open_nodes'],
                'sequential-thinking': ['sequentialthinking'],
                'atlassian': ['get_jira_projects', 'create_jira_project', 'get_jira_issues', 'create_jira_issue',
                             'update_jira_progress', 'get_confluence_spaces', 'create_confluence_page']
            },
            system_prompt="""You are the Chat Coordinator for the AI Project Management System.
            Your responsibilities include:
            
            1. Understanding user requests and determining which specialized agent can best handle them
            2. Routing requests to the appropriate agent based on their expertise
            3. Combining and synthesizing responses from multiple agents when necessary
            4. Maintaining conversation context and flow
            5. Ensuring the user receives clear and helpful responses
            6. Managing Jira projects and issues through the Atlassian integration
            7. Creating and updating Confluence documentation as needed
            
            Available specialized agents include:
            - Project Manager: Handles project planning, task management, and resource allocation
            - Research Specialist: Handles information gathering, research, and data analysis
            
            When coordinating:
            - Analyze the user request carefully to understand the underlying need
            - Select the most appropriate agent(s) based on the request type
            - Route complex requests to multiple agents when needed
            - Integrate information from multiple sources into coherent responses
            - Maintain a friendly, helpful tone while ensuring accurate information
            
            When Jira is mentioned:
            - Help users create and manage projects in Jira
            - Assist with creating, updating, and tracking issues
            - Provide updates on project status and task progress
            
            When Confluence is mentioned:
            - Help users create and manage documentation in Confluence
            - Create pages with formatted content from markdown or text
            - Link Jira issues to related Confluence documentation
            """
        )
        
        # Initialize the base agent
        super().__init__(llm=llm, config=config, tools=all_tools, mcp_client=mcp_client)
        
        # Dictionary to store references to specialized agents
        self.specialized_agents: Dict[str, ModernBaseAgent] = {}
        
        # Track agent-specific context for conversation continuity
        self.agent_context: Dict[str, List[Dict[str, str]]] = {}
        
        self.logger = logging.getLogger("agent.chat_coordinator")
        self.logger.info("Chat Coordinator agent initialized")
    
    def _create_coordinator_tools(self) -> List[Tool]:
        """
        Create tools for coordination capabilities.
        
        Returns:
            List of LangChain tools for coordination
        """
        tools = []
        
        # Route request tool
        tools.append(
            Tool(
                name="route_request",
                func=self._route_request,
                description="Route a request to a specialized agent. Requires agent_name and request parameters."
            )
        )
        
        # Multi-agent request tool
        tools.append(
            Tool(
                name="multi_agent_request",
                func=self._multi_agent_request,
                description="Send a request to multiple agents and combine their responses. Requires agent_names list and request."
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
        
        # Add Confluence tools if available
        if self.confluence_tools:
            tools.append(
                Tool(
                    name="get_confluence_spaces",
                    func=self._get_confluence_spaces,
                    description="Get all available Confluence spaces."
                )
            )
            
            tools.append(
                Tool(
                    name="create_confluence_page",
                    func=self._create_confluence_page,
                    description="Create a new Confluence page. Requires space_key, title, and content."
                )
            )
            
            tools.append(
                Tool(
                    name="markdown_to_confluence",
                    func=self._markdown_to_confluence,
                    description="Convert Markdown content to Confluence storage format. Requires markdown_content."
                )
            )
        
        return tools
    
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
    
    async def _create_jira_project(
        self, 
        name: str, 
        key: str = None, 
        description: str = None
    ) -> Dict[str, Any]:
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
    
    async def _get_jira_issues(
        self, 
        project_key: str = None, 
        jql: str = None
    ) -> Dict[str, Any]:
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
    
    async def _create_jira_issue(
        self, 
        project_key: str, 
        summary: str, 
        description: str = None,
        issue_type: str = "Task", 
        priority: str = "Medium"
    ) -> Dict[str, Any]:
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
    
    async def _update_jira_progress(
        self, 
        issue_key: str, 
        progress: int, 
        note: str = None
    ) -> Dict[str, Any]:
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
    
    async def _get_confluence_spaces(self) -> Dict[str, Any]:
        """Get all available Confluence spaces."""
        try:
            if not self.confluence_tools:
                return {"status": "error", "error": "Confluence tools not initialized"}
                
            spaces = await self.confluence_tools.get_spaces()
            return {
                "status": "success",
                "spaces": spaces
            }
        except Exception as e:
            self.logger.error(f"Error getting Confluence spaces: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def _create_confluence_page(
        self, 
        space_key: str, 
        title: str, 
        content: str,
        is_markdown: bool = False
    ) -> Dict[str, Any]:
        """Create a new Confluence page."""
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
            self.logger.error(f"Error creating Confluence page: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def _markdown_to_confluence(self, markdown_content: str) -> Dict[str, Any]:
        """Convert Markdown content to Confluence storage format."""
        try:
            if not self.confluence_tools:
                return {"status": "error", "error": "Confluence tools not initialized"}
                
            converted_content = self.confluence_tools.markdown_to_confluence_storage_format(markdown_content)
            return {
                "status": "success",
                "content": converted_content
            }
        except Exception as e:
            self.logger.error(f"Error converting markdown to Confluence format: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    def add_agent(self, name: str, agent: ModernBaseAgent) -> None:
        """
        Register a specialized agent with the coordinator.
        
        Args:
            name: Name to reference the agent by
            agent: Agent instance
        """
        self.specialized_agents[name] = agent
        self.agent_context[name] = []
        self.logger.info(f"Registered specialized agent: {name}")
    
    def get_available_agents(self) -> Set[str]:
        """
        Get the set of available specialized agent names.
        
        Returns:
            Set of available agent names
        """
        return set(self.specialized_agents.keys())
    
    async def _route_request(self, agent_name: str, request: str) -> Dict[str, Any]:
        """Route a request to a specific agent."""
        try:
            if agent_name not in self.specialized_agents:
                raise ValueError(f"Agent {agent_name} not found")
                
            agent = self.specialized_agents[agent_name]
            
            # Initialize context for this agent if not exists
            if agent_name not in self.agent_context:
                self.agent_context[agent_name] = []
                
            # Add request to context
            self.agent_context[agent_name].append({
                "role": "user",
                "content": request
            })
            
            # Get response from agent
            response = await agent.process(request)
            
            # Clean response content before adding to context
            cleaned_content = self._clean_agent_response(response.content)
            
            # Add response to context
            self.agent_context[agent_name].append({
                "role": "assistant",
                "content": cleaned_content
            })
            
            # Maintain context window
            if len(self.agent_context[agent_name]) > 10:
                self.agent_context[agent_name] = self.agent_context[agent_name][-10:]
            
            return {
                "status": "success",
                "agent_name": agent_name,
                "content": cleaned_content,
                "timestamp": str(response.timestamp)
            }
            
        except Exception as e:
            self.logger.error(f"Error routing request to {agent_name}: {str(e)}")
            return {"status": "error", "error": {"message": str(e)}}

    def _clean_agent_response(self, content: str) -> str:
        """Clean agent response by removing inter-agent dialogue markers."""
        if not content:
            return ""
            
        lines = content.split('\n')
        final_lines = []
        
        for line in lines:
            line = line.strip()
            if not line:
                continue
                
            # Skip lines with dialogue markers or metadata
            if any(marker in line for marker in [
                "Human:", "User:", "AI:", "Machine:", "System:", "Assistant:",
                "Agent thinking:", "Processing request:", "Adding agent message from"
            ]):
                continue
                
            final_lines.append(line)
            
        return "\n".join(final_lines).strip()
    
    async def _multi_agent_request(self, agent_names: List[str], request: str) -> Dict[str, Any]:
        """
        Send a request to multiple agents and combine their responses.
        
        Args:
            agent_names: List of agent names to route to
            request: Request to send to the agents
            
        Returns:
            Combined response from all agents
        """
        self.logger.info(f"Multi-agent request to {', '.join(agent_names)}: {request[:50]}...")
        
        # Verify all agents exist
        for name in agent_names:
            if name not in self.specialized_agents:
                return {"status": "error", "error": {"message": f"Agent '{name}' not found"}}
        
        tasks = []
        for name in agent_names:
            task = asyncio.create_task(self._route_request(name, request))
            tasks.append((name, task))
        
        # Wait for all agent responses
        responses = {}
        for name, task in tasks:
            try:
                result = await task
                responses[name] = result
            except Exception as e:
                self.logger.error(f"Error getting response from {name}: {str(e)}")
                responses[name] = {"status": "error", "error": {"message": str(e)}}
        
        return {
            "status": "success",
            "multi_agent": True,
            "responses": responses,
            "timestamp": str(datetime.now())
        }
    
    async def route_by_expertise(self, request: str) -> AgentResponse:
        """
        Intelligently route a request to the most appropriate agent based on the request content.
        
        Args:
            request: User request to route
            
        Returns:
            Response from the selected agent
        """
        self.logger.info(f"Routing request by expertise: {request[:50]}...")
        
        # Enhanced keyword-based routing logic including Atlassian-related keywords
        request_lower = request.lower()
        
        # Project management / Jira related keywords
        pm_keywords = ["project", "task", "timeline", "schedule", "plan", "resource", 
                      "jira", "ticket", "milestone", "status", "update", "allocation",
                      "issue", "sprint", "kanban", "board", "backlog", "epic"]
                      
        # Research / Confluence related keywords
        research_keywords = ["research", "information", "find", "search", "analyze", 
                           "trend", "data", "documentation", "best practice", "comparison",
                           "confluence", "wiki", "document", "page", "space", "knowledge base"]
        
        # Direct Jira-related request
        jira_keywords = ["jira", "project", "issue", "ticket", "sprint", "kanban", "board"]
        
        # Direct Confluence-related request
        confluence_keywords = ["confluence", "wiki", "page", "space", "documentation"]
        
        # Check if this is a direct Jira or Confluence request first
        is_jira_request = any(keyword in request_lower for keyword in jira_keywords)
        is_confluence_request = any(keyword in request_lower for keyword in confluence_keywords)
        
        # If it's a direct Jira or Confluence request and we have the tools, handle directly
        if (is_jira_request and self.jira_tools) or (is_confluence_request and self.confluence_tools):
            # We'll handle it directly with our tools
            response = await self.process(request)
            return response
        
        # Otherwise, proceed with regular agent routing
        # Count matches
        pm_score = sum(1 for keyword in pm_keywords if keyword in request_lower)
        research_score = sum(1 for keyword in research_keywords if keyword in request_lower)
        
        # Determine the most appropriate agent
        if pm_score > research_score and "project_manager" in self.specialized_agents:
            agent_name = "project_manager"
        elif research_score > 0 and "research_specialist" in self.specialized_agents:
            agent_name = "research_specialist"
        # If scores are tied or no clear winner, default to project manager
        elif "project_manager" in self.specialized_agents:
            agent_name = "project_manager"
        # If no project manager, use any available agent
        elif self.specialized_agents:
            agent_name = next(iter(self.specialized_agents.keys()))
        else:
            # No specialized agents available, handle directly
            self.logger.warning("No specialized agents available, handling request directly")
            return await self.process(request)
        
        # Route to the selected agent
        self.logger.info(f"Selected agent by expertise: {agent_name}")
        route_result = await self._route_request(agent_name, request)
        
        if route_result.get("status") == "success":
            return AgentResponse(
                agent_name=route_result.get("agent_name", agent_name),
                content=route_result.get("content", ""),
                timestamp=datetime.now()
            )
        else:
            error_msg = route_result.get("error", {}).get("message", "Unknown routing error")
            return AgentResponse(
                agent_name=self.name,
                content="",
                error=error_msg,
                timestamp=datetime.now()
            )
    
    async def process(self, request: str) -> AgentResponse:
        """
        Process a request with appropriate routing or direct handling.
        
        Args:
            request: The request to process
            
        Returns:
            The agent's response
        """
        # If the request explicitly mentions routing to a specific agent
        agent_prefixes = {
            "project manager:": "project_manager",
            "research specialist:": "research_specialist"
        }
        
        for prefix, agent_name in agent_prefixes.items():
            if request.lower().startswith(prefix):
                if agent_name in self.specialized_agents:
                    # Strip the prefix and route to the specified agent
                    clean_request = request[len(prefix):].strip()
                    route_result = await self._route_request(agent_name, clean_request)
                    
                    if route_result.get("status") == "success":
                        return AgentResponse(
                            agent_name=route_result.get("agent_name", agent_name),
                            content=route_result.get("content", ""),
                            timestamp=datetime.now()
                        )
                    else:
                        error_msg = route_result.get("error", {}).get("message", "Unknown routing error")
                        return AgentResponse(
                            agent_name=self.name,
                            content="",
                            error=error_msg,
                            timestamp=datetime.now()
                        )
        
        # Check for Atlassian-specific keywords to handle directly
        request_lower = request.lower()
        
        # Atlassian keywords
        jira_keywords = ["jira", "project", "issue", "ticket", "sprint", "kanban", "board"]
        confluence_keywords = ["confluence", "wiki", "page", "space", "documentation"]
        
        # If it contains Atlassian keywords and we have the tools, handle directly
        if any(keyword in request_lower for keyword in jira_keywords + confluence_keywords) and (
            self.jira_tools or self.confluence_tools
        ):
            # Let the LLM decide how to process this with our Atlassian tools
            self.logger.info("Handling Atlassian-related request directly")
            return await super().process(request)
        
        # Requests that might benefit from multiple agents
        multi_agent_keywords = ["compare", "both", "all agents", "everyone"]
        if any(keyword in request.lower() for keyword in multi_agent_keywords) and len(self.specialized_agents) > 1:
            self.logger.info("Using multi-agent approach")
            agent_names = list(self.specialized_agents.keys())
            multi_result = await self._multi_agent_request(agent_names, request)
            
            if multi_result.get("status") == "success":
                # Combine responses from all agents
                combined_content = "Combined input from multiple agents:\n\n"
                for name, response in multi_result.get("responses", {}).items():
                    if response.get("status") == "success":
                        combined_content += f"--- {name.replace('_', ' ').title()} ---\n"
                        combined_content += response.get("content", "") + "\n\n"
                
                return AgentResponse(
                    agent_name=self.name,
                    content=combined_content.strip(),
                    timestamp=datetime.now()
                )
        
        # Otherwise, route based on expertise
        return await self.route_by_expertise(request)