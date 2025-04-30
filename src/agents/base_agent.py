"""
Base Agent class for the AI Project Management System.
All specialized agents inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.
    Provides common functionality and enforces interface requirements.
    Includes support for an MCP client.
    """
    
    def __init__(self, llm, name: str, description: str, mcp_client: Optional[Any] = None):
        """
        Initialize the base agent.
        
        Args:
            llm: Language model to use for responses
            name: Name identifier for the agent
            description: Description of the agent's role and capabilities
            mcp_client: Optional client for interacting with MCP servers.
        """
        self.llm = llm
        self.name = name
        self.description = description
        self.mcp_client = mcp_client # Added MCP client instance
        self.logger = logging.getLogger(f"agent.{name}")
        self.logger.info(f"Initialized {name} agent")
        self.memory = []  # Simple memory to store past interactions
    
    @abstractmethod
    def process(self, request: Dict[str, Any]) -> Any:
        """
        Process a request and generate a response.
        Must be implemented by all concrete agent classes.
        
        Args:
            request: The request to process
            
        Returns:
            The agent's response
        """
        pass
    
    def store_memory(self, interaction: Dict[str, Any]) -> None:
        """
        Store an interaction in the agent's memory.
        
        Args:
            interaction: Dictionary containing the interaction details
        """
        self.memory.append(interaction)
        # Keep memory at a reasonable size by removing oldest entries if too large
        if len(self.memory) > 50:
            self.memory.pop(0)
    
    def get_memory(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
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
    
    def _format_log(self, message: str) -> None:
        """
        Format and log a message.
        
        Args:
            message: The message to log
        """
        self.logger.info(f"{self.name}: {message}")
    
    def __str__(self) -> str:
        """String representation of the agent."""
        return f"{self.name} - {self.description}"
