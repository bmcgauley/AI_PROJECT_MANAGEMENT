"""
Modern Base Agent class using Pydantic and LangGraph for the AI Project Management System.
All specialized agents will use this implementation.
"""

from typing import Any, Dict, List, Optional, Union, cast, Literal, TypedDict, Annotated, Sequence
import logging
import asyncio
from datetime import datetime
import operator

from pydantic import BaseModel, Field
from langchain_core.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, BaseMessage
from langchain_core.tools import Tool
from langchain_core.language_models import BaseLanguageModel

# Updated imports for newer LangChain agent architecture
from langchain.agents import AgentExecutor
from langchain_community.chat_models.ollama import ChatOllama
from langgraph.graph import END, StateGraph

# Import for creating ReAct style agent with LangGraph
from langgraph.prebuilt import create_react_agent

from ..models.agent_models import AgentState, AgentConfig, EdgeType, AgentResponse, AgentMemoryItem

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

# Define a typed schema for the workflow state
class WorkflowState(TypedDict):
    """Schema for the workflow state used by LangGraph."""
    messages: List[BaseMessage]
    context: str
    attempts: int
    max_attempts: int
    verified: bool
    result: Optional[str]
    error: Optional[str]
    tool_calls: List[Any]
    next: str

class AgentStateGraph(TypedDict):
    """Schema for the agent state used by the LangGraph ReAct agent."""
    messages: Annotated[Sequence[BaseMessage], operator.add]

