"""
Tests for the SimpleAgent class.
"""

import os
import sys
from pathlib import Path
from typing import cast, Dict, Any, List, Optional, Union, Literal

# Add the src directory to Python path
sys.path.append(str(Path(__file__).parent.parent.parent / "src"))

# Set SQLite path before any other imports
os.environ["LANGCHAIN_SQLITE_PATH"] = ":memory:"

import pytest
from unittest.mock import MagicMock, AsyncMock, patch
from langchain_core.tools import Tool
from agents.simple_agent import SimpleAgent, AgentState
from langgraph.graph import END

class TestSimpleAgent:
    """Tests for the SimpleAgent class."""
    
    def setup_method(self):
        """Set up test fixtures."""
        self.llm = MagicMock()
        self.llm.invoke = MagicMock(return_value="Test response")
        self.llm.ainvoke = AsyncMock(return_value="Test response")
        
        # Create mock tools
        self.mock_tools = [
            Tool(
                name="test_tool",
                description="A test tool",
                func=lambda x: f"Tool response: {x}"
            ),
            Tool(
                name="search_tool",
                description="A search tool",
                func=lambda x: f"Search results for: {x}"
            )
        ]
        
        # Mock the agent executor response
        self.mock_executor_response = {
            "output": "Test execution response",
            "intermediate_steps": []
        }
        
        # Initialize agent with mock tools
        with patch('langchain.agents.AgentExecutor') as mock_executor:
            mock_executor.return_value.invoke = MagicMock(return_value=self.mock_executor_response)
            mock_executor.return_value.ainvoke = AsyncMock(return_value=self.mock_executor_response)
            
            self.agent = SimpleAgent(
                llm=self.llm,
                tools=self.mock_tools,
                agent_type="project_manager"
            )
            
            # Replace the real executor with our mock
            self.agent.agent_executor = mock_executor.return_value
    
    def test_initialization_with_agent_type(self):
        """Test agent initializes correctly with specific agent type."""
        researcher_agent = SimpleAgent(
            llm=self.llm,
            tools=self.mock_tools,
            agent_type="researcher"
        )
        assert researcher_agent.agent_type == "researcher"
        assert len(researcher_agent.tools) == 2
        assert isinstance(researcher_agent.memory, list)
        assert len(researcher_agent.memory) == 0

    def test_prompt_customization_by_agent_type(self):
        """Test prompt template is customized based on agent type."""
        researcher_agent = SimpleAgent(
            llm=self.llm,
            tools=[],
            agent_type="researcher"
        )
        
        pm_prompt = self.agent._get_prompt()
        researcher_prompt = researcher_agent._get_prompt()
        
        # Verify different prompts for different agent types
        assert "Project planning and organization" in str(pm_prompt)
        assert "Gathering relevant information" in str(researcher_prompt)

    def test_workflow_execution_expected(self):
        """Test workflow executes correctly in expected case."""
        response = self.agent.process("test request")
        assert response == "Test execution response"
        assert len(self.agent.memory) == 1
        assert self.agent.memory[0]["input"] == "test request"
        assert self.agent.memory[0]["output"] == "Test execution response"

    @pytest.mark.asyncio
    async def test_async_workflow_execution_expected(self):
        """Test async workflow executes correctly."""
        response = await self.agent.aprocess("test request")
        assert response == "Test execution response"
        assert len(self.agent.memory) == 1
        assert self.agent.memory[0]["input"] == "test request"
        assert self.agent.memory[0]["output"] == "Test execution response"

    def test_workflow_error_handling_failure(self):
        """Test error handling in workflow execution."""
        # Make the workflow raise an exception
        self.agent.agent_executor.invoke = MagicMock(side_effect=Exception("Workflow error"))
        
        response = self.agent.process("test request")
        assert "Error processing request" in response
        assert "Workflow error" in response
        assert len(self.agent.memory) == 0  # No memory stored on error

    def test_workflow_retry_on_verification_failure(self):
        """Test workflow retries when verification fails."""
        # Setup mock to fail twice then succeed
        responses = [
            Exception("First try failed"),
            Exception("Second try failed"),
            {"output": "Success on third try", "intermediate_steps": []}
        ]
        self.agent.agent_executor.invoke = MagicMock(side_effect=responses)
        
        response = self.agent.process("test request")
        assert "Success on third try" in response
        assert len(self.agent.memory) == 1
        assert self.agent.memory[0]["output"] == "Success on third try"

    def test_memory_management_expected(self):
        """Test memory storage and retrieval with workflows."""
        # Add more than the memory limit
        for i in range(12):
            self.agent.process(f"request {i}")
        
        # Check memory limit enforcement
        assert len(self.agent.memory) == 10
        # Verify most recent interactions are kept
        assert "request 11" in self.agent.memory[-1]["input"]

    def test_context_formatting_with_workflows(self):
        """Test context formatting includes workflow results."""
        # Add test interactions through workflow
        self.agent.process("test request 1")
        self.agent.process("test request 2")
        
        context = self.agent.get_context()
        assert "Human: test request 1" in context
        assert "Assistant: Test execution response" in context
        assert "Human: test request 2" in context

    def test_empty_context_edge_case(self):
        """Test context handling with no workflow history."""
        context = self.agent.get_context()
        assert context == "No previous context available."

    def test_max_retries_failure(self):
        """Test workflow stops after max retries."""
        # Mock workflow to always fail
        self.agent.agent_executor.invoke = MagicMock(side_effect=Exception("Persistent error"))
        
        response = self.agent.process("test request")
        assert "Error processing request after 3 attempts" in response