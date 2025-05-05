"""
Simple LangChain-based agent for the AI Project Management System.
Uses modern LangChain patterns with LangGraph support for reliable workflows.
"""

import os
os.environ["LANGCHAIN_SQLITE_PATH"] = ":memory:"  # Use in-memory SQLite

from typing import Any, Dict, List, Optional, TypedDict, Annotated, Union, Literal, cast
import logging
from langchain.prompts import ChatPromptTemplate, MessagesPlaceholder
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage
from langchain_core.tools import Tool
from langchain.agents import AgentExecutor, create_openai_tools_agent
from langchain_core.runnables import RunnablePassthrough
from langgraph.graph import END, StateGraph
from pydantic import BaseModel

# Define edge names for type safety
EdgeType = Literal["process", "verify", "end"]

# Define state types
class AgentState(TypedDict, total=False):
    """State maintained by the agent during execution."""
    input: str
    context: str
    attempts: int
    max_attempts: int
    verified: bool
    chat_history: Optional[List[HumanMessage | AIMessage]]
    result: Optional[str]
    error: Optional[str]
    tool_calls: Optional[List[Any]]
    next: Optional[EdgeType]  # Next node in workflow

class SimpleAgent:
    """
    A simplified agent using modern LangChain patterns with LangGraph support.
    Provides core functionality with built-in tool handling, memory, and workflow management.
    """
    
    def __init__(self, llm, tools: Optional[List[Tool]] = None, agent_type: str = "project_manager"):
        """
        Initialize the simple agent.
        
        Args:
            llm: Language model to use
            tools: Optional list of LangChain tools to make available
            agent_type: Type of agent ("project_manager", "researcher", etc.)
        """
        self.llm = llm
        self.tools = tools or []
        self.agent_type = agent_type
        self.memory: List[Dict[str, Any]] = []
        self.logger = logging.getLogger(f"simple_agent.{agent_type}")
        
        # Create the agent and executor with better error handling
        try:
            prompt = self._get_prompt()
            self.agent = create_openai_tools_agent(
                llm=self.llm,
                tools=self.tools,
                prompt=prompt
            )
            self.agent_executor = AgentExecutor(
                agent=self.agent,
                tools=self.tools,
                verbose=True,
                handle_parsing_errors=True  # Better error handling
            )
            
            # Initialize the workflow graph
            self.workflow = self._create_workflow_graph()
            
            self.logger.info(f"Initialized {agent_type} agent with {len(self.tools)} tools")
        except Exception as e:
            self.logger.error(f"Error initializing agent: {str(e)}")
            raise

    def _get_prompt(self) -> ChatPromptTemplate:
        """Get the agent's prompt template."""
        # Base system message with role-specific instructions
        system_message = f"""You are an AI Project Management assistant specialized in {self.agent_type}.
        Your goal is to help users manage their projects effectively.
        
        When using tools, think step-by-step:
        1. Analyze the request and context
        2. Determine if you need additional information
        3. Plan your approach using available tools
        4. Execute your plan carefully
        5. Verify the results
        """
        
        # Add role-specific focus areas
        if self.agent_type == "project_manager":
            system_message += """
            Focus on:
            - Project planning and organization
            - Task tracking and timeline management
            - Resource allocation
            - Risk assessment
            """
        elif self.agent_type == "researcher":
            system_message += """
            Focus on:
            - Gathering relevant information
            - Analyzing requirements
            - Providing well-researched recommendations
            - Documenting findings
            """
        
        # Create prompt following LangChain's latest patterns
        prompt = ChatPromptTemplate.from_messages([
            ("system", system_message),
            MessagesPlaceholder(variable_name="chat_history", optional=True),
            ("human", "{input}"),
            MessagesPlaceholder(variable_name="agent_scratchpad")  # Required for tool use
        ])
        
        return prompt

    def _determine_next_step(self, state: AgentState) -> Union[EdgeType, Literal["end"]]:
        """Determine the next workflow step based on state."""
        next_step = state.get("next")
        if next_step == "end" or not next_step:
            return END
        return cast(EdgeType, next_step)

    def _create_workflow_graph(self) -> StateGraph:
        """Create a LangGraph workflow for more reliable agent execution."""
        # Create a graph with explicit state type
        workflow = StateGraph()
        
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

    def _initialize_state(self, request: str, context: str) -> AgentState:
        """Initialize the workflow state."""
        return {
            "input": request,
            "context": context,
            "attempts": 0,
            "max_attempts": 3,
            "verified": False,
            "chat_history": None,
            "result": None,
            "error": None,
            "tool_calls": None,
            "next": cast(EdgeType, "process")  # Start with process
        }

    def _process_request(self, state: AgentState) -> AgentState:
        """Process a request using the agent executor."""
        try:
            # Add chat history from memory
            state["chat_history"] = self._get_chat_history()
            
            response = self.agent_executor.invoke(state)
            return {
                **state,
                "result": response["output"],
                "tool_calls": response.get("intermediate_steps", []),
                "error": None,
                "next": cast(EdgeType, "verify")  # Always verify after processing
            }
        except Exception as e:
            self.logger.error(f"Error in process_request: {str(e)}")
            return {
                **state,
                "error": str(e),
                "result": None,
                "tool_calls": None,
                "next": cast(EdgeType, "verify")  # Still verify to handle the error
            }

    def _verify_result(self, state: AgentState) -> AgentState:
        """Verify the result and decide whether to continue or end."""
        if state.get("error"):
            if state["attempts"] < state["max_attempts"]:
                state["attempts"] += 1
                state["next"] = cast(EdgeType, "process")
            else:
                state["next"] = cast(EdgeType, "end")
            return state
            
        if state.get("result"):
            state["verified"] = True
            state["next"] = cast(EdgeType, "end")
            return state
            
        state["attempts"] += 1
        state["next"] = cast(EdgeType, "process") if state["attempts"] < state["max_attempts"] else cast(EdgeType, "end")
        return state

    def _get_chat_history(self) -> List[HumanMessage | AIMessage]:
        """Convert memory to chat history format."""
        history = []
        for interaction in self.memory[-3:]:  # Last 3 interactions
            history.append(HumanMessage(content=interaction["input"]))
            history.append(AIMessage(content=interaction["output"]))
        return history

    def add_memory(self, interaction: Dict[str, Any]) -> None:
        """Add an interaction to memory."""
        self.memory.append(interaction)
        # Keep only last 10 interactions
        if len(self.memory) > 10:
            self.memory = self.memory[-10:]

    def get_context(self) -> str:
        """Get formatted context from recent memory."""
        if not self.memory:
            return "No previous context available."
        
        context = []
        for interaction in self.memory[-3:]:  # Last 3 interactions
            context.append(f"Human: {interaction.get('input', '')}")
            context.append(f"Assistant: {interaction.get('output', '')}\n")
        return "\n".join(context)

    async def aprocess(self, request: str) -> str:
        """
        Process a request asynchronously using the workflow graph.
        
        Args:
            request: The user's request
            
        Returns:
            The agent's response
        """
        try:
            # Initialize state with request and context
            initial_state = self._initialize_state(request, self.get_context())
            
            # Run the workflow
            final_state = await self.workflow.arun(initial_state)
            
            # Store interaction if successful
            if final_state.get("result"):
                self.add_memory({
                    "input": request,
                    "output": final_state["result"],
                    "tool_calls": final_state.get("tool_calls", [])
                })
                return final_state["result"]
            
            return f"Error processing request after {final_state['attempts']} attempts: {final_state.get('error', 'Unknown error')}"
            
        except Exception as e:
            error = f"Error processing request: {str(e)}"
            self.logger.error(error)
            return error

    def process(self, request: str) -> str:
        """Synchronous version of aprocess."""
        try:
            # Initialize state with request and context
            initial_state = self._initialize_state(request, self.get_context())
            
            # Run the workflow
            final_state = self.workflow.run(initial_state)
            
            # Store interaction if successful
            if final_state.get("result"):
                self.add_memory({
                    "input": request,
                    "output": final_state["result"],
                    "tool_calls": final_state.get("tool_calls", [])
                })
                return final_state["result"]
            
            return f"Error processing request after {final_state['attempts']} attempts: {final_state.get('error', 'Unknown error')}"
            
        except Exception as e:
            error = f"Error processing request: {str(e)}"
            self.logger.error(error)
            return error