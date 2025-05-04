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

import websockets
from websockets.exceptions import ConnectionClosed
from fastapi import WebSocket, WebSocketDisconnect

from src.request_processor import RequestProcessor

# Set up logging
logger = logging.getLogger("ai_pm_system.web.ws_handlers")

class WebSocketManager:
    """
    Manages WebSocket connections and message handling.
    Implements a pub/sub model for broadcasting agent events.
    """
    
    def __init__(self, request_processor: RequestProcessor):
        """
        Initialize the WebSocket manager.
        
        Args:
            request_processor: The request processor to handle user requests
        """
        self.active_connections: Dict[str, WebSocket] = {}
        self.request_processor = request_processor
        self.connection_queue: asyncio.Queue = asyncio.Queue()
        self.event_handlers: Dict[str, List[Callable[..., Awaitable[None]]]] = {}
        
    async def connect(self, websocket: WebSocket, client_id: Optional[str] = None) -> str:
        """
        Accept a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection to accept
            client_id: Optional client ID, generated if not provided
            
        Returns:
            str: The client ID for this connection
        """
        await websocket.accept()
        
        # Generate client ID if not provided
        if not client_id:
            client_id = str(uuid.uuid4())
            
        self.active_connections[client_id] = websocket
        logger.info(f"WebSocket connection established for client {client_id}")
        
        return client_id
        
    async def disconnect(self, client_id: str) -> None:
        """
        Handle WebSocket disconnection.
        
        Args:
            client_id: The client ID to disconnect
        """
        if client_id in self.active_connections:
            del self.active_connections[client_id]
            logger.info(f"WebSocket connection closed for client {client_id}")
            
    async def broadcast(self, message: Dict[str, Any]) -> None:
        """
        Broadcast a message to all connected clients.
        
        Args:
            message: The message to broadcast
        """
        if not self.active_connections:
            return
            
        serialized_message = json.dumps(message)
        
        # Send to all active connections
        for client_id, websocket in list(self.active_connections.items()):
            try:
                await websocket.send_text(serialized_message)
            except (WebSocketDisconnect, ConnectionClosed):
                # Connection might have been closed
                await self.disconnect(client_id)
            except Exception as e:
                logger.error(f"Error broadcasting to client {client_id}: {e}")
                
    async def send_personal(self, client_id: str, message: Dict[str, Any]) -> bool:
        """
        Send a message to a specific client.
        
        Args:
            client_id: The client ID to send to
            message: The message to send
            
        Returns:
            bool: True if message was sent successfully, False otherwise
        """
        if client_id not in self.active_connections:
            return False
            
        serialized_message = json.dumps(message)
        
        try:
            await self.active_connections[client_id].send_text(serialized_message)
            return True
        except (WebSocketDisconnect, ConnectionClosed):
            # Connection might have been closed
            await self.disconnect(client_id)
            return False
        except Exception as e:
            logger.error(f"Error sending message to client {client_id}: {e}")
            return False
            
    async def handle_connection(self, websocket: WebSocket) -> None:
        """
        Handle a WebSocket connection.
        
        Args:
            websocket: The WebSocket connection to handle
        """
        client_id = await self.connect(websocket)
        
        try:
            # Send initial connection message
            await self.send_personal(client_id, {
                "type": "connection_established",
                "client_id": client_id,
                "message": "Connected to AI Project Management System"
            })
            
            # Send agent information
            agent_states = self.request_processor.orchestrator.get_agent_states()
            agent_descriptions = self.request_processor.orchestrator.get_agent_descriptions()
            
            await self.send_personal(client_id, {
                "type": "agent_info",
                "agent_states": agent_states,
                "agent_descriptions": agent_descriptions
            })
            
            # Handle incoming messages
            while True:
                try:
                    data = await websocket.receive_text()
                    await self.handle_message(client_id, data)
                except WebSocketDisconnect:
                    await self.disconnect(client_id)
                    break
                except Exception as e:
                    logger.error(f"Error handling WebSocket message from {client_id}: {e}")
                    # Try to send error message
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
        """
        Handle an incoming WebSocket message.
        
        Args:
            client_id: The client ID that sent the message
            data: The message data
        """
        try:
            message = json.loads(data)
            
            # Handle different message types
            if message["type"] == "request":
                await self.handle_request(client_id, message)
            elif message["type"] == "ping":
                await self.send_personal(client_id, {"type": "pong", "timestamp": message.get("timestamp")})
            elif message["type"] == "get_agent_status":
                await self.send_agent_status(client_id)
        except json.JSONDecodeError:
            logger.warning(f"Received invalid JSON from client {client_id}")
            await self.send_personal(client_id, {
                "type": "error",
                "message": "Invalid JSON in request"
            })
        except KeyError:
            logger.warning(f"Received message with missing fields from client {client_id}")
            await self.send_personal(client_id, {
                "type": "error",
                "message": "Missing required fields in request"
            })
        except Exception as e:
            logger.error(f"Error handling message from client {client_id}: {e}")
            await self.send_personal(client_id, {
                "type": "error",
                "message": f"Error processing message: {str(e)}"
            })
            
    async def handle_request(self, client_id: str, message: Dict[str, Any]) -> None:
        """
        Handle a request message.
        
        Args:
            client_id: The client ID that sent the message
            message: The message data
        """
        user_request = message.get("text", "")
        request_id = message.get("id", str(uuid.uuid4()))
        
        # Send acknowledgment
        await self.send_personal(client_id, {
            "type": "request_received",
            "request_id": request_id,
            "message": "Request received and processing started"
        })
        
        # Process the request asynchronously
        asyncio.create_task(self.process_request(client_id, user_request, request_id))
        
    async def process_request(self, client_id: str, user_request: str, request_id: str) -> None:
        """
        Process a user request and send the response.
        
        Args:
            client_id: The client ID that sent the request
            user_request: The user request text
            request_id: The request ID
        """
        try:
            # Define an event handler to send real-time updates
            async def event_handler(event_type: str, **kwargs):
                event_data = {
                    "type": event_type,
                    "timestamp": kwargs.get("timestamp", datetime.now().isoformat()),
                    "request_id": request_id,
                    **{k: v for k, v in kwargs.items() if k != "timestamp"}
                }
                await self.send_personal(client_id, event_data)
            
            # Process the request
            result = await self.request_processor.process_request(
                user_request=user_request,
                request_id=request_id,
                event_handler=event_handler
            )
            
            # Send the final response
            await self.send_personal(client_id, {
                "type": "response",
                "request_id": request_id,
                "status": result["status"],
                "processed_by": result["processed_by"],
                "involved_agents": result.get("involved_agents", []),
                "response": result["response"],
                "timestamp": datetime.now().isoformat()
            })
        except Exception as e:
            logger.error(f"Error processing request from client {client_id}: {e}")
            await self.send_personal(client_id, {
                "type": "error",
                "request_id": request_id,
                "message": f"Error processing request: {str(e)}"
            })
            
    async def send_agent_status(self, client_id: str) -> None:
        """
        Send current agent status to a client.
        
        Args:
            client_id: The client ID to send to
        """
        agent_states = self.request_processor.orchestrator.get_agent_states()
        
        await self.send_personal(client_id, {
            "type": "agent_status_update",
            "agent_states": agent_states,
            "timestamp": datetime.now().isoformat()
        })
        
    def register_event_handler(self, event_type: str, handler: Callable[..., Awaitable[None]]) -> None:
        """
        Register an event handler for a specific event type.
        
        Args:
            event_type: The event type to handle
            handler: The handler function
        """
        if event_type not in self.event_handlers:
            self.event_handlers[event_type] = []
            
        self.event_handlers[event_type].append(handler)
        
    async def trigger_event(self, event_type: str, **kwargs) -> None:
        """
        Trigger an event and call all registered handlers.
        
        Args:
            event_type: The event type to trigger
            **kwargs: Event data
        """
        if event_type not in self.event_handlers:
            return
            
        for handler in self.event_handlers[event_type]:
            try:
                await handler(**kwargs)
            except Exception as e:
                logger.error(f"Error in event handler for {event_type}: {e}")

# Add missing import
from datetime import datetime
