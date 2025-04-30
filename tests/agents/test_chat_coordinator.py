"""
Unit tests for the ChatCoordinatorAgent class.
"""

import pytest
import json
from unittest.mock import MagicMock, patch
from src.agents.chat_coordinator import ChatCoordinatorAgent
from src.agents.base_agent import BaseAgent


class MockSpecializedAgent(BaseAgent):
    """Mock specialized agent for testing."""
    
    def __init__(self, llm, name="Mock Agent", description="Mock Description"):
        """Initialize the mock agent."""
        super().__init__(llm, name, description)
    
    def process(self, request):
        """Mock process method that returns a predefined response."""
        return f"Response from {self.name}"


class TestChatCoordinatorAgent:
    """Tests for the ChatCoordinatorAgent class."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.llm = MagicMock()
        # Mock the LLMChain.run method to return a predefined JSON response
        self.llm.predict.return_value = json.dumps({
            "understanding": "test request",
            "primary_agent": "mock_agent",
            "supporting_agents": [],
            "plan": "process the request",
            "clarification_needed": False
        })
        
        # Create a ChatCoordinatorAgent with a mock agent
        self.mock_agent = MockSpecializedAgent(self.llm)
        self.coordinator = ChatCoordinatorAgent(self.llm)
        self.coordinator.add_agent("mock_agent", self.mock_agent)

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

    def test_get_available_agents_expected(self):
        """
        Test that get_available_agents returns the correct formatted string.
        
        Expected use case.
        """
        # Arrange - already has mock_agent added in setup_method
        
        # Act
        result = self.coordinator.get_available_agents()
        
        # Assert
        assert "Mock Agent: Mock Description" in result
        
        # Add another agent and check again
        new_agent = MockSpecializedAgent(self.llm, "Another Agent", "Another Description")
        self.coordinator.add_agent("another_agent", new_agent)
        
        result = self.coordinator.get_available_agents()
        assert "Mock Agent: Mock Description" in result
        assert "Another Agent: Another Description" in result

    @patch('src.agents.chat_coordinator.LLMChain')
    def test_process_request_with_existing_agent_expected(self, mock_llm_chain):
        """
        Test processing a request with an existing agent.
        
        Expected use case.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.return_value = json.dumps({
            "understanding": "test request",
            "primary_agent": "mock_agent",
            "supporting_agents": [],
            "plan": "process the request",
            "clarification_needed": False
        })
        mock_llm_chain.return_value = mock_chain_instance
        
        # Mock request parser
        self.coordinator.agents["request_parser"] = MagicMock()
        self.coordinator.agents["request_parser"].process.return_value = {
            "relevant": True,
            "category": "Test Category"
        }
        
        # Act
        response = self.coordinator.process({"text": "test request"})
        
        # Assert
        assert response["status"] == "success"
        assert response["processed_by"] == "mock_agent"
        assert response["response"] == "Response from Mock Agent"
        
        # Check that memory was updated
        assert len(self.coordinator.memory) == 1
        assert self.coordinator.memory[0]["request"] == "test request"
        assert self.coordinator.memory[0]["primary_agent"] == "mock_agent"

    @patch('src.agents.chat_coordinator.LLMChain')
    def test_process_request_with_clarification_needed_edge_case(self, mock_llm_chain):
        """
        Test processing a request that needs clarification.
        
        Edge case.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.return_value = json.dumps({
            "understanding": "unclear request",
            "primary_agent": "mock_agent",
            "supporting_agents": [],
            "plan": "ask for clarification",
            "clarification_needed": True,
            "clarification_questions": ["What do you mean?", "Can you provide more details?"]
        })
        mock_llm_chain.return_value = mock_chain_instance
        
        # Mock request parser
        self.coordinator.agents["request_parser"] = MagicMock()
        self.coordinator.agents["request_parser"].process.return_value = {
            "relevant": True,
            "category": "Test Category"
        }
        
        # Act
        response = self.coordinator.process({"text": "unclear request"})
        
        # Assert
        assert response["status"] == "clarification_needed"
        assert "clarification_questions" in response
        assert len(response["clarification_questions"]) == 2
        assert "What do you mean?" in response["clarification_questions"]

    @patch('src.agents.chat_coordinator.LLMChain')
    def test_process_request_with_missing_agent_failure(self, mock_llm_chain):
        """
        Test processing a request with a non-existent agent.
        
        Failure case.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.return_value = json.dumps({
            "understanding": "test request",
            "primary_agent": "nonexistent_agent",
            "supporting_agents": [],
            "plan": "process the request",
            "clarification_needed": False
        })
        mock_llm_chain.return_value = mock_chain_instance
        
        # Mock request parser
        self.coordinator.agents["request_parser"] = MagicMock()
        self.coordinator.agents["request_parser"].process.return_value = {
            "relevant": True,
            "category": "Test Category"
        }
        
        # Act
        response = self.coordinator.process({"text": "test request"})
        
        # Assert
        assert response["status"] == "fallback"
        assert "missing_agent" in response
        assert response["missing_agent"] == "nonexistent_agent"

    @patch('src.agents.chat_coordinator.LLMChain')
    def test_process_request_with_json_parse_error_edge_case(self, mock_llm_chain):
        """
        Test processing a request with a malformed JSON response.
        
        Edge case.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.return_value = "Invalid JSON response"
        mock_llm_chain.return_value = mock_chain_instance
        
        # Mock request parser
        self.coordinator.agents["request_parser"] = MagicMock()
        self.coordinator.agents["request_parser"].process.return_value = {
            "relevant": True,
            "category": "Test Category"
        }
        
        # Act
        response = self.coordinator.process({"text": "test request"})
        
        # Assert
        # Should fall back to default plan with chat_coordinator as primary agent
        assert "status" in response
        assert response["processed_by"] == "chat_coordinator"

    @patch('src.agents.chat_coordinator.LLMChain')
    def test_process_exception_handling_failure(self, mock_llm_chain):
        """
        Test that exceptions are properly handled during processing.
        
        Failure case.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.side_effect = Exception("Test error")
        mock_llm_chain.return_value = mock_chain_instance
        
        # Act
        response = self.coordinator.process({"text": "test request"})
        
        # Assert
        assert response["status"] == "error"
        assert "error" in response
        assert "Test error" in response["error"]

    def test_get_context_with_empty_memory_edge_case(self):
        """
        Test getting context when memory is empty.
        
        Edge case.
        """
        # Arrange - empty memory
        
        # Act
        context = self.coordinator.get_context()
        
        # Assert
        assert context == "No previous context available."

    def test_get_context_with_memory_expected(self):
        """
        Test getting context with populated memory.
        
        Expected use case.
        """
        # Arrange
        self.coordinator.store_memory({
            "request": "test request 1",
            "response": "test response 1"
        })
        self.coordinator.store_memory({
            "request": "test request 2",
            "response": "test response 2"
        })
        
        # Act
        context = self.coordinator.get_context()
        
        # Assert
        assert "test request 1" in context
        assert "test response 1" in context
        assert "test request 2" in context
        assert "test response 2" in context 