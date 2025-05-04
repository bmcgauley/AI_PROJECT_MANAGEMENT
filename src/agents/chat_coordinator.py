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
from crewai import Agent, Crew, Process, Task

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
        self.crew_agents = {}  # Store Crew.ai agent instances
        
        # Add RequestParserAgent automatically
        if 'request_parser' not in self.agents:
            self.agents['request_parser'] = RequestParserAgent(llm=llm, mcp_client=mcp_client)
        
        # Event callback for WebSocket notifications
        self.event_callback = None
        
        # Memory for conversation history
        self.memory = []
    
    def set_event_callback(self, callback: Callable) -> None:
        """Set callback for real-time event notifications."""
        self.event_callback = callback

    def add_agent(self, name: str, agent: BaseAgent) -> None:
        """Add a specialized agent to the coordinator."""
        self.agents[name.lower()] = agent
        self.logger.info(f"Added agent: {name}")
    
    def add_crew_agent(self, name: str, agent: Agent) -> None:
        """Add a Crew.ai agent to the coordinator."""
        self.crew_agents[name.lower()] = agent
        self.logger.info(f"Added Crew.ai agent: {name}")
    
    def get_available_agents(self) -> str:
        """Get formatted string listing available specialized agents."""
        agent_descriptions = []
        for name, agent in self.agents.items():
            if name != 'request_parser':
                agent_descriptions.append(f"{agent.name}: {agent.description}")
        
        # Include Crew.ai agents as well
        for name, agent in self.crew_agents.items():
            agent_descriptions.append(f"{agent.role}: {agent.backstory.split('.')[0] if agent.backstory else 'Specialized agent'}")
        
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
    
    async def process_jira_related_request(self, user_request: str, request_id: str) -> Dict[str, Any]:
        """Process a request specifically related to Jira using Project Manager agent."""
        # Check if Project Manager exists in either regular or crew agents
        pm_agent = None
        if 'project manager' in self.agents:
            pm_agent = self.agents['project manager']
        
        if not pm_agent:
            return {
                "status": "error",
                "processed_by": "AI Assistant",
                "response": "Sorry, I couldn't find the Project Manager agent to handle your Jira request.",
                "request_id": request_id
            }
        
        await self._emit_event("agent_assigned", 
            agent="Project Manager",
            request_id=request_id
        )
        
        await self._emit_event("agent_thinking", 
            agent="Project Manager",
            thinking=f"Working on Jira request: '{user_request}'",
            request_id=request_id
        )
        
        # Prepare request data
        request_data = {
            "original_text": user_request,
            "context": self.get_context(),
        }
        
        # Process with Project Manager
        if inspect.iscoroutinefunction(pm_agent.process):
            response = await pm_agent.process(request_data)
        else:
            response = pm_agent.process(request_data)
        
        # Store the interaction
        self.store_memory({
            "request": user_request,
            "response": response,
            "request_id": request_id,
            "primary_agent": "Project Manager",
            "timestamp": time.time()
        })
        
        await self._emit_event("agent_response", 
            agent="Project Manager",
            response=response,
            request_id=request_id
        )
        
        # Return structured response
        return {
            "status": "success",
            "processed_by": "Project Manager",
            "primary_agent": "Project Manager",
            "supporting_agents": [],
            "response": response,
            "request_id": request_id
        }

    async def _classify_request_intent(self, user_request: str) -> Dict[str, Any]:
        """
        Use the LLM to classify the user request and determine the most appropriate agent.
        This provides a more sophisticated approach than keyword matching.
        
        Args:
            user_request: The user's request text
            
        Returns:
            Dict containing the primary role, involved roles, and confidence
        """
        # For very short greetings/messages, provide a default classification
        if len(user_request.split()) <= 3 and any(word in user_request.lower() for word in ['hi', 'hello', 'hey', 'greetings']):
            return {
                "primary_role": "Research Specialist",
                "involved_roles": ["Research Specialist"],
                "confidence": 0.9
            }
        
        # Use a prompt to classify the request
        try:
            classification_prompt = f"""
            You are a request classifier for an AI system with multiple specialized agents.
            Based on the user's request, determine which agent would be most appropriate.
            
            The available agent roles are:
            1. Code Developer - For coding, programming, development tasks, debugging
            2. Code Reviewer - For reviewing and analyzing code quality
            3. Research Specialist - For information gathering, research questions, general knowledge
            4. Business Analyst - For business requirements, stakeholder needs, analysis
            5. Project Manager - For project planning, coordination, resource management
            6. Report Drafter - For creating documentation, reports, written content
            7. Report Reviewer - For reviewing and improving documentation
            
            For this user request: "{user_request}"
            
            Return a JSON object with:
            1. primary_role: The single most appropriate agent for this request
            2. involved_roles: List of roles that should be involved (1-2 most relevant)
            3. confidence: A number from 0.0 to 1.0 indicating your confidence in this classification
            
            Response format:
            {{
                "primary_role": "Role name",
                "involved_roles": ["Role name", "Role name"],
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
                    classification["primary_role"] = "Research Specialist"
                if "involved_roles" not in classification:
                    classification["involved_roles"] = [classification["primary_role"]]
                if "confidence" not in classification:
                    classification["confidence"] = 0.7
                
                return classification
                
            except Exception as e:
                self.logger.error(f"Error parsing classification: {e}")
                return {
                    "primary_role": "Research Specialist", 
                    "involved_roles": ["Research Specialist"],
                    "confidence": 0.5
                }
                
        except Exception as e:
            self.logger.error(f"Error classifying request: {e}")
            return {
                "primary_role": "Research Specialist",
                "involved_roles": ["Research Specialist"],
                "confidence": 0.5
            }

    async def process_with_crew_ai(self, user_request: str, request_id: str) -> Dict[str, Any]:
        """Process a request using Crew.ai for better agent orchestration."""
        if not self.crew_agents:
            return {
                "status": "error",
                "processed_by": "AI Assistant",
                "response": "Crew.ai agents are not configured. Please check your system setup.",
                "request_id": request_id
            }
        
        # Log that we're using Crew.ai
        await self._emit_event("workflow_step", 
            message="Processing request with Crew.ai orchestration",
            request_id=request_id
        )
        
        try:
            # Use the LLM-based classifier to determine intent and appropriate agents
            classification = await self._classify_request_intent(user_request)
            primary_role = classification["primary_role"]
            involved_roles = classification["involved_roles"]
            
            # Log the classification result
            self.logger.info(f"Request classified as {primary_role} with confidence {classification.get('confidence', 0.0)}")
            self.logger.info(f"Involved roles: {involved_roles}")
            
            # For Jira-related requests detected by the classifier, use the specialized handler
            if primary_role == "Project Manager" and any(kw in user_request.lower() for kw in ["jira", "atlassian", "ticket"]):
                return await self.process_jira_related_request(user_request, request_id)
            
            # Find matching crew agents
            crew_agents_to_use = []
            for role in involved_roles:
                role_lower = role.lower()
                found_agent = False
                
                # Look for exact or partial matches
                for name, agent in self.crew_agents.items():
                    agent_role_lower = agent.role.lower()
                    if role_lower == agent_role_lower or role_lower in agent_role_lower:
                        crew_agents_to_use.append(agent)
                        await self._emit_event("agent_assigned", 
                            agent=agent.role,
                            request_id=request_id
                        )
                        found_agent = True
                        break
                
                # If we couldn't find an agent with this role, try to find a substitute
                if not found_agent:
                    self.logger.warning(f"Could not find agent with role: {role}. Looking for alternatives.")
                    
                    # Try to find any available agent if we have none yet and this is our primary role
                    if not crew_agents_to_use and role == primary_role:
                        # Default to Research Specialist for general queries
                        for name, agent in self.crew_agents.items():
                            if "research" in agent.role.lower() or "specialist" in agent.role.lower():
                                crew_agents_to_use.append(agent)
                                await self._emit_event("agent_assigned", 
                                    agent=agent.role,
                                    request_id=request_id
                                )
                                self.logger.info(f"Using {agent.role} as fallback for {role}")
                                found_agent = True
                                break
                                
                        # If still no Research Specialist found, get any agent
                        if not found_agent:
                            for name, agent in self.crew_agents.items():
                                if "project manager" not in agent.role.lower():  # Try not to default to PM
                                    crew_agents_to_use.append(agent)
                                    await self._emit_event("agent_assigned", 
                                        agent=agent.role,
                                        request_id=request_id
                                    )
                                    self.logger.info(f"Using {agent.role} as fallback for {role}")
                                    found_agent = True
                                    break
            
            # If still no agents found, use any available agent (last resort)
            if not crew_agents_to_use and self.crew_agents:
                agent = next(iter(self.crew_agents.values()))
                crew_agents_to_use.append(agent)
                await self._emit_event("agent_assigned", 
                    agent=agent.role,
                    request_id=request_id
                )
                self.logger.info(f"Using {agent.role} as last resort")
            
            # Create task for Crew.ai
            primary_agent = None
            
            # Try to find the primary agent from our matched agents
            for agent in crew_agents_to_use:
                if primary_role.lower() in agent.role.lower():
                    primary_agent = agent
                    break
            
            # If primary role not found, use the first agent
            if not primary_agent and crew_agents_to_use:
                primary_agent = crew_agents_to_use[0]
            
            if not primary_agent:
                return {
                    "status": "error",
                    "processed_by": "AI Assistant",
                    "response": "I couldn't find appropriate agents to handle your request. Please try a different query.",
                    "request_id": request_id
                }
            
            # Emit event for primary agent thinking
            await self._emit_event("agent_thinking", 
                agent=primary_agent.role,
                thinking=f"Working on: '{user_request}'",
                request_id=request_id
            )
            
            # Create task and crew for this request
            task = Task(
                description=f"Handle this request: '{user_request}'",
                expected_output="A complete and helpful response to the user's request",
                agent=primary_agent
            )
            
            crew = Crew(
                agents=crew_agents_to_use,
                tasks=[task],
                verbose=True,
                process=Process.sequential if len(crew_agents_to_use) == 1 else Process.hierarchical
            )
            
            # Execute the crew
            result = crew.kickoff()
            
            # Convert result to string if needed
            result_str = str(result) if hasattr(result, '__str__') else "Task completed successfully"
            
            # Store the interaction
            self.store_memory({
                "request": user_request,
                "response": result_str,
                "request_id": request_id,
                "primary_agent": primary_agent.role,
                "supporting_agents": [agent.role for agent in crew_agents_to_use if agent != primary_agent],
                "timestamp": time.time()
            })
            
            # Emit completion event
            await self._emit_event("request_complete", 
                message="Request processing completed",
                request_id=request_id,
                involved_agents=[agent.role for agent in crew_agents_to_use]
            )
            
            return {
                "status": "success",
                "processed_by": primary_agent.role,
                "primary_agent": primary_agent.role,
                "supporting_agents": [agent.role for agent in crew_agents_to_use if agent != primary_agent],
                "response": result_str,
                "request_id": request_id
            }
            
        except Exception as e:
            error_msg = f"Error processing request with Crew.ai: {str(e)}"
            self.logger.error(error_msg)
            
            await self._emit_event("request_error", 
                message=error_msg,
                request_id=request_id
            )
            
            return {
                "status": "error",
                "processed_by": "AI Assistant",
                "response": f"I apologize, but there was an error processing your request with our agent system: {str(e)}",
                "error": str(e),
                "request_id": request_id
            }
    
    async def process_message(self, user_request: str) -> Dict[str, Any]:
        """
        Process a user message through the multi-agent system.
        This is the main entry point for handling user requests.
        """
        request_id = str(uuid.uuid4())
        self.logger.info(f"Processing new request ID: {request_id}")
        
        try:
            request_lower = user_request.lower()
            
            # First, check if this is specifically a Jira-related request
            if any(kw in request_lower for kw in ["jira", "atlassian", "ticket", "issue", "project"]):
                # For Jira requests, use the dedicated handler
                return await self.process_jira_related_request(user_request, request_id)
            
            # For all other requests, use Crew.ai if available
            if self.crew_agents:
                return await self.process_with_crew_ai(user_request, request_id)
                
            # If no Crew.ai agents, use the legacy processing path
            await self._emit_event("workflow_step", 
                message="No Crew.ai agents available - using legacy processing",
                request_id=request_id
            )
            
            # Just return a simple error for now (this path should be less common)
            return {
                "status": "error",
                "processed_by": "AI Assistant",
                "response": "I'm sorry, but the system is currently configured to use Crew.ai agents, which aren't available. Please check your system configuration.",
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
        
        # Directly call the process_message method
        return await self.process_message(user_request)
