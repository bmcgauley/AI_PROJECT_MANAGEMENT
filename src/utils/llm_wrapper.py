"""
Custom LLM wrappers for compatibility with different LangChain/LangGraph versions.
"""

from typing import Any, Dict, List, Optional, Sequence
from langchain_ollama import OllamaLLM
from langchain_core.callbacks import BaseCallbackManager
from langchain_core.language_models.llms import LLM
from langchain_core.tools import BaseTool
import logging

# Set up logging
logger = logging.getLogger("ai_pm_system.utils.llm_wrapper")

class CompatibleOllamaLLM(OllamaLLM):
    """
    A wrapper around OllamaLLM that adds compatibility with 
    newer LangGraph versions requiring the bind_tools method.
    
    This wrapper specifically addresses compatibility with LangGraph 0.2.69
    which expects LLM objects to have a bind_tools method.
    """
    
    def bind_tools(self, tools: Sequence[BaseTool]) -> LLM:
        """
        Add tools to this LLM for use in LangGraph ReAct agents.
        This method is required by newer versions of LangGraph.
        
        Args:
            tools: A sequence of tools to bind to the LLM
            
        Returns:
            The LLM itself for chaining
        """
        logger.info(f"Binding {len(tools)} tools to CompatibleOllamaLLM")
        # Store the tools for later use if needed
        self._tools = tools
        # Simply return self as this model doesn't need special handling
        return self
        
    def get_tools(self) -> Optional[Sequence[BaseTool]]:
        """
        Get the tools bound to this LLM.
        
        Returns:
            The sequence of tools, if any
        """
        return getattr(self, "_tools", None)
