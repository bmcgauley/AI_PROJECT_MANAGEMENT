"""
Unit tests for the ChatCoordinatorAgent class.
Tests the agent's ability to route requests and coordinate with other agents.
"""

import pytest
import asyncio
from unittest.mock import MagicMock
from src.agents.chat_coordinator import ChatCoordinatorAgent
from src.agents.project_manager import ProjectManagerAgent


class TestChatCoordinatorAgent:
    """Tests for the ChatCoordinatorAgent class."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.mock_llm = MagicMock()
        self.mock_mcp_client = MagicMock()
        self.mock_event_callback = MagicMock()
        
        # Initialize coordinator with mocked components
        self.coordinator = ChatCoordinatorAgent(
            llm=self.mock_llm,
            mcp_client=self.mock_mcp_client
        )
        self.coordinator.set_event_callback(self.mock_event_callback)
        
        # Add a mock Project Manager agent
        self.mock_pm = ProjectManagerAgent(
            llm=self.mock_llm,
            mcp_client=self.mock_mcp_client
        )
        self.coordinator.add_agent("project manager", self.mock_pm)
    
    def test_add_agent_expected(self):
        """
        Test that adding an agent works correctly.
        
        Expected use case.
        """
        # Arrange
        mock_agent = MagicMock()
        mock_agent.name = "Test Agent"
        mock_agent.description = "Test description"
        
        # Act
        self.coordinator.add_agent("test_agent", mock_agent)
        
        # Assert
        assert "test_agent" in self.coordinator.agents
        assert self.coordinator.agents["test_agent"] == mock_agent
    
    def test_get_available_agents_expected(self):
        """
        Test getting list of available agents.
        
        Expected use case.
        """
        # Act
        agents_str = self.coordinator.get_available_agents()
        
        # Assert
        assert isinstance(agents_str, str)
        assert "Project Manager" in agents_str
        assert self.mock_pm.description in agents_str
    
    @pytest.mark.asyncio
    async def test_emit_event_expected(self):
        """
        Test event emission functionality.
        
        Expected use case.
        """
        # Act
        event_type = "test_event"
        event_data = {"test": "data"}
        await self.coordinator._emit_event(event_type, **event_data)
        
        # Wait for async callback to complete
        await asyncio.sleep(0.1)
        
        # Assert
        self.mock_event_callback.assert_called_once_with(event_type, **event_data)
    
    @pytest.mark.asyncio
    async def test_process_jira_request_expected(self):
        """
        Test processing a Jira request.
        
        Expected use case.
        """
        # Arrange
        self.mock_pm.process_jira_request = MagicMock()
        self.mock_pm.process_jira_request.return_value = "Jira request processed"
        
        # Act
        result = await self.coordinator.process_message("create a jira ticket")
        
        # Assert
        assert result["status"] == "success"
        assert "Project Manager" in result["processed_by"]
        assert "Jira request processed" in result["response"]
        assert self.mock_event_callback.call_count > 0
    
    @pytest.mark.asyncio
    async def test_process_jira_request_no_pm_agent_failure(self):
        """
        Test handling Jira request without Project Manager agent.
        
        Failure case.
        """
        # Arrange - remove PM agent
        self.coordinator.agents.pop("project manager")
        
        # Act
        result = await self.coordinator.process_message("create a jira ticket")
        
        # Assert
        assert result["status"] == "error"
        assert "Project Manager agent not available" in result["response"]
        assert self.mock_event_callback.call_count > 0
    
    @pytest.mark.asyncio
    async def test_error_during_processing_failure(self):
        """
        Test handling errors during request processing.
        
        Failure case.
        """
        # Arrange
        self.mock_pm.process = MagicMock(side_effect=Exception("Test error"))
        
        # Act
        result = await self.coordinator.process_message("test message")
        
        # Assert
        assert result["status"] == "error"
        assert "Test error" in result["response"]
        assert self.mock_event_callback.call_count > 0
    
    def test_store_memory_and_limit_expected(self):
        """
        Test memory storage and limiting functionality.
        
        Expected use case.
        """
        # Act - add more than 10 items
        for i in range(15):
            self.coordinator.store_memory({
                "request": f"request {i}",
                "response": f"response {i}"
            })
        
        # Assert
        assert len(self.coordinator.memory) == 10  # Should be limited to 10 items
        assert self.coordinator.memory[-1]["request"] == "request 14"  # Last item should be newest