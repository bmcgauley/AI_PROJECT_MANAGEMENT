"""
Base Agent abstract class implementation.
This follows the pattern recommended in theGospel.md to ensure a consistent interface
across all agent implementations.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional

class BaseAgent(ABC):
    """Abstract base class for all agents in the system."""
    
    @abstractmethod
    def run(self, request: str) -> Dict[str, Any]:
        """
        Run the agent with the given request.
        
        Args:
            request: The request to process
            
        Returns:
            Dictionary with response and other metadata
        """
        pass
    
    @abstractmethod
    def initialize(self) -> None:
        """
        Initialize the agent with any necessary setup.
        Should be called before the first run.
        """
        pass
    
    @property
    @abstractmethod
    def name(self) -> str:
        """Get the agent's name."""
        pass
    
    @property
    @abstractmethod
    def description(self) -> str:
        """Get the agent's description."""
        pass
