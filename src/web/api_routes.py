#!/usr/bin/env python3
"""
API routes for the AI Project Management System.
Provides API endpoints for agent management and interaction.
"""

import logging
import uuid
import asyncio
import time
from typing import Dict, List, Any, Optional

from fastapi import APIRouter, HTTPException, Depends, Request
from pydantic import BaseModel

from src.models.agent_models import AgentResponse
from src.modern_orchestration import ModernOrchestrator

# Set up logging
logger = logging.getLogger("ai_pm_system.web.api_routes")

# Create API router
api_router = APIRouter(prefix="/api", tags=["Agents API"])

class RequestModel(BaseModel):
    """Pydantic model for API requests."""
    content: str
    request_id: Optional[str] = None

# Global reference to orchestrator, will be set during initialization
orchestrator: Optional[ModernOrchestrator] = None
initialization_in_progress = False
init_start_time = None
MAX_INIT_WAIT_TIME = 30  # Maximum seconds to wait for initialization

def get_orchestrator() -> ModernOrchestrator:
    """
    Dependency to get the orchestrator instance.
    Will wait briefly for the orchestrator to initialize if it's not ready yet.
    
    Returns:
        The orchestrator instance
    
    Raises:
        HTTPException: If the orchestrator is not initialized and not being initialized
    """
    global orchestrator, initialization_in_progress, init_start_time
    
    # If orchestrator is already initialized, return it
    if orchestrator is not None:
        return orchestrator
    
    # Check if initialization is in progress and not timed out
    if initialization_in_progress:
        # Check if we've been waiting too long
        if init_start_time and (time.time() - init_start_time > MAX_INIT_WAIT_TIME):
            logger.warning(f"Orchestrator initialization timed out after {MAX_INIT_WAIT_TIME}s")
            raise HTTPException(
                status_code=503, 
                detail="System initialization is taking longer than expected. Please try again later."
            )
        
        # Initialization is in progress, wait a bit
        logger.info("Orchestrator initialization in progress, waiting...")
        raise HTTPException(
            status_code=503, 
            detail="System is initializing. Please try again in a few moments."
        )
    
    # Orchestrator is not initialized and not being initialized
    logger.error("Orchestrator not initialized and no initialization in progress")
    raise HTTPException(
        status_code=503, 
        detail="System not fully initialized yet. Please refresh the page in a few moments."
    )

@api_router.get("/health")
async def health_check():
    """Health check endpoint."""
    global orchestrator, initialization_in_progress
    
    status = "initializing" if initialization_in_progress else "not_initialized"
    if orchestrator is not None:
        status = "healthy"
        
    return {
        "status": status, 
        "version": "2.0.0", 
        "architecture": "modern",
        "orchestrator_ready": orchestrator is not None
    }

@api_router.get("/agents")
async def get_agents(orch: ModernOrchestrator = Depends(get_orchestrator)):
    """
    Get information about available agents.
    
    Args:
        orch: The orchestrator instance (injected by FastAPI)
    
    Returns:
        Dictionary with agent information
    """
    try:
        agents = orch.list_agents()
        
        agent_info = {}
        for agent_name in agents:
            agent = orch.get_agent(agent_name)
            if agent:
                agent_info[agent_name] = {
                    "name": agent.name,
                    "description": agent.description,
                    "type": agent.config.agent_type.value if hasattr(agent.config, "agent_type") else "unknown"
                }
            
        return {"agents": agent_info, "count": len(agent_info)}
    except Exception as e:
        logger.error(f"Error getting agent information: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error retrieving agent information: {str(e)}")

@api_router.get("/system/status")
async def system_status():
    """
    Get the current system initialization status.
    This endpoint is always available regardless of orchestrator state.
    
    Returns:
        Dictionary with system status information
    """
    global orchestrator, initialization_in_progress, init_start_time
    
    status = "not_initialized"
    if orchestrator is not None:
        status = "ready"
    elif initialization_in_progress:
        status = "initializing"
        
    init_time = None
    if init_start_time:
        init_time = round(time.time() - init_start_time, 1)
        
    return {
        "status": status,
        "initialization_in_progress": initialization_in_progress,
        "initialization_time": init_time,
        "orchestrator_ready": orchestrator is not None
    }

@api_router.post("/request")
async def process_request(
    request_data: RequestModel, 
    orch: ModernOrchestrator = Depends(get_orchestrator)
):
    """
    Process a user request using the modern orchestrator.
    
    Args:
        request_data: The request data
        orch: The orchestrator instance (injected by FastAPI)
    
    Returns:
        The agent's response
    """
    try:
        request_id = request_data.request_id or str(uuid.uuid4())
        
        # Process the request
        response = await orch.process_request(request_data.content)
        
        # Add request_id to response
        response_dict = response.model_dump() if hasattr(response, "model_dump") else response.dict()
        response_dict["request_id"] = request_id
        
        return response_dict
        
    except Exception as e:
        logger.error(f"Error processing request: {str(e)}")
        raise HTTPException(status_code=500, detail=f"Error processing request: {str(e)}")

def setup_api_router(orch: Optional[ModernOrchestrator] = None) -> APIRouter:
    """
    Initialize the API router with an orchestrator instance.
    If the orchestrator is not provided, mark initialization as in progress.
    
    Args:
        orch: The orchestrator instance to use for processing requests
    
    Returns:
        The initialized API router
    """
    global orchestrator, initialization_in_progress, init_start_time
    
    if orch is not None:
        # Orchestrator is ready
        orchestrator = orch
        initialization_in_progress = False
        logger.info("API router initialized with orchestrator")
    else:
        # Orchestrator will be initialized later
        initialization_in_progress = True
        init_start_time = time.time()
        logger.info("API router initialized, waiting for orchestrator")
    
    return api_router

def set_orchestrator(orch: ModernOrchestrator) -> None:
    """
    Update the global orchestrator instance.
    Call this when the orchestrator is ready to handle requests.
    
    Args:
        orch: The orchestrator instance
    """
    global orchestrator, initialization_in_progress
    
    orchestrator = orch
    initialization_in_progress = False
    logger.info("Orchestrator set and ready to handle requests")