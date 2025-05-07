"""
Chat Coordinator agent implementation using the modern agent structure with Pydantic and LangGraph.
This agent is responsible for routing requests to specialized agents and coordinating their responses.
"""

from typing import Any, Dict, List, Optional, Union, Set
import logging
import asyncio
from datetime import datetime

from langchain_core.tools import Tool
from langchain_core.language_models import BaseLanguageModel
from pydantic import BaseModel, Field

from ..models.agent_models import AgentConfig, AgentType, AgentResponse
from .modern_base_agent import ModernBaseAgent

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
                'sequential-thinking': ['sequentialthinking']
            },
            system_prompt="""You are the Chat Coordinator for the AI Project Management System.
            Your responsibilities include:
            
            1. Understanding user requests and determining which specialized agent can best handle them
            2. Routing requests to the appropriate agent based on their expertise
            3. Combining and synthesizing responses from multiple agents when necessary
            4. Maintaining conversation context and flow
            5. Ensuring the user receives clear and helpful responses
            
            Available specialized agents include:
            - Project Manager: Handles project planning, task management, and resource allocation
            - Research Specialist: Handles information gathering, research, and data analysis
            
            When coordinating:
            - Analyze the user request carefully to understand the underlying need
            - Select the most appropriate agent(s) based on the request type
            - Route complex requests to multiple agents when needed
            - Integrate information from multiple sources into coherent responses
            - Maintain a friendly, helpful tone while ensuring accurate information
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
        
        return tools
    
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
        """
        Route a request to a specialized agent.
        
        Args:
            agent_name: Name of the agent to route to
            request: Request to send to the agent
            
        Returns:
            Agent response
        """
        if agent_name not in self.specialized_agents:
            self.logger.warning(f"Agent not found: {agent_name}")
            return {"status": "error", "error": {"message": f"Agent '{agent_name}' not found"}}
        
        agent = self.specialized_agents[agent_name]
        self.logger.info(f"Routing request to {agent_name}: {request[:50]}...")
        
        try:
            # Process the request with the specialized agent
            response = await agent.process(request)
            
            # Update agent-specific context
            if agent_name in self.agent_context:
                self.agent_context[agent_name].append({
                    "request": request,
                    "response": response.content
                })
                # Limit context size
                if len(self.agent_context[agent_name]) > 10:
                    self.agent_context[agent_name] = self.agent_context[agent_name][-10:]
            
            return {
                "status": "success",
                "agent_name": agent_name,
                "content": response.content,
                "timestamp": str(response.timestamp)
            }
        except Exception as e:
            self.logger.error(f"Error routing request to {agent_name}: {str(e)}")
            return {"status": "error", "error": {"message": str(e)}}
    
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
        
        # Simple keyword-based routing logic
        # In a more advanced implementation, this could use an ML classifier
        request_lower = request.lower()
        
        # Project management related keywords
        pm_keywords = ["project", "task", "timeline", "schedule", "plan", "resource", 
                      "jira", "ticket", "milestone", "status", "update", "allocation"]
                      
        # Research related keywords
        research_keywords = ["research", "information", "find", "search", "analyze", 
                           "trend", "data", "documentation", "best practice", "comparison"]
        
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