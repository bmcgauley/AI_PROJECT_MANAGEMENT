"""
Chat Coordinator Agent for the AI Project Management System.
Acts as the main interface that handles user interactions and orchestrates communication.
"""

from typing import Any, Dict, List
import json
import asyncio # Added asyncio
import inspect # Added inspect
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough

from src.agents.base_agent import BaseAgent
from src.agents.request_parser import RequestParserAgent

class ChatCoordinatorAgent(BaseAgent):
    """
    Chat Coordinator Agent that serves as the main interface for users.
Handles all user interactions and orchestrates communication between specialized agents.
"""

from typing import Any, Dict, List, Optional # Added Optional
import json
import asyncio # Added asyncio
import inspect # Added inspect
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough

from src.agents.base_agent import BaseAgent
from src.agents.request_parser import RequestParserAgent

class ChatCoordinatorAgent(BaseAgent):
    """
    Chat Coordinator Agent that serves as the main interface for users.
    Handles all user interactions and orchestrates communication between specialized agents.
    """
    
    def __init__(self, llm, mcp_client: Optional[Any] = None, agents=None): # Added mcp_client
        """
        Initialize the Chat Coordinator agent.
        
        Args:
            llm: Language model to use for responses
            mcp_client: Optional client for interacting with MCP servers.
            agents: Optional dictionary of specialized agents
        """
        super().__init__(
            llm=llm,
            name="Chat Coordinator",
            description="Main interface that handles user interactions and orchestrates agent communication",
            mcp_client=mcp_client # Pass mcp_client to base
        )
        
        # Initialize with empty agents dictionary if None provided
        self.agents = agents if agents is not None else {}
        
        # Add RequestParserAgent automatically, passing mcp_client
        if 'request_parser' not in self.agents:
             # Assuming RequestParserAgent also needs mcp_client, update its init if necessary
            self.agents['request_parser'] = RequestParserAgent(llm=llm, mcp_client=mcp_client)
        
        # Define the prompt template for coordination
        self.coordinator_prompt = PromptTemplate(
            input_variables=["request", "context", "available_agents"],
            template="""
            You are the Chat Coordinator, the main interface for an AI Project Management System.
            Your role is to:
            1. Understand the user's request
            2. Decide which specialized agent(s) should handle the request
            3. Provide a clear, concise response back to the user
            
            Available agents: {available_agents}
            
            Context from previous interactions:
            {context}
            
            User request:
            {request}
            
            First, determine which specialized agent(s) should handle this request.
            Then, formulate a complete response plan in the following JSON format:
            {{
                "understanding": "brief restatement of what the user is asking for",
                "primary_agent": "name of the primary agent that should handle this",
                "supporting_agents": ["list", "of", "supporting", "agents"],
                "plan": "step-by-step plan for how you'll process this request",
                "clarification_needed": false,
                "clarification_questions": ["question1", "question2"]
            }}
            
            If clarification is needed from the user, set clarification_needed to true and list the questions.
            
            Generate only the JSON response, nothing else.
            """
        )
        
        # Create the coordinator chain using the newer RunnableSequence approach
        self.coordinator_chain = self.coordinator_prompt | llm
    
    def add_agent(self, name: str, agent: BaseAgent) -> None:
        """
        Add a specialized agent to the coordinator.
        
        Args:
            name: Name identifier for the agent
            agent: The agent instance to add
        """
        self.agents[name] = agent
        self.logger.info(f"Added agent: {name}")
    
    def get_available_agents(self) -> str:
        """
        Get a formatted string listing all available specialized agents.
        
        Returns:
            String describing available agents
        """
        agent_descriptions = []
        for name, agent in self.agents.items():
            if name != 'request_parser':  # Skip the parser in the list of specialized agents
                agent_descriptions.append(f"- {agent.name}: {agent.description}")
        
        return "\n".join(agent_descriptions)
    
    def get_context(self, limit: int = 5) -> str:
        """
        Get recent context from memory for decision making.
        
        Args:
            limit: Number of recent interactions to include
            
        Returns:
            Formatted string with recent context
        """
        recent_memory = self.get_memory(limit)
        if not recent_memory:
            return "No previous context available."
        
        context_parts = []
        for i, memory_item in enumerate(recent_memory):
            if 'request' in memory_item and 'response' in memory_item:
                context_parts.append(f"Interaction {i+1}:")
                context_parts.append(f"User: {memory_item['request']}")
                context_parts.append(f"System: {memory_item['response']}\n")
        
        return "\n".join(context_parts)
    
    async def process(self, request: Dict[str, Any]) -> Dict[str, Any]: # Changed to async def
        """
        Process a user request asynchronously, coordinate with specialized agents, and return a response.
        
        Args:
            request: Dictionary containing the request details
            
        Returns:
            Dictionary with the response and processing metadata
        """
        # Extract the user's request text
        if isinstance(request, dict) and 'text' in request:
            user_request = request['text']
        else:
            user_request = str(request)
        
        self.logger.info(f"Processing request: {user_request[:50]}...")
        
        try:
            # Parse the request to understand what it's about
            if 'request_parser' in self.agents:
                parsed_request = self.agents['request_parser'].process(user_request)
            else:
                parsed_request = {"relevant": True, "category": "General Request"}
            
            # Get coordinator's plan for handling this request using invoke instead of run
            coordinator_response = self.coordinator_chain.invoke({
                "request": user_request,
                "context": self.get_context(),
                "available_agents": self.get_available_agents()
            })
            
            # Try to parse the JSON response
            try:
                # Clean up the response if it contains markdown code blocks
                if "```json" in coordinator_response:
                    coordinator_response = coordinator_response.split("```json")[1].split("```")[0].strip()
                elif "```" in coordinator_response:
                    coordinator_response = coordinator_response.split("```")[1].split("```")[0].strip()
                
                plan = json.loads(coordinator_response.strip())
            except (json.JSONDecodeError, IndexError) as e:
                self.logger.error(f"Error parsing coordinator response: {str(e)}")
                plan = {
                    "understanding": "Failed to properly parse the request",
                    "primary_agent": "chat_coordinator",
                    "supporting_agents": [],
                    "plan": "Handle the request directly",
                    "clarification_needed": False
                }
            
            # Check if clarification is needed
            if plan.get("clarification_needed", False):
                response = {
                    "response": "I need some clarification before I can help you properly.",
                    "clarification_questions": plan.get("clarification_questions", ["Could you provide more details?"]),
                    "status": "clarification_needed"
                }
                self.store_memory({"request": user_request, "response": response["response"], "needs_clarification": True})
                return response
            
            # Identify which agent should handle this request
            primary_agent_name = plan.get("primary_agent", "").lower().replace(" ", "_")
            
            # If the primary agent exists, delegate the request to it
            if primary_agent_name in self.agents:
                primary_agent = self.agents[primary_agent_name]
                
                # Enrich the request with parsing results and plan
                enriched_request = {
                    "original_text": user_request,
                    "parsed_request": parsed_request,
                    "plan": plan,
                    "context": self.get_context()
                }
                
                # Get response from the primary agent, handling both sync and async methods
                if inspect.iscoroutinefunction(primary_agent.process):
                    agent_response = await primary_agent.process(enriched_request)
                else:
                    # Run synchronous function in a thread pool to avoid blocking asyncio loop
                    # Note: This requires the event loop to be running.
                    loop = asyncio.get_running_loop()
                    agent_response = await loop.run_in_executor(None, primary_agent.process, enriched_request)

                # Store this interaction in memory
                self.store_memory({
                    "request": user_request,
                    "primary_agent": primary_agent_name,
                    "response": agent_response
                })
                
                return {
                    "response": agent_response,
                    "processed_by": primary_agent_name,
                    "status": "success"
                }
            else:
                # Handle the case where the identified agent doesn't exist
                fallback_response = f"I understood you want help with {plan.get('understanding', 'your request')}, but I don't have the specialized agent needed to handle this properly. I'll do my best to assist directly or can route this to a different agent if you prefer."
                
                self.store_memory({
                    "request": user_request,
                    "response": fallback_response,
                    "missing_agent": primary_agent_name
                })
                
                return {
                    "response": fallback_response,
                    "status": "fallback",
                    "missing_agent": primary_agent_name
                }
                
        except Exception as e:
            error_message = f"Error processing request: {str(e)}"
            self.logger.error(error_message)
            
            self.store_memory({
                "request": user_request,
                "error": error_message
            })
            
            return {
                "response": "I encountered an error while processing your request. Please try again or rephrase your question.",
                "status": "error",
                "error": str(e)
            }
