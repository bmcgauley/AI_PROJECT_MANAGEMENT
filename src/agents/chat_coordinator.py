"""
Chat Coordinator Agent for the AI Project Management System.
Acts as the main interface that handles user interactions and orchestrates communication.
"""

from typing import Any, Dict, List, Optional, Callable
import json
import asyncio
import inspect
import time
import uuid
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
            name="AI Assistant",
            description="Your friendly AI assistant that coordinates all specialized agents",
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
            
            IMPORTANT RULES:
            1. You MUST select "primary_agent" ONLY from the exact list of available agents above.
            2. DO NOT invent new agent names or use creative variations like "Chaotic Coordinator".
            3. "supporting_agents" must be an array of agent names from the available list.
            4. Use empty arrays [] for empty lists, not null values.
            5. Your response must be valid JSON without ANY comments.
            
            Respond with ONLY a valid JSON object in this exact format:
            {{
                "understanding": "brief restatement of request",
                "primary_agent": "name of main agent to handle this",
                "supporting_agents": [],
                "plan": "step-by-step plan",
                "clarification_needed": false,
                "clarification_questions": []
            }}
            """
        )
        
        # Create the coordinator chain
        self.coordinator_chain = self.coordinator_prompt | llm
        
        # Event callback for WebSocket notifications
        self.event_callback = None
        
        # Memory for conversation history
        self.memory = []
        
        # Natural language interface prompt
        self.interface_prompt = PromptTemplate(
            input_variables=["response", "request"],
            template="""You are a helpful AI assistant for project management.
            
            The user asked: {request}
            
            The specialized agent provided this response: {response}
            
            Present this information in a friendly, conversational tone. Focus on being helpful
            and professional. Use markdown formatting when useful.
            """
        )
        
        # Create the interface chain
        self.interface_chain = self.interface_prompt | llm
        
    def set_event_callback(self, callback: Callable) -> None:
        """Set callback for real-time event notifications."""
        self.event_callback = callback

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
    
    async def _emit_event(self, event_type: str, **kwargs) -> None:
        """Emit event to WebSocket if callback is set."""
        if self.event_callback:
            # Create a task for the async callback to avoid blocking
            asyncio.create_task(self.event_callback(event_type, **kwargs))
    
    def store_memory(self, item: Dict[str, Any]) -> None:
        """Store an item in memory."""
        self.memory.append(item)
        # Keep only the most recent conversations (limit to 10)
        if len(self.memory) > 10:
            self.memory = self.memory[-10:]
    
    def get_memory(self, limit: int = None) -> List[Dict[str, Any]]:
        """Get items from memory with optional limit."""
        if limit is None:
            return self.memory
        return self.memory[-limit:]
    
    @backoff.on_exception(backoff.expo, Exception, max_tries=3)
    async def _get_coordinator_plan(self, user_request: str, category: str, request_id: str) -> Dict[str, Any]:
        """Get coordination plan with retries."""
        await self._emit_event("agent_thinking", 
            agent="AI Assistant",
            thinking=f"Analyzing request: '{user_request}'\nCategory: {category}\nDetermining which agents should handle this...",
            request_id=request_id
        )
        
        try:
            # Get the available agents
            available_agents = self.get_available_agents()
            
            # Run the coordination chain
            result = await asyncio.to_thread(
                self.coordinator_chain.invoke,
                {"request": user_request, "category": category, "available_agents": available_agents}
            )
            
            # Clean up the result - remove any leading/trailing text and code blocks
            cleaned_result = result
            
            # Remove markdown code blocks if present
            import re
            cleaned_result = re.sub(r'```json\s*|\s*```', '', cleaned_result)
            
            # Parse the JSON result
            try:
                # First attempt: direct parsing
                plan = json.loads(cleaned_result)
                return plan
            except json.JSONDecodeError:
                # Second attempt: try to extract JSON from the response
                self.logger.warning("Failed to parse coordinator response as JSON, attempting to extract JSON")
                
                # Look for the most promising JSON-like structure
                json_matches = re.findall(r'\{(?:[^{}]|(?:\{[^{}]*\}))*\}', cleaned_result, re.DOTALL)
                
                if json_matches:
                    # Try each match until we find valid JSON
                    for potential_json in json_matches:
                        try:
                            # Remove any line comments (// ...)
                            clean_json = re.sub(r'//.*?(\n|$)', '', potential_json)
                            # Replace any remaining comment-like structures
                            clean_json = re.sub(r'/\*.*?\*/', '', clean_json, flags=re.DOTALL)
                            # Try to parse the cleaned JSON
                            plan = json.loads(clean_json)
                            return plan
                        except json.JSONDecodeError:
                            continue
                
                # If we're here, all extraction attempts failed
                self.logger.error(f"Failed to extract valid JSON. Raw response: {result}")
                raise ValueError("Could not extract valid JSON from coordinator response")
        except Exception as e:
            self.logger.error(f"Error getting coordination plan: {str(e)}")
            raise

    async def _get_agent_response(self, agent_name: str, request_data: Dict[str, Any], request_id: str) -> str:
        """Get response from a specific agent."""
        if agent_name.lower() not in self.agents:
            for name in self.agents.keys():
                if agent_name.lower() in name.lower():
                    agent_name = name
                    break
            else:
                return f"Agent '{agent_name}' not found."
        
        agent = self.agents[agent_name.lower()]
        await self._emit_event("agent_processing", 
            agent=agent.name,
            message=f"Processing request: \"{request_data.get('original_text', '')}\"",
            request_id=request_id
        )
        
        # Process the request through the agent
        if inspect.iscoroutinefunction(agent.process):
            response = await agent.process(request_data)
        else:
            response = agent.process(request_data)
        
        await self._emit_event("agent_response", 
            agent=agent.name,
            response=response,
            request_id=request_id
        )
        
        return response

    async def _process_with_delegations(self, user_request: str, parsed_data: Dict[str, Any], coordination_plan: Dict[str, Any], request_id: str) -> str:
        """Process request with full delegation flow to primary and supporting agents."""
        primary_agent = coordination_plan["primary_agent"]
        supporting_agents = coordination_plan["supporting_agents"]
        plan = coordination_plan["plan"]
        
        # Prepare request data with all context
        request_data = {
            "original_text": user_request,
            "parsed_request": parsed_data,
            "context": self.get_context(),
            "coordination_plan": coordination_plan
        }
        
        # First, get response from primary agent (usually Project Manager)
        await self._emit_event("workflow_step", 
            message=f"Routing request to primary agent: {primary_agent}",
            request_id=request_id
        )
        
        primary_response = await self._get_agent_response(primary_agent.lower(), request_data, request_id)
        
        # If there are supporting agents, process with them and collect their responses
        supporting_responses = {}
        if supporting_agents:
            await self._emit_event("workflow_step", 
                message=f"Delegating to supporting agents: {', '.join(supporting_agents)}",
                request_id=request_id
            )
            
            # Add primary response to context for supporting agents
            request_data["primary_response"] = primary_response
            
            # Process with each supporting agent
            for agent_name in supporting_agents:
                supporting_response = await self._get_agent_response(agent_name.lower(), request_data, request_id)
                supporting_responses[agent_name] = supporting_response
        
        # If we have supporting responses, send them back to primary agent for integration
        final_response = primary_response
        if supporting_responses:
            await self._emit_event("workflow_step", 
                message="Integrating responses from all agents",
                request_id=request_id
            )
            
            # Add supporting responses to request data
            request_data["supporting_responses"] = supporting_responses
            
            # Get final integrated response from primary agent
            integration_response = await self._get_agent_response(primary_agent.lower(), request_data, request_id)
            final_response = integration_response
        
        # Transform the technical response into natural language
        await self._emit_event("workflow_step",
            message="Creating user-friendly response",
            request_id=request_id
        )
        
        natural_response = await asyncio.to_thread(
            self.interface_chain.invoke,
            {"response": final_response, "request": user_request}
        )
        
        return natural_response

    async def process_message(self, user_request: str) -> Dict[str, Any]:
        """
        Process a user message through the multi-agent system following the correct flow:
        1. Request Parser categorizes the request
        2. Coordinator creates a plan
        3. Project Manager receives request and delegates to specialized agents
        4. Project Manager integrates responses and returns final response
        5. Chat Coordinator converts to natural language
        """
        request_id = str(uuid.uuid4())
        self.logger.info(f"Processing new request ID: {request_id}")
        
        try:
            # Step 1: Parse the request
            await self._emit_event("workflow_step", 
                message="Parsing request to understand intent and category",
                request_id=request_id
            )
            
            request_parser = self.agents["request_parser"]
            if inspect.iscoroutinefunction(request_parser.process):
                parsed_data = await request_parser.process({"text": user_request})
            else:
                parsed_data = request_parser.process({"text": user_request})
            
            # Extract category from parsed data
            category = "General Inquiry"
            if isinstance(parsed_data, dict):
                category = parsed_data.get("category", "General Inquiry")
            
            # Step 2: Get coordination plan
            await self._emit_event("workflow_step", 
                message="Creating coordination plan for request",
                request_id=request_id
            )
            coordination_plan = await self._get_coordinator_plan(user_request, category, request_id)
            
            # Check if clarification is needed
            if coordination_plan.get("clarification_needed", False):
                clarification_questions = coordination_plan.get("clarification_questions", ["Could you provide more details about your request?"])
                result = {
                    "status": "clarification_needed",
                    "processed_by": "AI Assistant",
                    "clarification_questions": clarification_questions,
                    "request_id": request_id
                }
                return result
            
            # Step 3-4: Process with full delegation flow
            final_response = await self._process_with_delegations(user_request, parsed_data, coordination_plan, request_id)
            
            # Store the interaction
            self.store_memory({
                "request": user_request,
                "response": final_response,
                "request_id": request_id,
                "primary_agent": coordination_plan["primary_agent"],
                "supporting_agents": coordination_plan["supporting_agents"],
                "timestamp": time.time()
            })
            
            # Return structured response
            return {
                "status": "success",
                "processed_by": "AI Assistant",
                "primary_agent": coordination_plan["primary_agent"],
                "supporting_agents": coordination_plan["supporting_agents"],
                "response": final_response,
                "request_id": request_id
            }
            
        except Exception as e:
            error_msg = f"Error processing message: {str(e)}"
            self.logger.error(error_msg)
            return {
                "status": "error",
                "processed_by": "AI Assistant",
                "response": f"I apologize, but there was an error processing your request: {str(e)}",
                "error": str(e),
                "request_id": request_id
            }
    
    async def process(self, request: Dict[str, Any]) -> Dict[str, Any]:
        """
        Process a request asynchronously.
        This is a wrapper around the async process_message.
        """
        user_request = request.get('text', str(request))
        request_id = request.get('request_id', str(uuid.uuid4()))
        
        # Directly call the process_message method without dealing with event loops
        return await self.process_message(user_request)
