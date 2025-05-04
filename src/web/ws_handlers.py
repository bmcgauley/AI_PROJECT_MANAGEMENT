#!/usr/bin/env python3
"""
WebSocket handlers for the AI Project Management System.
Handles WebSocket connections, events, and real-time updates.
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, List, Any, Optional, Callable, Awaitable
from datetime import datetime

import websockets
from websockets.exceptions import ConnectionClosed
from fastapi import WebSocket, WebSocketDisconnect

from src.request_processor import RequestProcessor
from src.agents.chat_coordinator import ChatCoordinatorAgent

# Set up logging
logger = logging.getLogger("ai_pm_system.web.ws_handlers")

class WebSocketManager:
    """Manages WebSocket connections and real-time updates."""

    def __init__(self, request_processor: RequestProcessor):
        """Initialize the WebSocket manager."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.request_processor = request_processor
        self.event_handlers: Dict[str, List[Callable[..., Awaitable[None]]]] = {}
        self._setup_event_handlers()
        self.initialization_event = asyncio.Event()  # Event for signaling system initialization
        self.initialized = False
        self.broadcast_event = self.broadcast  # Alias for compatibility
        logger.info("WebSocket manager initialized")

    def set_initialized(self, value: bool = True) -> None:
        """Set initialization status and trigger the event if initialized."""
        self.initialized = value
        if value:
            self.initialization_event.set()
            logger.info("System initialization complete, notifying clients")
        else:
            self.initialization_event.clear()

    async def connect(self, websocket: WebSocket) -> str:
        """Accept a new WebSocket connection."""
        await websocket.accept()
        client_id = str(uuid.uuid4())
        self.active_connections[client_id] = websocket
        return client_id

    async def disconnect(self, client_id: str) -> None:
        """Handle client disconnection."""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].close()
            except Exception:
                pass
            del self.active_connections[client_id]
            logger.info(f"Client {client_id} removed from active connections")

    async def close_all(self) -> None:
        """Close all active connections."""
        for client_id in list(self.active_connections.keys()):
            await self.disconnect(client_id)
        logger.info("All WebSocket connections closed")

    async def send_personal(self, client_id: str, message: Dict[str, Any]) -> None:
        """Send a message to a specific client."""
        if client_id in self.active_connections:
            try:
                await self.active_connections[client_id].send_json(message)
            except Exception as e:
                logger.error(f"Error sending message to {client_id}: {e}")
                await self.disconnect(client_id)

    async def broadcast(self, event_type: str, **kwargs) -> None:
        """Broadcast a message to all connected clients."""
        message = {
            "type": event_type,
            "timestamp": datetime.now().isoformat(),
            **kwargs
        }
        
        disconnected_clients = []
        for client_id in list(self.active_connections.keys()):
            try:
                await self.send_personal(client_id, message)
            except Exception as e:
                logger.error(f"Error broadcasting to {client_id}: {e}")
                disconnected_clients.append(client_id)
        
        # Clean up disconnected clients
        for client_id in disconnected_clients:
            await self.disconnect(client_id)

    def _setup_event_handlers(self) -> None:
        """Set up handlers for different event types."""
        self.register_event_handler("agent_handoff", self._handle_agent_handoff)
        self.register_event_handler("agent_thinking", self._handle_agent_thinking)
        self.register_event_handler("request_complete", self._handle_request_complete)
        self.register_event_handler("workflow_step", self._handle_workflow_step)
        self.register_event_handler("system_initialized", self._handle_system_initialized)

    async def _handle_system_initialized(self, **kwargs) -> None:
        """Handle system initialization event."""
        self.set_initialized(True)
        await self.broadcast("system_status", status="initialized")

    async def handle_agent_event(self, event_type: str, **kwargs) -> None:
        """Handle and broadcast agent events to clients."""
        try:
            # Get the request_id if present
            request_id = kwargs.get("request_id")
            
            # Create the event data
            event_data = {
                "type": event_type,
                "timestamp": kwargs.get("timestamp", datetime.now().isoformat()),
                **{k: v for k, v in kwargs.items() if k != "timestamp"}
            }
            
            # Update agent states if applicable
            if event_type == "agent_handoff" and "to_agent" in kwargs:
                if hasattr(self.request_processor, 'agent_states'):
                    self.request_processor.agent_states[kwargs["to_agent"]] = "active"
            
            # Broadcast event
            await self.broadcast(event_type, **kwargs)
            
            # Trigger any registered handlers for this event type
            await self.trigger_event(event_type, **kwargs)
            
        except Exception as e:
            logger.error(f"Error handling agent event {event_type}: {e}")

    async def handle_connection(self, websocket: WebSocket) -> None:
        """Handle a new WebSocket connection."""
        await websocket.accept()
        client_id = str(uuid.uuid4())
        self.active_connections[client_id] = websocket
        
        try:
            # Check if system is initialized
            system_ready = self.initialized
            if not system_ready and hasattr(self.request_processor, 'initialized'):
                system_ready = self.request_processor.initialized

            if not system_ready:
                # Notify client about initialization status
                await self.send_personal(client_id, {
                    "type": "system_status",
                    "status": "initializing",
                    "message": "System is initializing. Please wait..."
                })
                
                logger.info(f"Client {client_id} connected while system is initializing, waiting...")
                
                # Set a timeout for waiting (30 seconds maximum)
                try:
                    # Wait for initialization to complete with timeout
                    initialization_task = asyncio.create_task(self.initialization_event.wait())
                    done, pending = await asyncio.wait(
                        [initialization_task],
                        timeout=30.0,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    if initialization_task in pending:
                        # Timeout occurred, notify client but don't disconnect
                        await self.send_personal(client_id, {
                            "type": "system_status",
                            "status": "initialization_delayed",
                            "message": "System initialization is taking longer than expected. Please wait..."
                        })
                    
                    # Check system status again after waiting
                    system_ready = self.initialized
                    if hasattr(self.request_processor, 'initialized'):
                        system_ready = self.request_processor.initialized or self.initialized
                        
                except asyncio.CancelledError:
                    logger.warning(f"Waiting for initialization was cancelled for client {client_id}")
                    
            # At this point, either system is ready or we've waited
            # If it's still not ready after waiting, we'll send updates but not disconnect
            
            # Send initial connection message
            await self.send_personal(client_id, {
                "type": "connection_established",
                "client_id": client_id,
                "message": "Connected to AI Project Management System",
                "system_ready": system_ready
            })
            
            # Send agent information if available
            agent_states = {}
            agent_descriptions = {}
            
            if self.request_processor and hasattr(self.request_processor, 'agent_states'):
                agent_states = self.request_processor.agent_states
                
                # Get agent descriptions if coordinator is initialized
                if hasattr(self.request_processor, 'coordinator') and self.request_processor.coordinator:
                    available_agents = self.request_processor.coordinator.get_available_agents()
                    agent_descriptions = {
                        name: desc for name, desc in [
                            line.split(": ", 1) for line in available_agents.split("\n") if ": " in line
                        ]
                    }
            
            await self.send_personal(client_id, {
                "type": "agent_info",
                "agent_states": agent_states,
                "agent_descriptions": agent_descriptions,
                "system_ready": system_ready
            })
            
            # Handle incoming messages
            while True:
                try:
                    data = await websocket.receive_text()
                    
                    # Check if system is initialized before processing requests
                    is_ready = self.initialized
                    if hasattr(self.request_processor, 'initialized'):
                        is_ready = self.request_processor.initialized or self.initialized
                    
                    if not is_ready:
                        await self.send_personal(client_id, {
                            "type": "system_status",
                            "status": "not_ready",
                            "message": "System is still initializing. Please wait before sending requests."
                        })
                        continue
                        
                    await self.handle_message(client_id, data)
                except WebSocketDisconnect:
                    logger.info(f"Client {client_id} disconnected")
                    await self.disconnect(client_id)
                    break
                except Exception as e:
                    logger.error(f"Error handling WebSocket message from {client_id}: {e}")
                    try:
                        await self.send_personal(client_id, {
                            "type": "error",
                            "message": f"Error processing message: {str(e)}"
                        })
                    except Exception:
                        pass
                    
        except Exception as e:
            logger.error(f"WebSocket error for {client_id}: {e}")
            await self.disconnect(client_id)

    async def handle_message(self, client_id: str, data: str) -> None:
        """Handle an incoming message from a client."""
        try:
            message = json.loads(data)
            
            if message["type"] == "request":
                # Generate request ID if not provided
                request_id = message.get("request_id", str(uuid.uuid4()))
                
                # Send request_start event
                await self.send_personal(client_id, {
                    "type": "request_start",
                    "request_id": request_id
                })
                
                # Process the request
                await self.process_request(client_id, message["content"], request_id)
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from client {client_id}")
        except KeyError as e:
            logger.error(f"Missing required field in message from {client_id}: {e}")
        except Exception as e:
            logger.error(f"Error processing message from {client_id}: {e}")

    async def process_request(self, client_id: str, user_request: str, request_id: str) -> None:
        """Process a user request through the request processor."""
        try:
            response = await self.request_processor.process_request(
                user_request, 
                request_id=request_id
            )
            
            await self.send_personal(client_id, {
                "type": "response",
                "content": response
            })
            
        except Exception as e:
            error_msg = f"Error processing request: {str(e)}"
            logger.error(error_msg)
            
            await self.send_personal(client_id, {
                "type": "response",
                "content": {
                    "status": "error",
                    "processed_by": "System",
                    "response": f"An error occurred while processing your request: {str(e)}",
                    "request_id": request_id
                }
            })

    def register_event_handler(self, event_type: str, handler: Callable[..., Awaitable[None]]) -> None:
        """Register a handler for a specific event type."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)

    async def trigger_event(self, event_type: str, **kwargs) -> None:
        """Trigger all handlers for a specific event type."""
        if event_type in self.event_handlers:
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(**kwargs)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")

    # Event handler methods
    async def _handle_agent_handoff(self, **kwargs) -> None:
        """Handle agent handoff events."""
        if hasattr(self.request_processor, 'agent_states'):
            from_agent = kwargs.get("from_agent")
            to_agent = kwargs.get("to_agent")
            if from_agent:
                self.request_processor.agent_states[from_agent] = "idle"
            if to_agent:
                self.request_processor.agent_states[to_agent] = "active"

    async def _handle_agent_thinking(self, **kwargs) -> None:
        """Handle agent thinking events."""
        agent = kwargs.get("agent")
        if agent and hasattr(self.request_processor, 'agent_states'):
            self.request_processor.agent_states[agent] = "thinking"

    async def _handle_request_complete(self, **kwargs) -> None:
        """Handle request completion events."""
        if hasattr(self.request_processor, 'agent_states'):
            # Reset all agent states to idle
            for agent in self.request_processor.agent_states:
                self.request_processor.agent_states[agent] = "idle"

    async def _handle_workflow_step(self, **kwargs) -> None:
        """Handle workflow step events."""
        agent = kwargs.get("agent")
        if agent and hasattr(self.request_processor, 'agent_states'):
            self.request_processor.agent_states[agent] = "working"
