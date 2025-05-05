#!/usr/bin/env python3
"""
Modern WebSocket handlers for the AI Project Management System.
Handles WebSocket connections for agents using Pydantic and LangGraph.
"""

import asyncio
import json
import logging
import uuid
from typing import Dict, List, Any, Optional, Callable, Awaitable
from datetime import datetime

from fastapi import WebSocket, WebSocketDisconnect
from pydantic import BaseModel

from src.models.agent_models import AgentResponse

# Set up logging
logger = logging.getLogger("ai_pm_system.web.modern_ws_handlers")

class ModernWebSocketManager:
    """Manages WebSocket connections for the modern agent architecture."""

    def __init__(self):
        """Initialize the WebSocket manager."""
        self.active_connections: Dict[str, WebSocket] = {}
        self.event_handlers: Dict[str, List[Callable[..., Awaitable[None]]]] = {}
        self._setup_event_handlers()
        self.initialization_event = asyncio.Event()
        self.initialized = False
        logger.info("Modern WebSocket manager initialized")

    def set_initialized(self, value: bool = True) -> None:
        """Set initialization status and trigger the event if initialized."""
        self.initialized = value
        if value:
            self.initialization_event.set()
            logger.info("Modern system initialization complete, notifying clients")
        else:
            self.initialization_event.clear()

    async def connect(self, websocket: WebSocket) -> str:
        """Accept a new WebSocket connection."""
        try:
            await websocket.accept()
            client_id = str(uuid.uuid4())
            self.active_connections[client_id] = websocket
            logger.info(f"New client connected with ID: {client_id}")
            return client_id
        except Exception as e:
            logger.error(f"Error accepting WebSocket connection: {str(e)}")
            # Generate a client ID even if there was an error
            # This prevents errors in the calling code
            return str(uuid.uuid4())

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
                logger.debug(f"Message sent to client {client_id}: {message['type']}")
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
        self.register_event_handler("agent_thinking", self._handle_agent_thinking)
        self.register_event_handler("request_complete", self._handle_request_complete)
        self.register_event_handler("workflow_step", self._handle_workflow_step)
        self.register_event_handler("system_initialized", self._handle_system_initialized)
        # IMPORTANT: Register handler for new_request event
        self.register_event_handler("new_request", self._handle_new_request)

    async def _handle_system_initialized(self, **kwargs) -> None:
        """Handle system initialization event."""
        self.set_initialized(True)
        await self.broadcast("system_status", status="initialized")

    async def _handle_new_request(self, **kwargs) -> None:
        """Handle new request events."""
        client_id = kwargs.get("client_id")
        content = kwargs.get("content")
        request_id = kwargs.get("request_id")
        
        logger.info(f"Processing new request from client {client_id}: {content[:50]}...")
        
        # This will be implemented by the orchestrator that sets up this manager
        # Just log it for now
        logger.info(f"Request {request_id} from {client_id} requires orchestrator processing")

    async def handle_agent_event(self, event_type: str, **kwargs) -> None:
        """Handle and broadcast agent events to clients."""
        try:
            request_id = kwargs.pop("request_id", None)
            
            event_data = {
                "type": event_type,
                "timestamp": kwargs.pop("timestamp", datetime.now().isoformat()),
                **kwargs
            }
            
            if request_id:
                event_data["request_id"] = request_id
            
            # Broadcast event
            await self.broadcast(event_type, **event_data)
            
            # Trigger any registered handlers for this event type
            await self.trigger_event(event_type, request_id=request_id, **kwargs)
            
        except Exception as e:
            logger.error(f"Error in agent event handler: {str(e)}")

    async def handle_connection(self, websocket: WebSocket) -> None:
        """Handle a new WebSocket connection."""
        client_id = await self.connect(websocket)
        
        try:
            # Check if system is initialized
            if not self.initialized:
                # Notify client about initialization status
                await self.send_personal(client_id, {
                    "type": "system_status",
                    "status": "initializing",
                    "message": "Modern agent system is initializing. Please wait..."
                })
                
                logger.info(f"Client {client_id} connected while system is initializing, waiting...")
                
                # Wait for initialization with timeout (30 seconds)
                try:
                    initialization_task = asyncio.create_task(self.initialization_event.wait())
                    done, pending = await asyncio.wait(
                        [initialization_task],
                        timeout=30.0,
                        return_when=asyncio.FIRST_COMPLETED
                    )
                    
                    if initialization_task in pending:
                        await self.send_personal(client_id, {
                            "type": "system_status",
                            "status": "initialization_delayed",
                            "message": "System initialization is taking longer than expected. Please wait..."
                        })
                        
                except asyncio.CancelledError:
                    logger.warning(f"Waiting for initialization was cancelled for client {client_id}")
            
            # Send initial connection message
            await self.send_personal(client_id, {
                "type": "connection_established",
                "client_id": client_id,
                "message": "Connected to AI Project Management System with Modern Agent Architecture",
                "system_ready": self.initialized
            })
            
            # Handle incoming messages
            while True:
                try:
                    data = await websocket.receive_text()
                    logger.debug(f"Received message from client {client_id}: {data[:100]}...")
                    
                    # Check if system is initialized before processing requests
                    if not self.initialized:
                        await self.send_personal(client_id, {
                            "type": "system_status",
                            "status": "not_ready",
                            "message": "Modern agent system is still initializing. Please wait."
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
                
                # Send request_start event to acknowledge receipt
                await self.send_personal(client_id, {
                    "type": "request_start",
                    "request_id": request_id,
                    "message": "Processing your request..."
                })
                
                logger.info(f"Received request from client {client_id}, request_id: {request_id}")
                
                # Process the request with event triggering
                await self.trigger_event("new_request", 
                                       client_id=client_id, 
                                       content=message["content"], 
                                       request_id=request_id)
                
        except json.JSONDecodeError:
            logger.error(f"Invalid JSON from client {client_id}")
            await self.send_personal(client_id, {
                "type": "error",
                "message": "Invalid request format. Please send valid JSON."
            })
        except KeyError as e:
            logger.error(f"Missing required field in message from {client_id}: {e}")
            await self.send_personal(client_id, {
                "type": "error",
                "message": f"Missing required field: {str(e)}"
            })
        except Exception as e:
            logger.error(f"Error processing message from {client_id}: {e}")
            await self.send_personal(client_id, {
                "type": "error",
                "message": f"Error processing message: {str(e)}"
            })

    async def handle_agent_response(self, client_id: str, response: AgentResponse, request_id: str) -> None:
        """Handle an agent response and send it to the client."""
        try:
            # Convert Pydantic model to dict for JSON serialization
            response_dict = response.model_dump() if hasattr(response, "model_dump") else response.dict()
            
            # Add request_id
            response_dict["request_id"] = request_id
            
            await self.send_personal(client_id, {
                "type": "response",
                "content": response_dict
            })
            
            # Broadcast completion event
            await self.broadcast("request_complete", request_id=request_id)
            
        except Exception as e:
            error_msg = f"Error handling agent response: {str(e)}"
            logger.error(error_msg)
            
            await self.send_personal(client_id, {
                "type": "response",
                "content": {
                    "status": "error",
                    "agent_name": "System",
                    "content": f"An error occurred while processing your request: {str(e)}",
                    "request_id": request_id
                }
            })

    def register_event_handler(self, event_type: str, handler: Callable[..., Awaitable[None]]) -> None:
        """Register a handler for a specific event type."""
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
        self.event_handlers[event_type].append(handler)
        logger.debug(f"Registered handler for event type: {event_type}")

    async def trigger_event(self, event_type: str, **kwargs) -> None:
        """Trigger all handlers for a specific event type."""
        if event_type in self.event_handlers:
            logger.debug(f"Triggering {len(self.event_handlers[event_type])} handlers for event type: {event_type}")
            for handler in self.event_handlers[event_type]:
                try:
                    await handler(**kwargs)
                except Exception as e:
                    logger.error(f"Error in event handler for {event_type}: {e}")
        else:
            logger.warning(f"No handlers registered for event type: {event_type}")

    # Event handler methods
    async def _handle_agent_thinking(self, **kwargs) -> None:
        """Handle agent thinking events."""
        agent = kwargs.get("agent_name")
        if agent:
            await self.broadcast("agent_status_update", agent_name=agent, status="thinking")

    async def _handle_request_complete(self, **kwargs) -> None:
        """Handle request completion events."""
        await self.broadcast("agent_states_update", status="idle")

    async def _handle_workflow_step(self, **kwargs) -> None:
        """Handle workflow step events."""
        agent = kwargs.get("agent_name")
        step = kwargs.get("step")
        if agent:
            await self.broadcast("agent_status_update", 
                               agent_name=agent, 
                               status="working", 
                               step=step)
