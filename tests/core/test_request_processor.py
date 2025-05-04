#!/usr/bin/env python3
"""
Tests for the enhanced request_processor module using ChatCoordinatorAgent.
"""

import os
import sys
import pytest
from unittest.mock import patch, MagicMock, AsyncMock

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.request_processor import RequestProcessor
from src.agents.chat_coordinator import ChatCoordinatorAgent

class TestRequestProcessor:
    """Tests for the enhanced RequestProcessor class."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Create mock orchestrator
        self.mock_orchestrator = MagicMock()
        self.mock_orchestrator.get_agent_states.return_value = {
            "Project Manager": "idle",
            "Code Developer": "idle",
            "Business Analyst": "idle",
            "Research Specialist": "idle",
            "Report Drafter": "idle"
        }
        self.mock_orchestrator.initialize_system = AsyncMock()
        
        # Create mock MCP client
        self.mock_mcp_client = MagicMock()
        
        # Create RequestProcessor instance with mocks
        self.processor = RequestProcessor(
            orchestrator=self.mock_orchestrator,
            mcp_client=self.mock_mcp_client
        )
        
        # Mock coordinator
        self.mock_coordinator = MagicMock(spec=ChatCoordinatorAgent)
        self.mock_coordinator.process_message = AsyncMock()
        
    @pytest.mark.asyncio
    async def test_initialize_expected(self):
        """
        Test initialization of the RequestProcessor.
        
        Expected use case.
        """
        # Arrange
        mock_event_handler = AsyncMock()
        mock_system_components = {
            "coordinator": self.mock_coordinator,
            "crew_agents": {"agent1": MagicMock(), "agent2": MagicMock()},
            "base_agents": {"agent3": MagicMock(), "agent4": MagicMock()}
        }
        self.mock_orchestrator.initialize_system.return_value = mock_system_components
        
        # Act
        await self.processor.initialize(mock_event_handler)
        
        # Assert
        self.mock_orchestrator.initialize_system.assert_called_once_with(mock_event_handler)
        assert self.processor.coordinator == self.mock_coordinator
        
    @pytest.mark.asyncio
    async def test_process_request_with_coordinator_expected(self):
        """
        Test processing a request using the ChatCoordinatorAgent.
        
        Expected use case.
        """
        # Arrange
        self.processor.coordinator = self.mock_coordinator
        self.mock_coordinator.process_message.return_value = {
            "status": "success",
            "processed_by": "Project Manager",
            "response": "Task completed successfully",
            "request_id": "test-123"
        }
        
        # Act
        result = await self.processor.process_request(
            "Create a project timeline",
            request_id="test-123"
        )
        
        # Assert
        self.mock_coordinator.process_message.assert_called_once_with("Create a project timeline")
        assert result["status"] == "success"
        assert result["processed_by"] == "Project Manager"
        assert result["response"] == "Task completed successfully"
        
    @pytest.mark.asyncio
    async def test_process_request_no_coordinator_failure(self):
        """
        Test processing a request when coordinator is not initialized.
        
        Failure case.
        """
        # Arrange
        self.processor.coordinator = None
        
        # Act
        result = await self.processor.process_request(
            "Create a project timeline",
            request_id="test-123"
        )
        
        # Assert
        assert result["status"] == "error"
        assert result["processed_by"] == "System"
        assert "not initialized" in result["response"]
        
    @pytest.mark.asyncio
    async def test_process_request_exception_failure(self):
        """
        Test processing a request when coordinator raises an exception.
        
        Failure case.
        """
        # Arrange
        self.processor.coordinator = self.mock_coordinator
        self.mock_coordinator.process_message.side_effect = Exception("Test error")
        mock_event_handler = AsyncMock()
        
        # Act
        result = await self.processor.process_request(
            "Create a project timeline",
            request_id="test-123",
            event_handler=mock_event_handler
        )
        
        # Assert
        assert result["status"] == "error"
        assert result["processed_by"] == "System"
        assert "Test error" in result["response"]
        
        # Verify event handler was called for the error
        if mock_event_handler.call_count > 0:
            mock_event_handler.assert_called_with(
                "request_error", 
                message="Error processing request: Test error",
                request_id="test-123"
            )
            
    def test_classify_request_legacy(self):
        """
        Test that the legacy _classify_request method still works.
        
        Expected use case.
        """
        # Test project management related request
        request = "Create a project timeline for the new mobile app development"
        classification = self.processor._classify_request(request)
        
        assert classification["primary_agent"] == "Project Manager"
        assert "Project Manager" in classification["involved_agents"]
        assert classification["is_pm_request"] == True
        assert classification["is_jira_request"] == False
        
        # Test Jira-related request
        request = "Create a new Jira project named 'Mobile App'"
        classification = self.processor._classify_request(request)
        
        assert classification["primary_agent"] == "Project Manager"
        assert "Project Manager" in classification["involved_agents"]
        assert classification["is_pm_request"] == True
        assert classification["is_jira_request"] == True
