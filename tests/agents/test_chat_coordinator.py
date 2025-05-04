"""
Unit tests for the ChatCoordinatorAgent class.
Tests the agent's ability to route requests and coordinate with other agents.
"""

import pytest
import json
import asyncio
from unittest.mock import MagicMock, AsyncMock, patch
from src.agents.chat_coordinator import ChatCoordinatorAgent
from src.agents.base_agent import BaseAgent
from crewai import Agent, Process


class MockSpecializedAgent(BaseAgent):
    """Mock specialized agent for testing."""
    
    def __init__(self, llm, name="Mock Agent", description="Mock Description", mcp_client=None):
        """Initialize the mock agent."""
        super().__init__(llm, name, description, mcp_client)
    
    def process(self, request):
        """Mock process method that returns a predefined response."""
        return f"Response from {self.name}"

    async def process_async(self, request):
        """Mock async process method."""
        return self.process(request)


class TestChatCoordinatorAgent:
    """Tests for the ChatCoordinatorAgent class."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.llm = MagicMock()
        self.llm.invoke = MagicMock(return_value="Test response")
        
        # Mock MCP client
        self.mcp_client = MagicMock()
        self.mcp_client.use_tool = AsyncMock()
        
        # Create a ChatCoordinatorAgent with a mock agent
        self.mock_agent = MockSpecializedAgent(self.llm, mcp_client=self.mcp_client)
        self.coordinator = ChatCoordinatorAgent(self.llm, self.mcp_client)
        self.coordinator.add_agent("mock_agent", self.mock_agent)
        
        # Mock event callback
        self.mock_event_callback = AsyncMock()
        self.coordinator.set_event_callback(self.mock_event_callback)

    def test_add_agent_expected(self):
        """
        Test that adding an agent works correctly.
        
        Expected use case.
        """
        # Arrange
        new_agent = MockSpecializedAgent(self.llm, "New Agent", "New Description")
        
        # Act
        self.coordinator.add_agent("new_agent", new_agent)
        
        # Assert
        assert "new_agent" in self.coordinator.agents
        assert self.coordinator.agents["new_agent"] == new_agent

    def test_add_crew_agent_expected(self):
        """
        Test that adding a Crew.ai agent works correctly.
        
        Expected use case.
        """
        # Arrange
        mock_crew_agent = MagicMock()
        mock_crew_agent.role = "Crew Agent"
        mock_crew_agent.backstory = "Test backstory"
        
        # Act
        self.coordinator.add_crew_agent("crew_agent", mock_crew_agent)
        
        # Assert
        assert "crew_agent" in self.coordinator.crew_agents
        assert self.coordinator.crew_agents["crew_agent"] == mock_crew_agent

    def test_get_available_agents_expected(self):
        """
        Test that get_available_agents returns the correct formatted string.
        
        Expected use case.
        """
        # Arrange - add a crew agent
        mock_crew_agent = MagicMock()
        mock_crew_agent.role = "Crew Agent"
        mock_crew_agent.backstory = "Test backstory"
        self.coordinator.add_crew_agent("crew_agent", mock_crew_agent)
        
        # Act
        result = self.coordinator.get_available_agents()
        
        # Assert
        assert "Mock Agent: Mock Description" in result
        assert "Crew Agent: Test backstory" in result

    @pytest.mark.asyncio
    async def test_emit_event_expected(self):
        """
        Test that events are emitted correctly.
        
        Expected use case.
        """
        # Arrange - event callback already set in setup
        
        # Act
        await self.coordinator._emit_event("test_event", message="Test message")
        
        # Assert
        self.mock_event_callback.assert_called_once_with("test_event", message="Test message")

    @pytest.mark.asyncio
    async def test_process_jira_request_expected(self):
        """
        Test processing a Jira-specific request.
        
        Expected use case.
        """
        # Arrange
        jira_agent = MockSpecializedAgent(self.llm, "Project Manager", "Project manager agent", self.mcp_client)
        jira_agent.process = AsyncMock(return_value="Jira projects listed successfully")
        self.coordinator.add_agent("project manager", jira_agent)
        
        # Act
        result = await self.coordinator.process_message("list my jira projects")
        
        # Assert
        assert result["status"] == "success"
        assert result["processed_by"] == "Project Manager"
        assert result["response"] == "Jira projects listed successfully"
        assert self.mock_event_callback.call_count > 0

    @pytest.mark.asyncio
    @patch('src.agents.chat_coordinator.Crew')
    async def test_process_with_crew_ai_expected(self, mock_crew_class):
        """
        Test processing a request using Crew.ai agents.
        
        Expected use case.
        """
        # Arrange
        mock_crew_instance = MagicMock()
        mock_crew_instance.kickoff.return_value = "Research complete"
        mock_crew_class.return_value = mock_crew_instance
        
        # Create mock crew agents
        mock_pm = MagicMock()
        mock_pm.role = "Project Manager"
        mock_pm.backstory = "PM backstory"
        
        mock_researcher = MagicMock()
        mock_researcher.role = "Research Specialist"
        mock_researcher.backstory = "Research backstory"
        
        self.coordinator.add_crew_agent("project manager", mock_pm)
        self.coordinator.add_crew_agent("research specialist", mock_researcher)
        
        # Act
        result = await self.coordinator.process_message("research the latest project management techniques")
        
        # Assert
        assert result["status"] == "success"
        assert "Research Specialist" in result["primary_agent"]
        assert result["response"] == "Research complete"
        mock_crew_instance.kickoff.assert_called_once()
        assert self.mock_event_callback.call_count > 0

    @pytest.mark.asyncio
    async def test_no_crew_agents_failure(self):
        """
        Test handling a non-Jira request when no Crew.ai agents are available.
        
        Failure case.
        """
        # Arrange - no crew agents added
        
        # Act
        result = await self.coordinator.process_message("what are the best project management practices?")
        
        # Assert
        assert result["status"] == "error"
        assert "Crew.ai agents are not configured" in result["response"]
        assert self.mock_event_callback.call_count > 0

    @pytest.mark.asyncio
    async def test_process_jira_request_no_pm_agent_failure(self):
        """
        Test processing a Jira request with no Project Manager agent.
        
        Failure case.
        """
        # Arrange - no PM agent added
        
        # Act
        result = await self.coordinator.process_message("list my jira projects")
        
        # Assert
        assert result["status"] == "error"
        assert "couldn't find the Project Manager agent" in result["response"]
        assert self.mock_event_callback.call_count > 0

    @pytest.mark.asyncio
    async def test_error_during_processing_failure(self):
        """
        Test handling an error during request processing.
        
        Failure case.
        """
        # Arrange - add PM agent that raises an exception
        jira_agent = MockSpecializedAgent(self.llm, "Project Manager", "Project manager agent", self.mcp_client)
        jira_agent.process = AsyncMock(side_effect=ValueError("Test error"))
        self.coordinator.add_agent("project manager", jira_agent)
        
        # Act
        result = await self.coordinator.process_message("list my jira projects")
        
        # Assert
        assert result["status"] == "error"
        assert "Test error" in result["response"] or "Test error" in result.get("error", "")
        assert self.mock_event_callback.call_count > 0

    def test_store_memory_and_limit_expected(self):
        """
        Test that memory storage works and is limited to 10 items.
        
        Expected use case.
        """
        # Arrange
        self.coordinator.memory = []
        
        # Act
        for i in range(15):
            self.coordinator.store_memory({
                "request": f"request {i}",
                "response": f"response {i}"
            })
        
        # Assert
        assert len(self.coordinator.memory) == 10
        assert self.coordinator.memory[0]["request"] == "request 5"
        assert self.coordinator.memory[-1]["request"] == "request 14"

    def test_get_memory_with_limit_expected(self):
        """
        Test getting memory with a limit.
        
        Expected use case.
        """
        # Arrange
        self.coordinator.memory = []
        for i in range(5):
            self.coordinator.store_memory({
                "request": f"request {i}",
                "response": f"response {i}"
            })
        
        # Act
        memory = self.coordinator.get_memory(limit=2)
        
        # Assert
        assert len(memory) == 2
        assert memory[0]["request"] == "request 3"
        assert memory[1]["request"] == "request 4"

    def test_get_context_expected(self):
        """
        Test getting context from memory.
        
        Expected use case.
        """
        # Arrange
        self.coordinator.memory = []
        self.coordinator.store_memory({
            "request": "request 1",
            "response": "response 1"
        })
        self.coordinator.store_memory({
            "request": "request 2",
            "response": "response 2"
        })
        
        # Act
        context = self.coordinator.get_context()
        
        # Assert
        assert "User: request 1" in context
        assert "System: response 1" in context
        assert "User: request 2" in context
        assert "System: response 2" in context

    def test_get_context_empty_memory_edge_case(self):
        """
        Test getting context when memory is empty.
        
        Edge case.
        """
        # Arrange
        self.coordinator.memory = []
        
        # Act
        context = self.coordinator.get_context()
        
        # Assert
        assert context == "No previous context available."