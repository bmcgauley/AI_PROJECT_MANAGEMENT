#!/usr/bin/env python3
"""
Modern FastAPI application setup for AI Project Management System.
Integrates with modern agents using Pydantic and LangGraph.
"""

import logging
import os
import asyncio
import uuid
from typing import Dict, Any, Optional, Callable, Awaitable
from functools import wraps

from fastapi import FastAPI, WebSocket, WebSocketDisconnect, Request, Depends, HTTPException
from fastapi.responses import HTMLResponse, JSONResponse, RedirectResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from fastapi.middleware.cors import CORSMiddleware
from pydantic import BaseModel
from starlette.routing import WebSocketRoute

from src.models.agent_models import AgentResponse
from .modern_ws_handlers import ModernWebSocketManager
from .api_routes import api_router, setup_api_router, set_orchestrator  # Import the set_orchestrator function

# Set up logging
logger = logging.getLogger("ai_pm_system.web.modern_app")

# Create the FastAPI application
app = FastAPI(
    title="AI Project Management System",
    description="Modern agent architecture using Pydantic and LangGraph",
    version="2.0.0",
    docs_url="/api/docs",
    redoc_url="/api/redoc",
    openapi_url="/api/openapi.json"
)

# Add CORS middleware
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],  # For development; restrict in production
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Mount static files
app.mount("/static", StaticFiles(directory="src/web/static"), name="static")

# Set up Jinja2 templates
templates = Jinja2Templates(directory="src/web/templates")

class RequestModel(BaseModel):
    """Pydantic model for API requests."""
    content: str
    request_id: Optional[str] = None

# WebSocket handler reference - will be updated during initialization
ws_handler: Callable[[WebSocket], Awaitable[None]] = None

# Add basic routes immediately that don't require the orchestrator
@app.get("/test", response_class=HTMLResponse)
async def test_route():
    """Test route to verify routing is working."""
    return HTMLResponse(content="<h1>Modern Agent System is Running!</h1>", status_code=200)

@app.get("/ping")
async def ping():
    """Health check ping endpoint."""
    return {"status": "ok", "message": "pong"}

@app.get("/", response_class=HTMLResponse)
async def root(request: Request):
    """Serve the main interface or redirect to it."""
    try:
        return templates.TemplateResponse("index.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering index.html: {e}")
        return HTMLResponse("<h1>AI Project Management System</h1><p>Welcome! The system is starting up...</p>")

@app.get("/modern", response_class=HTMLResponse)
async def modern_index(request: Request):
    """Serve the modern interface."""
    try:
        return templates.TemplateResponse("modern_index.html", {"request": request})
    except Exception as e:
        logger.error(f"Error rendering modern_index.html: {e}")
        return HTMLResponse("<h1>Modern Agent System</h1><p>The interface is loading...</p>")

# Initial placeholder WebSocket handler
async def placeholder_ws_handler(websocket: WebSocket) -> None:
    """
    Placeholder WebSocket handler that keeps the connection alive
    until the real handler is ready.
    
    Args:
        websocket: The WebSocket connection
    """
    try:
        await websocket.accept()
        await websocket.send_json({
            "type": "system_status", 
            "status": "initializing",
            "message": "System is starting up, please wait..."
        })
        
        # Keep the connection open until the real handler takes over or timeout
        try:
            while True:
                data = await asyncio.wait_for(websocket.receive_text(), timeout=30.0)
                await websocket.send_json({
                    "type": "info",
                    "message": "System is still initializing, please wait..."
                })
        except (asyncio.TimeoutError, WebSocketDisconnect):
            pass
    except Exception as e:
        logger.error(f"Error in placeholder WebSocket handler: {e}")

# Dynamic WebSocket handler that delegates to the current handler implementation
@app.websocket("/ws")
async def websocket_endpoint(websocket: WebSocket):
    """
    WebSocket endpoint that delegates to the current handler implementation.
    Initially uses the placeholder handler, but will be updated to use
    the real handler once the system is initialized.
    
    Args:
        websocket: The WebSocket connection
    """
    global ws_handler
    
    # Use the current handler (starts with placeholder, replaced during setup)
    current_handler = ws_handler or placeholder_ws_handler
    await current_handler(websocket)

# Initialize the global handler with the placeholder
ws_handler = placeholder_ws_handler

# Placeholder for state - will be properly set in setup_modern_app
app.state.initialized = False

# Initialize the API router early to handle requests during startup
# We're not providing the orchestrator yet since it's not ready
setup_api_router(None)  # Mark initialization as in progress

# Include our API router here to ensure endpoints are registered early
app.include_router(api_router)

async def process_request_background(
    orchestrator: Any, 
    ws_manager: ModernWebSocketManager,
    client_id: str,
    content: str,
    request_id: str
) -> None:
    """
    Process a request in the background and send the result via WebSocket.
    
    Args:
        orchestrator: The modern orchestrator for processing requests
        ws_manager: WebSocket manager for sending responses
        client_id: ID of the client that sent the request
        content: Content of the request
        request_id: ID of the request
    """
    try:
        # Process the request with the orchestrator
        response = await orchestrator.process_request(content)
        
        # Send the response to the client
        await ws_manager.handle_agent_response(client_id, response, request_id)
        
    except Exception as e:
        logger.error(f"Error processing request in background: {str(e)}")
        await ws_manager.send_personal(
            client_id,
            {
                "type": "error",
                "message": f"Error processing request: {str(e)}",
                "request_id": request_id
            }
        )

def setup_modern_app(app_instance: FastAPI, ws_manager: ModernWebSocketManager, orchestrator: Any) -> None:
    """
    Set up the FastAPI application with modern components.
    
    Args:
        app_instance: FastAPI application instance
        ws_manager: WebSocket manager for handling real-time connections
        orchestrator: Modern orchestrator for managing agents
    """
    global ws_handler
    
    # Store components in app state
    app_instance.state.modern_ws_manager = ws_manager
    app_instance.state.modern_orchestrator = orchestrator
    app_instance.state.initialized = True
    
    # Initialize the API router with our orchestrator
    set_orchestrator(orchestrator)
    logger.info("API router initialized with orchestrator")
    
    # Define the real WebSocket handler that uses the manager
    async def real_ws_handler(websocket: WebSocket):
        """Real WebSocket handler that uses the WebSocketManager."""
        client_id = await ws_manager.connect(websocket)
        try:
            await ws_manager.handle_connection(websocket)
        except WebSocketDisconnect:
            await ws_manager.disconnect(client_id)
    
    # Update the global handler to use the real implementation
    ws_handler = real_ws_handler
    logger.info("WebSocket handler updated to use WebSocketManager")
            
    # Add event handler for processing requests from WebSocket connections
    async def handle_new_request(client_id: str, content: str, request_id: str, **kwargs):
        """Handle a new request from a WebSocket connection."""
        try:
            orchestrator = app_instance.state.modern_orchestrator
            ws_manager = app_instance.state.modern_ws_manager
            
            # Start a background task to process the request
            asyncio.create_task(
                process_request_background(
                    orchestrator=orchestrator,
                    ws_manager=ws_manager,
                    client_id=client_id,
                    content=content,
                    request_id=request_id
                )
            )
                
        except Exception as e:
            logger.error(f"Error handling new request: {str(e)}")
            await app_instance.state.modern_ws_manager.send_personal(
                client_id,
                {
                    "type": "error",
                    "message": f"Error processing request: {str(e)}",
                    "request_id": request_id
                }
            )
    
    # Register the handler
    ws_manager.register_event_handler("new_request", handle_new_request)
    
    logger.info("Modern FastAPI application setup complete")
