"""
Unit tests for the BaseAgent class.
"""

import pytest
from unittest.mock import MagicMock
from src.agents.base_agent import BaseAgent

# Create a concrete implementation of BaseAgent for testing
class ConcreteTestAgent(BaseAgent):
    """Concrete implementation of BaseAgent for testing."""
    def process(self, request):
        """Process a request and return a response."""
        return f"Processed: {request}"


class TestBaseAgent:
    """Tests for the BaseAgent class."""

    def test_initialization_expected(self):
        """
        Test that BaseAgent initializes correctly with expected parameters.
        
        Expected use case.
        """
        # Arrange
        llm = MagicMock()
        name = "Test Agent"
        description = "Test Description"
        
        # Act
        agent = ConcreteTestAgent(llm, name, description)
        
        # Assert
        assert agent.name == name
        assert agent.description == description
        assert agent.llm == llm
        assert agent.memory == []

    def test_memory_storage_expected(self):
        """
        Test that interactions are stored correctly in memory.
        
        Expected use case.
        """
        # Arrange
        llm = MagicMock()
        agent = ConcreteTestAgent(llm, "Test Agent", "Test Description")
        interaction = {"request": "test request", "response": "test response"}
        
        # Act
        agent.store_memory(interaction)
        
        # Assert
        assert len(agent.memory) == 1
        assert agent.memory[0] == interaction
        assert agent.get_memory() == [interaction]
        assert agent.get_memory(limit=1) == [interaction]

    def test_memory_limit_edge_case(self):
        """
        Test that memory size is limited correctly when it exceeds the maximum.
        
        Edge case.
        """
        # Arrange
        llm = MagicMock()
        agent = ConcreteTestAgent(llm, "Test Agent", "Test Description")
        
        # Act - Add 60 items (more than the 50 item limit)
        for i in range(60):
            agent.store_memory({"id": i, "data": f"test data {i}"})
        
        # Assert
        assert len(agent.memory) == 50  # Only 50 items should be kept
        assert agent.memory[0]["id"] == 10  # First 10 items should be removed
        assert agent.memory[-1]["id"] == 59  # Last item should be id 59

    def test_get_memory_with_limit(self):
        """
        Test that get_memory correctly limits the number of returned items.
        
        Expected use case.
        """
        # Arrange
        llm = MagicMock()
        agent = ConcreteTestAgent(llm, "Test Agent", "Test Description")
        
        # Add 10 items to memory
        for i in range(10):
            agent.store_memory({"id": i})
        
        # Act & Assert
        assert len(agent.get_memory(limit=5)) == 5
        assert agent.get_memory(limit=5)[0]["id"] == 5  # Should get the 5 most recent items
        assert agent.get_memory(limit=5)[-1]["id"] == 9

    def test_process_method_implementation(self):
        """
        Test that the process method works as expected in the concrete implementation.
        
        Expected use case.
        """
        # Arrange
        llm = MagicMock()
        agent = ConcreteTestAgent(llm, "Test Agent", "Test Description")
        
        # Act
        result = agent.process("test request")
        
        # Assert
        assert result == "Processed: test request"

    def test_instantiate_abstract_class_failure(self):
        """
        Test that instantiating the abstract BaseAgent class directly raises TypeError.
        
        Failure case.
        """
        # Act & Assert
        with pytest.raises(TypeError):
            BaseAgent(MagicMock(), "Test Agent", "Test Description")

    def test_string_representation(self):
        """
        Test the string representation of the agent.
        
        Expected use case.
        """
        # Arrange
        llm = MagicMock()
        name = "Test Agent"
        description = "Test Description"
        agent = ConcreteTestAgent(llm, name, description)
        
        # Act & Assert
        assert str(agent) == f"{name} - {description}" 