class ModernBaseAgent:
    """
    Modern base agent using Pydantic and LangGraph.
    Provides common functionality for all agents in the system.
    """
    
    def __init__(
        self,
        llm: BaseLanguageModel,
        config: AgentConfig,
        tools: Optional[List[Tool]] = None,
        mcp_client: Optional[Any] = None
    ):
        """
        Initialize the modern base agent.
        
        Args:
            llm: Language model to use for responses
            config: Configuration for the agent
            tools: List of LangChain tools available to the agent
            mcp_client: Optional client for interacting with MCP servers
        """
        self.llm = llm
        self.config = config
        self.tools = tools or []
        self.mcp_client = mcp_client
        self.name = config.name
        self.description = config.description
        self.logger = logging.getLogger(f"agent.{self.name}")
        self.logger.info(f"Initialized {self.name} agent")
        self.memory: List[AgentMemoryItem] = []
        
        # Create the agent and executor with modern LangGraph approach
        try:
            # Build system message
            system_message_content = self._build_system_message()
            
            # Create a system message object
            system_message_obj = SystemMessage(content=system_message_content)
            
            # Create ReAct agent with LangGraph's prebuilt function
            self.agent_executor = create_react_agent(
                model=self.llm,
                tools=self.tools,
                # Changed from system_prompt to prompt to match the current LangGraph API
                prompt=system_message_content
            )
            
            # Initialize the workflow graph
            self.workflow = self._create_workflow_graph()
            
        except Exception as e:
            self.logger.error(f"Error initializing agent: {str(e)}")
            raise
    
    def _build_system_message(self) -> str:
        """
        Build the agent's system message based on its configuration.
        
        Returns:
            str: The configured system message
        """
        # Use the provided system prompt if available
        if self.config.system_prompt:
            return self.config.system_prompt
        
        # Default role description
        return f"""You are an AI assistant specialized in {self.config.agent_type.value}.
        Your name is {self.name} and your role is: {self.description}
        
        When using tools, follow these steps:
        1. Analyze the request carefully
        2. Determine if you need additional information 
        3. Plan your approach using available tools
        4. Execute your plan step by step
        5. Verify your results
        """
    
    def _create_workflow_graph(self) -> StateGraph:
        """
        Create a LangGraph workflow for more reliable agent execution.
        
        Returns:
            StateGraph: The compiled workflow graph
        """
        # Create a graph with state schema - updated for modern LangGraph
        workflow = StateGraph(WorkflowState)
        
        # Add nodes for different workflow states
        workflow.add_node("process", self._process_request)
        workflow.add_node("verify", self._verify_result)
        
        # Set the entry point
        workflow.set_entry_point("process")
        
        # Define conditional routing
        workflow.add_conditional_edges(
            "verify",
            self._determine_next_step,
            {
                "process": "process",  # Try again
                END: END  # End workflow
            }
        )
        
        # Always go to verify after process
        workflow.add_edge("process", "verify")
        
        return workflow.compile()
    
    def _determine_next_step(self, state: WorkflowState) -> Union[str, Literal["end"]]:
        """
        Determine the next workflow step based on state.
        
        Args:
            state: Current workflow state
            
        Returns:
            Next step or END to terminate workflow
        """
        next_step = state.get("next")
        if next_step == "end" or not next_step:
            return END
        return cast(str, next_step)
    
    def _process_request(self, state: WorkflowState) -> WorkflowState:
        """
        Process a request using the agent executor.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state
        """
        try:
            # Ensure messages field exists for LangGraph agent
            if "messages" not in state:
                # Get the input from state and convert to messages format
                input_content = state.get("input", "")
                state["messages"] = [HumanMessage(content=input_content)]
            
            # Add chat history if not already present in messages
            if len(state["messages"]) == 1:  # Only the current user message
                history_messages = self._get_chat_history()
                if history_messages:
                    # Insert history before the current message
                    state["messages"] = history_messages + state["messages"]
            
            # Use LangGraph agent executor with modern invoke pattern
            agent_response = self.agent_executor.invoke({"messages": state["messages"]})
            
            # Extract final AI message and add to result
            final_message = agent_response["messages"][-1]
            
            return {
                **state,
                "result": final_message.content if hasattr(final_message, "content") else str(final_message),
                "messages": agent_response["messages"],
                "tool_calls": agent_response.get("intermediate_steps", []),
                "error": None,
                "next": "verify"  # Always verify after processing
            }
        except Exception as e:
            self.logger.error(f"Error in process_request: {str(e)}")
            return {
                **state,
                "error": str(e),
                "result": None,
                "tool_calls": [],
                "next": "verify"  # Still verify to handle the error
            }
    
    def _verify_result(self, state: WorkflowState) -> WorkflowState:
        """
        Verify the result and decide whether to continue or end.
        
        Args:
            state: Current workflow state
            
        Returns:
            Updated workflow state with next action decision
        """
        if state.get("error"):
            if state["attempts"] < state["max_attempts"]:
                state["attempts"] += 1
                state["next"] = "process"
            else:
                state["next"] = "end"
            return state
            
        if state.get("result"):
            state["verified"] = True
            state["next"] = "end"
            return state
            
        state["attempts"] += 1
        if state["attempts"] < state["max_attempts"]:
            state["next"] = "process"
        else:
            state["next"] = "end"
        
        return state
    
    def _get_chat_history(self) -> List[Union[HumanMessage, AIMessage]]:
        """
        Convert memory to chat history format.
        
        Returns:
            List of message objects for chat history
        """
        history = []
        for interaction in self.memory[-5:]:  # Last 5 interactions
            history.append(HumanMessage(content=interaction.input))
            history.append(AIMessage(content=interaction.output))
        return history
    
    def _initialize_state(self, request: str, context: str = "") -> WorkflowState:
        """
        Initialize the workflow state.
        
        Args:
            request: User request to process
            context: Optional context information
            
        Returns:
            Initial workflow state
        """
        return {
            "messages": [HumanMessage(content=request)],
            "context": context,
            "attempts": 0,
            "max_attempts": 3,
            "verified": False,
            "result": None,
            "error": None,
            "tool_calls": [],
            "next": "process"  # Start with process
        }
    
    def store_memory(self, item: AgentMemoryItem) -> None:
        """
        Store an interaction in the agent's memory.
        
        Args:
            item: Memory item to store
        """
        self.memory.append(item)
        # Keep memory at a reasonable size by removing oldest entries if too large
        if len(self.memory) > 50:
            self.memory.pop(0)
    
    def get_memory(self, limit: Optional[int] = None) -> List[AgentMemoryItem]:
        """
        Retrieve the agent's memory of past interactions.
        
        Args:
            limit: Optional limit on the number of memory items to return
            
        Returns:
            List of past interactions
        """
        if limit:
            return self.memory[-limit:]
        return self.memory
    
    async def use_tool(self, server: str, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use an MCP tool with the specified server.
        
        Args:
            server: MCP server name
            tool: Tool name to use
            arguments: Arguments for the tool
            
        Returns:
            The result from the tool
        """
        if not self.mcp_client:
            self.logger.warning(f"Cannot use {tool} - no MCP client available")
            return {"status": "error", "error": {"message": "No MCP client available"}}
            
        # Check if the agent has access to this tool
        if (server not in self.config.available_tools or 
            tool not in self.config.available_tools.get(server, [])):
            self.logger.warning(f"{self.name} does not have permission to use {tool} on {server}")
            return {
                "status": "error", 
                "error": {"message": f"Permission denied: {self.name} cannot access {tool}"}
            }
            
        try:
            result = await self.mcp_client.use_tool(server, tool, arguments)
            return result
        except Exception as e:
            self.logger.error(f"Error using tool {tool} on {server}: {str(e)}")
            return {"status": "error", "error": {"message": str(e)}}
    
    def use_tool_sync(self, server: str, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronous wrapper for use_tool.
        
        Args:
            server: MCP server name
            tool: Tool name to use
            arguments: Arguments for the tool
            
        Returns:
            The result from the tool
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(self.use_tool(server, tool, arguments))
    
    async def process(self, request: str) -> AgentResponse:
        """
        Process a request and generate a response.
        
        Args:
            request: The request to process
            
        Returns:
            The agent's response
        """
        try:
            # Initialize state with request
            initial_state = self._initialize_state(request)
            
            # Run the workflow using the modern async approach
            final_state = await asyncio.to_thread(self.workflow.invoke, initial_state)
            
            # Store the interaction in memory if successful
            if final_state.get("result"):
                memory_item = AgentMemoryItem(
                    input=request,
                    output=final_state["result"],
                    tool_calls=final_state.get("tool_calls", [])
                )
                self.store_memory(memory_item)
                
                response = AgentResponse(
                    agent_name=self.name,
                    content=final_state["result"],
                    tool_calls=final_state.get("tool_calls", []),
                    state=final_state,
                    timestamp=datetime.now()
                )
                
                return response
            
            # Handle error case
            error_msg = f"Error processing request after {final_state['attempts']} attempts: {final_state.get('error', 'Unknown error')}"
            return AgentResponse(
                agent_name=self.name,
                content="",
                error=error_msg,
                timestamp=datetime.now()
            )
            
        except Exception as e:
            error = f"Error processing request: {str(e)}"
            self.logger.error(error)
            return AgentResponse(
                agent_name=self.name,
                content="",
                error=error,
                timestamp=datetime.now()
            )
    
    def __str__(self) -> str:
        """String representation of the agent."""
        return f"{self.name} - {self.description}"
