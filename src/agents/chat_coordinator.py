"""
Chat Coordinator Agent for the AI Project Management System.
Acts as the main interface that handles user interactions and orchestrates communication.
"""

from typing import Any, Dict, List, Optional
import json
import asyncio
import inspect
import time
import backoff  # Will add to requirements.txt
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough

from src.agents.base_agent import BaseAgent
from src.agents.request_parser import RequestParserAgent

class ChatCoordinatorAgent(BaseAgent):
    """
    Chat Coordinator Agent that serves as the main interface for users.
    Handles all user interactions and orchestrates communication between specialized agents.
    """
    
    def __init__(self, llm, mcp_client: Optional[Any] = None, agents=None):
        """Initialize the Chat Coordinator agent."""
        super().__init__(
            llm=llm,
            name="Chat Coordinator",
            description="Main interface that handles user interactions and orchestrates agent communication",
            mcp_client=mcp_client
        )
        
        # Initialize with empty agents dictionary if None provided
        self.agents = agents if agents is not None else {}
        
        # Add RequestParserAgent automatically
        if 'request_parser' not in self.agents:
            self.agents['request_parser'] = RequestParserAgent(llm=llm, mcp_client=mcp_client)
        
        # Define the prompt template for coordination
        self.coordinator_prompt = PromptTemplate(
            input_variables=["request", "category", "available_agents"],
            template="""You are the Chat Coordinator for an AI Project Management System.
            Based on the parsed category and request, determine which specialized agent(s) should handle it.
            
            Available agents:
            {available_agents}
            
            Request category: {category}
            User request: {request}
            
            Respond with ONLY a valid JSON object in this format:
            {{
                "understanding": "<brief restatement of request>",
                "primary_agent": "<name of main agent to handle this>",
                "supporting_agents": ["<agent1>", "<agent2>"],  // can be empty list
                "plan": "<step-by-step plan>"
            }}"""
        )
        
        # Create the coordinator chain
        self.coordinator_chain = self.coordinator_prompt | llm

    def add_agent(self, name: str, agent: BaseAgent) -> None:
        """Add a specialized agent to the coordinator."""
        self.agents[name] = agent
        self.logger.info(f"Added agent: {name}")
    
    def get_available_agents(self) -> str:
        """Get formatted string listing available specialized agents."""
        agent_descriptions = []
        for name, agent in self.agents.items():
            if name != 'request_parser':
                agent_descriptions.append(f"{agent.name}: {agent.description}")
        return "\n".join(agent_descriptions)
    
    def get_context(self, limit: int = 5) -> str:
        """Get recent context from memory."""
        recent_memory = self.get_memory(limit)
        if not recent_memory:
            return "No previous context available."
        
        context_parts = []
        for i, memory_item in enumerate(recent_memory):
            if 'request' in memory_item and 'response' in memory_item:
                context_parts.append(f"User: {memory_item['request']}")
                context_parts.append(f"System: {memory_item['response']}\n")
        
        return "\n".join(context_parts)

    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    async def _get_coordinator_plan(self, user_request: str, category: str) -> Dict[str, Any]:
        """Get coordination plan with retries."""
        try:
            response = await self.coordinator_chain.ainvoke({
                "request": user_request,
                "category": category,
                "available_agents": self.get_available_agents()
            })
            
            # Clean and parse JSON response
            if isinstance(response, dict):
                return response
            
            # Extract JSON if wrapped in code blocks
            response_text = response
            if "```json" in response_text:
                response_text = response_text.split("```json")[1].split("```")[0]
            elif "```" in response_text:
                response_text = response_text.split("```")[1].split("```")[0]
            
            return json.loads(response_text.strip())
            
        except Exception as e:
            self.logger.error(f"Error getting coordinator plan: {str(e)}")
            raise

    async def process(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """Process a user request asynchronously and return a response."""
        try:
            # Extract request text
            user_request = request.get('text', str(request))
            self.logger.info(f"Processing request: {user_request[:50]}...")
            
            # 1. Parse request through RequestParser
            parsed_request = self.agents['request_parser'].process(user_request)
            category = parsed_request.get('category', 'General Request')
            
            # 2. Get coordination plan with retries
            try:
                plan = await self._get_coordinator_plan(user_request, category)
            except Exception as e:
                self.logger.error(f"Failed to get coordination plan: {str(e)}")
                # Fallback to project manager
                plan = {
                    "understanding": user_request,
                    "primary_agent": "project_manager",
                    "supporting_agents": [],
                    "plan": "Direct request to project manager due to coordination error"
                }
            
            # 3. Route to primary agent
            primary_agent_name = plan['primary_agent'].lower().replace(' ', '_')
            if primary_agent_name in self.agents:
                primary_agent = self.agents[primary_agent_name]
                
                # Prepare enriched request with context
                enriched_request = {
                    "text": user_request,
                    "category": category,
                    "parsed_request": parsed_request,
                    "context": self.get_context(),
                    "supporting_agents": plan.get('supporting_agents', [])
                }
                
                # Handle both sync and async agent processes
                if inspect.iscoroutinefunction(primary_agent.process):
                    response = await primary_agent.process(enriched_request)
                else:
                    loop = asyncio.get_running_loop()
                    response = await loop.run_in_executor(
                        None, primary_agent.process, enriched_request
                    )
                
                # Store interaction
                self.store_memory({
                    "request": user_request,
                    "response": response,
                    "primary_agent": primary_agent_name
                })
                
                # Return formatted response
                return {
                    "status": "success",
                    "response": response,
                    "processed_by": primary_agent_name
                }
            
            else:
                # Handle missing agent case
                error_msg = f"Agent '{primary_agent_name}' not found. Falling back to project manager."
                self.logger.warning(error_msg)
                
                # Fall back to project manager
                fallback_response = await self.agents['project_manager'].process({
                    "text": user_request,
                    "category": category,
                    "parsed_request": parsed_request,
                    "context": self.get_context()
                })
                
                self.store_memory({
                    "request": user_request,
                    "response": fallback_response,
                    "primary_agent": "project_manager",
                    "fallback": True
                })
                
                return {
                    "status": "success",
                    "response": fallback_response,
                    "processed_by": "project_manager",
                    "note": "Fell back to project manager"
                }
                
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            self.logger.error(error_msg)
            
            self.store_memory({
                "request": user_request,
                "error": error_msg
            })
            
            return {
                "status": "error",
                "error": str(e),
                "response": "I encountered an error processing your request. The project manager will be notified."
            }
