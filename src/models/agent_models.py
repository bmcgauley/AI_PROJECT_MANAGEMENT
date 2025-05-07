"""
Pydantic models for agent state management in the AI Project Management System.
"""

from pydantic import BaseModel, Field
from typing import Dict, List, Optional, Any, Union, Literal, cast
from enum import Enum
from datetime import datetime
from langchain_core.messages import HumanMessage, AIMessage, SystemMessage, FunctionMessage

class ToolPermission(BaseModel):
    """Model representing tool permissions for agents."""
    server: str
    tools: List[str]

class AgentType(str, Enum):
    """Enum of available agent types."""
    PROJECT_MANAGER = "project_manager"
    RESEARCHER = "researcher"
    CODE_DEVELOPER = "code_developer"
    BUSINESS_ANALYST = "business_analyst"
    CHAT_COORDINATOR = "chat_coordinator"
    CODE_REVIEWER = "code_reviewer"
    REPORT_DRAFTER = "report_drafter"
    REPORT_PUBLISHER = "report_publisher"
    REPORT_REVIEWER = "report_reviewer"
    REQUEST_PARSER = "request_parser"
    
class AgentMemoryItem(BaseModel):
    """Model representing a single item in an agent's memory."""
    timestamp: datetime = Field(default_factory=datetime.now)
    input: str
    output: str
    tool_calls: Optional[List[Dict[str, Any]]] = None
    
class AgentConfig(BaseModel):
    """Configuration for an agent."""
    name: str
    description: str
    agent_type: AgentType
    available_tools: Dict[str, List[str]] = Field(default_factory=dict)
    system_prompt: Optional[str] = None
    
class EdgeType(str, Enum):
    """Enum for graph edge types."""
    PROCESS = "process"
    VERIFY = "verify"
    TOOL = "tool"
    END = "end"
    ERROR = "error"
    SUCCESS = "success"

class AgentState(BaseModel):
    """Model representing the current state of an agent."""
    input: str
    context: str = ""
    attempts: int = 0
    max_attempts: int = 3
    verified: bool = False
    chat_history: List[Union[HumanMessage, AIMessage, SystemMessage, FunctionMessage]] = Field(default_factory=list)
    result: Optional[str] = None
    error: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    next: Optional[EdgeType] = None
    
    class Config:
        arbitrary_types_allowed = True

class AgentResponse(BaseModel):
    """Model representing an agent's response."""
    agent_name: str
    content: str
    thought_process: Optional[str] = None
    tool_calls: List[Dict[str, Any]] = Field(default_factory=list)
    state: Optional[Dict[str, Any]] = None
    error: Optional[str] = None
    timestamp: datetime = Field(default_factory=datetime.now)

class ProjectSummary(BaseModel):
    """Model representing a project summary."""
    project_id: str
    name: str
    description: str
    status: str = "planning"
    creation_date: datetime = Field(default_factory=datetime.now)
    last_updated: datetime = Field(default_factory=datetime.now)
    team_members: List[str] = Field(default_factory=list)
    tasks: List[Dict[str, Any]] = Field(default_factory=list)
    milestones: List[Dict[str, Any]] = Field(default_factory=list)
    metadata: Dict[str, Any] = Field(default_factory=dict)
    
    class Config:
        arbitrary_types_allowed = True
