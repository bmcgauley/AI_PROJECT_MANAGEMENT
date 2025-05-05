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
import backoff
from langchain.prompts import PromptTemplate

from src.agents.base_agent import BaseAgent
from src.agents.request_parser import RequestParserAgent

class ChatCoordinatorAgent(BaseAgent):
    """
    Chat Coordinator Agent that serves as the main interface for users.
    Handles all user interactions and orchestrates communication between specialized agents.
    Can use a secretary persona to provide a consistent voice across all interactions.
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
        
        # Event callback for WebSocket notifications
        self.event_callback = None
        
        # Memory for conversation history
        self.memory = []
        
        # Secretary persona functionality
        self.use_secretary_persona = True
        
        # Define the secretary persona template
        self.secretary_prompt = PromptTemplate(
            input_variables=["original_response", "persona_notes", "agent_name", "user_request"],
            template="""
            You are a friendly Executive Assistant for an AI Project Management system.
            
            Your role is to represent the entire system with a consistent, helpful, and professional personality.
            Although different specialized agents handle different types of requests behind the scenes,
            the user should always feel like they're talking to the same friendly assistant.
            
            Persona notes:
            {persona_notes}
            
            The user's request was: {user_request}
            
            The specialized {agent_name} agent provided this response:
            {original_response}
            
            Reframe this response using your Executive Assistant persona. Keep all the technical information 
            and helpful content from the original response, but make it sound like it's coming from you,
            a friendly and consistent assistant. Add conversational elements to maintain rapport.
            
            Important guidelines:
            1. Never mention that you're "reframing" or "translating" a response.
            2. Never explicitly mention which specialized agent actually handled the request.
            3. Use a consistent, personable tone throughout.
            4. Maintain all technical accuracy and key information from the original response.
            5. Feel free to add brief pleasantries or personalizations at the beginning/end.
            6. If the original response is already conversational, make only minor adjustments for consistency.
            
            Your reframed response:
            """
        )
        
        # Use the modern API pattern
        self.secretary_chain = self.secretary_prompt | llm
    
    def set_event_callback(self, callback: Callable) -> None:
        """Set callback for real-time event notifications."""
        self.event_callback = callback

    def add_agent(self, name: str, agent: BaseAgent) -> None:
        """Add a specialized agent to the coordinator."""
        self.agents[name.lower()] = agent
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
    
    async def _classify_request_intent(self, user_request: str) -> Dict[str, Any]:
        """
        Use the LLM to classify the user request and determine the most appropriate agent.
        
        Args:
            user_request: The user's request text
            
        Returns:
            Dict containing the primary role and confidence
        """
        # For very short greetings/messages, provide a default classification
        if len(user_request.split()) <= 3 and any(word in user_request.lower() for word in ['hi', 'hello', 'hey', 'greetings']):
            return {
                "primary_role": "AI Assistant",
                "confidence": 0.9
            }
        
        # Use a prompt to classify the request
        try:
            classification_prompt = f"""
            You are a request classifier for an AI system with multiple specialized agents.
            Based on the user's request, determine which agent would be most appropriate.
            
            The available agent roles are:
            {self.get_available_agents()}
            
            For this user request: "{user_request}"
            
            Return a JSON object with:
            1. primary_role: The single most appropriate agent for this request
            2. confidence: A number from 0.0 to 1.0 indicating your confidence in this classification
            
            Response format:
            {{
                "primary_role": "Role name",
                "confidence": 0.9
            }}
            """
            
            response = await self.llm.apredict(classification_prompt)
            
            # Parse the JSON response
            try:
                # Extract JSON if wrapped in text
                if "```json" in response:
                    json_str = response.split("```json")[1].split("```")[0].strip()
                elif "```" in response:
                    json_str = response.split("```")[1].strip()
                else:
                    json_str = response.strip()
                
                # Clean up the string to ensure valid JSON
                import re
                json_str = re.sub(r'[\r\n\t]', '', json_str)
                
                # Find the JSON object between curly braces
                match = re.search(r'\{.*\}', json_str)
                if match:
                    json_str = match.group(0)
                
                classification = json.loads(json_str)
                
                # Ensure we have the required fields
                if "primary_role" not in classification:
                    classification["primary_role"] = "AI Assistant"
                if "confidence" not in classification:
                    classification["confidence"] = 0.7
                
                return classification
                
            except Exception as e:
                self.logger.error(f"Error parsing classification: {e}")
                return {
                    "primary_role": "AI Assistant",
                    "confidence": 0.5
                }
                
        except Exception as e:
            self.logger.error(f"Error classifying request: {e}")
            return {
                "primary_role": "AI Assistant",
                "confidence": 0.5
            }
            
    async def aprocess(self, request: Dict[str, Any]) -> str:
        """
        Async version of process - handles a user request by coordinating with specialized agents.
        
        Args:
            request: Dictionary containing the request details
            
        Returns:
            The response to the user
        """
        user_request = request.get("original_text", "")
        request_id = request.get("request_id", str(uuid.uuid4()))
        context = request.get("context", "")
        
        # Log the incoming request
        self.logger.info(f"Processing request: {user_request[:100]}...")
        
        # First check if it's a Jira-related request using keyword detection
        is_jira_request = any(keyword in user_request.lower() for keyword in 
                              ["jira", "issue", "ticket", "project", "sprint", "board", "atlassian"])
        
        if is_jira_request:
            self.logger.info(f"Detected Jira-related request, routing to specialized handler")
            result = await self.process_jira_related_request(user_request, request_id)
            return result.get("response", "Error processing Jira request")
            
        # For non-Jira requests, use the classifier to determine the appropriate agent
        classification = await self._classify_request_intent(user_request)
        primary_role = classification["primary_role"]
        confidence = classification["confidence"]
        
        self.logger.info(f"Request classified as {primary_role} with confidence {confidence}")
        
        # Find the appropriate agent
        agent_name = primary_role.lower()
        if agent_name in self.agents:
            agent = self.agents[agent_name]
            
            await self._emit_event("agent_assigned", 
                agent=primary_role,
                request_id=request_id
            )
            
            await self._emit_event("agent_thinking", 
                agent=primary_role,
                thinking=f"Working on: '{user_request}'",
                request_id=request_id
            )
            
            # Process with the chosen agent
            try:
                if hasattr(agent, 'aprocess'):
                    response = await agent.aprocess({"original_text": user_request, "context": context})
                else:
                    # Fallback to regular process method
                    if inspect.iscoroutinefunction(agent.process):
                        response = await agent.process({"original_text": user_request, "context": context})
                    else:
                        response = agent.process({"original_text": user_request, "context": context})
                
                # Apply secretary persona if enabled
                if self.use_secretary_persona:
                    response = await self.personalize_response(
                        original_response=response,
                        agent_name=primary_role,
                        user_request=user_request
                    )
                
                # Store the interaction
                self.store_memory({
                    "request": user_request,
                    "response": response,
                    "request_id": request_id,
                    "primary_agent": primary_role,
                    "timestamp": time.time()
                })
                
                await self._emit_event("request_complete", 
                    message="Request processing completed",
                    request_id=request_id,
                    involved_agents=[primary_role]
                )
                
                return response
                
            except Exception as e:
                error_msg = f"Error processing request with {primary_role}: {str(e)}"
                self.logger.error(error_msg)
                
                await self._emit_event("request_error", 
                    message=error_msg,
                    request_id=request_id
                )
                
                return f"I apologize, but I encountered an error while processing your request: {str(e)}"
        
        # If we couldn't find an appropriate agent, return an error
        return "I apologize, but I couldn't find an appropriate agent to handle your request."
    
    def process(self, request: Dict[str, Any]) -> Any:
        """
        Process a request and generate a response.
        Implementation of the abstract method required by BaseAgent.
        
        Args:
            request: Dictionary containing the request details
            
        Returns:
            The response to the user
        """
        # Create event loop for async processing if needed
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        # Call the async version
        return loop.run_until_complete(self.aprocess(request))
    
    async def process_message(self, message: str, request_id: str = None) -> Dict[str, Any]:
        """
        Process a user message. This method exists for backward compatibility.
        Internally uses the new process/aprocess methods.
        
        Args:
            message: The user's message text
            request_id: Optional unique identifier for the request
            
        Returns:
            Dict containing the processing result
        """
        result = await self.aprocess({
            "original_text": message,
            "request_id": request_id or str(uuid.uuid4()),
            "context": self.get_context()
        })
        
        # If the result is already a dict with proper structure, return it
        if isinstance(result, dict) and "status" in result:
            return result
            
        # Otherwise wrap it in a proper response structure
        return {
            "status": "success",
            "processed_by": "AI Assistant",
            "response": str(result),
            "request_id": request_id
        }
        
    async def personalize_response(self, original_response: str, agent_name: str, user_request: str) -> str:
        """Apply the secretary persona to responses for a consistent voice."""
        if not self.use_secretary_persona:
            return original_response
            
        try:
            # Basic persona notes
            persona_notes = (
                "Be friendly, helpful, and professional. Maintain conversational tone while "
                "preserving all technical details. Use clear language and avoid unnecessary jargon."
            )
            
            # Use the chain to transform the response
            personalized = await self.secretary_chain.ainvoke({
                "original_response": original_response,
                "persona_notes": persona_notes,
                "agent_name": agent_name,
                "user_request": user_request
            })
            
            return personalized
        except Exception as e:
            self.logger.error(f"Error personalizing response: {str(e)}")
            return original_response  # Fall back to original if transformation fails
    
    async def cleanup(self) -> None:
        """Clean up any resources used by the Chat Coordinator agent."""
        # Clean up any resources in use
        self.agents.clear()
        self.memory.clear()
        self.event_callback = None
        logger.info("Chat Coordinator agent cleaned up successfully")
