"""
Isolated tests for the SimpleAgent class.
"""

import os
import sys
from pathlib import Path

# Add the specific module directory to Python path instead of the whole project
module_path = Path(__file__).parent.parent.parent / "src" / "agents"
sys.path.append(str(module_path))

os.environ["LANGCHAIN_SQLITE_PATH"] = ":memory:"  # Use in-memory SQLite

import pytest
from unittest.mock import MagicMock, AsyncMock
from langchain_core.tools import Tool

# Direct import from the module file
from simple_agent import SimpleAgent

class TestSimpleAgent:
    """Tests for the SimpleAgent class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.llm = MagicMock()
        self.llm.invoke = MagicMock(return_value="Test response")
        self.llm.ainvoke = AsyncMock(return_value="Test response")
        
        # Create a mock tool
        self.mock_tool = Tool(
            name="test_tool",
            description="A test tool",
            func=lambda x: f"Tool response: {x}"
        )
        
        # Initialize agent with mock tool
        self.agent = SimpleAgent(self.llm, tools=[self.mock_tool])
    
    def test_initialization_expected(self):
        """Test agent initializes correctly with tools."""
        assert len(self.agent.tools) == 1
        assert self.agent.tools[0].name == "test_tool"
        assert isinstance(self.agent.memory, list)
        assert len(self.agent.memory) == 0
    
    def test_memory_management_expected(self):
        """Test memory storage and retrieval."""
        # Add some test interactions
        for i in range(12):  # Add more than memory limit
            self.agent.add_memory({
                "input": f"test input {i}",
                "output": f"test output {i}"
            })
        
        # Check memory limit enforcement
        assert len(self.agent.memory) == 10
        assert self.agent.memory[0]["input"] == "test input 2"
        assert self.agent.memory[-1]["input"] == "test input 11"
    
    def test_context_formatting_expected(self):
        """Test context is formatted correctly."""
        # Add test interactions
        self.agent.add_memory({
            "input": "test input 1",
            "output": "test output 1"
        })
        self.agent.add_memory({
            "input": "test input 2",
            "output": "test output 2"
        })
        
        context = self.agent.get_context()
        assert "Human: test input 1" in context
        assert "Assistant: test output 1" in context
        assert "Human: test input 2" in context
        assert "Assistant: test output 2" in context
    
    def test_empty_context_edge_case(self):
        """Test context handling with no memory."""
        context = self.agent.get_context()
        assert context == "No previous context available."
    
    @pytest.mark.asyncio
    async def test_aprocess_expected(self):
        """Test async processing works correctly."""
        # Mock the agent executor
        self.agent.agent_executor.ainvoke = AsyncMock(
            return_value={"output": "Test response", "intermediate_steps": []}
        )
        
        response = await self.agent.aprocess("test request")
        assert response == "Test response"
        assert len(self.agent.memory) == 1
        assert self.agent.memory[0]["input"] == "test request"
    
    def test_process_expected(self):
        """Test sync processing works correctly."""
        # Mock the agent executor
        self.agent.agent_executor.invoke = MagicMock(
            return_value={"output": "Test response", "intermediate_steps": []}
        )
        
        response = self.agent.process("test request")
        assert response == "Test response"
        assert len(self.agent.memory) == 1
        assert self.agent.memory[0]["input"] == "test request"
    
    def test_error_handling_failure(self):
        """Test error handling when processing fails."""
        # Make the agent executor raise an exception
        self.agent.agent_executor.invoke = MagicMock(side_effect=Exception("Test error"))
        
        response = self.agent.process("test request")
        assert "Error processing request: Test error" in response