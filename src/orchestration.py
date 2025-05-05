#!/usr/bin/env python3
"""
Orchestration module for the AI Project Management System.
Handles agent initialization and task management.
"""

import logging
import os
from typing import Dict, List, Any, Optional, Callable
from datetime import datetime

from langchain_ollama import OllamaLLM
from langchain_core.language_models import BaseLLM

from src.config import get_agent_config, get_ollama_config
from src.mcp_client import MCPClient
from src.agents.chat_coordinator import ChatCoordinatorAgent
from src.agents.project_manager import ProjectManagerAgent
from src.agents.agent_definitions import create_all_agents

# Set up logging
logger = logging.getLogger("ai_pm_system.orchestration")

class AgentOrchestrator:
    """
    Manages agent initialization and task assignment.
    """
    
    def __init__(self, llm: Optional[BaseLLM] = None, mcp_client: Optional[MCPClient] = None):
        """Initialize the orchestrator."""
        self.llm = llm
        self.mcp_client = mcp_client
        self.agents_dict = {}
        self.chat_coordinator = None
        
    async def initialize_system(self, event_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """Initialize the complete agent system."""
        try:
            # Initialize LLM if not provided
            if not self.llm:
                self.llm = self._initialize_llm()
            
            # Create base Project Manager for Jira integration
            self._create_base_project_manager()
            
            # Create Chat Coordinator
            self.chat_coordinator = self._create_chat_coordinator(event_callback)
            
            # Initialize all other agents
            self.agents_dict.update(create_all_agents(self.llm, self.mcp_client))
            
            # Add all agents to the Chat Coordinator
            for name, agent in self.agents_dict.items():
                self.chat_coordinator.add_agent(name, agent)
            
            # Update agent states for UI
            agent_states = {name: "idle" for name in self.agents_dict}
            
            return {
                "status": "success",
                "message": "Agent system initialized successfully",
                "agents": list(self.agents_dict.keys()),
                "agent_states": agent_states
            }
            
        except Exception as e:
            logger.error(f"Error initializing agent system: {e}")
            return {
                "status": "error",
                "message": f"Failed to initialize agent system: {str(e)}",
                "error": str(e)
            }
    
    def _initialize_llm(self) -> OllamaLLM:
        """Initialize the Ollama language model."""
        config = get_ollama_config()
        
        return OllamaLLM(
            model=config.get("model", "tinyllama"),
            base_url=config.get("base_url", "http://localhost:11434"),
            temperature=config.get("temperature", 0.7),
            request_timeout=config.get("request_timeout", 120.0),
            model_kwargs={
                "system": "You are a helpful AI assistant skilled in project management and software development."
            }
        )
    
    def _create_base_project_manager(self) -> None:
        """Create the base Project Manager agent for Jira integration."""
        self.agents_dict["project manager"] = ProjectManagerAgent(
            llm=self.llm,
            mcp_client=self.mcp_client
        )
    
    def _create_chat_coordinator(self, event_callback: Optional[Callable] = None) -> ChatCoordinatorAgent:
        """Create the Chat Coordinator agent."""
        coordinator = ChatCoordinatorAgent(
            llm=self.llm,
            mcp_client=self.mcp_client,
            agents=self.agents_dict.copy()
        )
        
        if event_callback:
            coordinator.set_event_callback(event_callback)
        
        return coordinator
    
    async def process_request(self, request: str, request_id: str = None) -> Dict[str, Any]:
        """Process a user request."""
        if not self.chat_coordinator:
            return {
                "status": "error",
                "message": "Agent system not initialized",
                "request_id": request_id
            }
            
        try:
            result = await self.chat_coordinator.process_message(request, request_id)
            return result
            
        except Exception as e:
            logger.error(f"Error processing request: {e}")
            return {
                "status": "error",
                "message": f"Error processing request: {str(e)}",
                "request_id": request_id
            }
