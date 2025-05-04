#!/usr/bin/env python3
"""
Request processor for the AI Project Management System.
Handles incoming requests and coordinates agent responses.
"""

import logging
import asyncio
from typing import Dict, Any, Optional, Callable

from src.orchestration import AgentOrchestrator
from src.mcp_client import MCPClient

logger = logging.getLogger("ai_pm_system.request_processor")

class RequestProcessor:
    """Processes requests and coordinates agent responses."""

    def __init__(self, orchestrator: AgentOrchestrator, mcp_client: MCPClient):
        """Initialize the request processor."""
        self.orchestrator = orchestrator
        self.mcp_client = mcp_client
        self.coordinator = None
        self.event_handler = None
        self.agent_states = {}  # Tracks agent states for UI
        self.initialized = False  # Add initialization flag
        self.ws_manager = None  # Reference to WebSocketManager, will be set later

    def set_ws_manager(self, ws_manager) -> None:
        """Set the WebSocketManager reference for initialization signaling."""
        self.ws_manager = ws_manager
        logger.info("WebSocketManager reference set in RequestProcessor")

    async def initialize(self, event_handler: Optional[Callable] = None) -> None:
        """Initialize the request processor with a chat coordinator."""
        try:
            self.coordinator = self.orchestrator.chat_coordinator
            self.event_handler = event_handler
            
            # Set up initial agent states
            if self.coordinator:
                available_agents = self.coordinator.get_available_agents()
                for line in available_agents.split("\n"):
                    if ": " in line:
                        name = line.split(": ", 1)[0]
                        self.agent_states[name] = "idle"
                
                # Only set initialized to True if coordinator is properly set
                self.initialized = True
                logger.info("Request processor successfully initialized with ChatCoordinatorAgent")
                
                # Notify the WebSocketManager that system is initialized
                if self.ws_manager:
                    self.ws_manager.set_initialized(True)
                    await self.notify_system_initialized()
                else:
                    logger.warning("WebSocketManager not set, can't signal initialization")
            else:
                logger.error("Failed to initialize RequestProcessor: ChatCoordinatorAgent not available")
                self.initialized = False
        except Exception as e:
            logger.error(f"Error during RequestProcessor initialization: {str(e)}")
            self.initialized = False
            raise

    async def notify_system_initialized(self) -> None:
        """Notify clients that the system is fully initialized."""
        if self.event_handler:
            try:
                await self.event_handler(
                    "system_initialized",
                    message="AI Project Management System initialized successfully",
                    agent_count=len(self.agent_states)
                )
                logger.info("System initialization event sent to clients")
            except Exception as e:
                logger.error(f"Error sending system initialization event: {str(e)}")

    async def process_request(self, 
                            user_request: str, 
                            request_id: str = None,
                            event_handler: Any = None) -> Dict[str, Any]:
        """
        Process a user request through the ChatCoordinatorAgent interface.
        
        Args:
            user_request: The user's request text
            request_id: Optional unique identifier for the request
            event_handler: Optional event handler for real-time updates
            
        Returns:
            Dict[str, Any]: Response containing the processing result
        """
        if not self.initialized or not self.coordinator:
            return {
                "status": "error",
                "processed_by": "System",
                "response": "The agent system is not initialized yet. Please try again later.",
                "request_id": request_id
            }
        
        try:
            # If a one-time event handler is provided, use it for this request
            if event_handler:
                original_handler = self.coordinator.event_callback
                self.coordinator.set_event_callback(event_handler)
            
            # Process the request through the ChatCoordinatorAgent
            result = await self.coordinator.process_message(user_request)
            
            # Restore the original event handler if we used a one-time handler
            if event_handler:
                self.coordinator.set_event_callback(original_handler)
            
            return result
            
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            logger.error(error_msg)
            
            if self.event_handler:
                await self.event_handler("request_error", message=error_msg, request_id=request_id)
            
            return {
                "status": "error",
                "processed_by": "System",
                "response": f"An error occurred while processing your request: {str(e)}",
                "error": str(e),
                "request_id": request_id
            }

    async def cleanup(self) -> None:
        """Clean up any resources used by the request processor."""
        # Reset all agent states
        for agent in self.agent_states:
            self.agent_states[agent] = "idle"
        
        # Clear any temporary resources
        if self.coordinator:
            await self.coordinator.cleanup()  # Assuming ChatCoordinatorAgent has a cleanup method
