"""
Tests for the modern agent structure using Pydantic and LangGraph.
"""

import unittest
import asyncio
from unittest.mock import MagicMock, patch
import sys
import os
from datetime import datetime

# Add the src directory to the path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../')))

from src.agents.modern_base_agent import ModernBaseAgent
from src.models.agent_models import AgentConfig, AgentType, AgentResponse, AgentMemoryItem

class TestModernAgent(unittest.TestCase):
    """Test cases for the modern agent structure."""
    
    def setUp(self):
        """Set up test fixtures."""
        # Create a mock LLM
        self.mock_llm = MagicMock()
        self.mock_llm.invoke.return_value = "Test response"
        
        # Create a mock MCP client
        self.mock_mcp_client = MagicMock()
        self.mock_mcp_client.use_tool.return_value = {"status": "success", "result": "Tool result"}
        
        # Create a test agent config
        self.test_config = AgentConfig(
            name="Test Agent",
            description="A test agent",
            agent_type=AgentType.PROJECT_MANAGER,
            available_tools={
                'memory-server': ['create_entities', 'read_graph'],
                'sequential-thinking': ['sequentialthinking'],
            }
        )
        
        # Patch the create_openai_tools_agent function
        self.agent_patch = patch('src.agents.modern_base_agent.create_openai_tools_agent')
        self.mock_create_agent = self.agent_patch.start()
        self.mock_agent = MagicMock()
        self.mock_create_agent.return_value = self.mock_agent
        
        # Patch the AgentExecutor
        self.executor_patch = patch('src.agents.modern_base_agent.AgentExecutor')
        self.mock_executor_class = self.executor_patch.start()
        self.mock_executor = MagicMock()
        self.mock_executor_class.return_value = self.mock_executor
        self.mock_executor.invoke.return_value = {"output": "Test response", "intermediate_steps": []}
        
        # Patch StateGraph
        self.graph_patch = patch('src.agents.modern_base_agent.StateGraph')
        self.mock_graph_class = self.graph_patch.start()
        self.mock_graph = MagicMock()
        self.mock_compiled_graph = MagicMock()
        self.mock_graph.compile.return_value = self.mock_compiled_graph
        self.mock_graph_class.return_value = self.mock_graph
        self.mock_compiled_graph.arun.return_value = {
            "input": "Test request",
            "result": "Test response",
            "attempts": 1,
            "verified": True,
            "error": None,
            "tool_calls": [],
            "next": "end"
        }
    
    def tearDown(self):
        """Tear down test fixtures."""
        self.agent_patch.stop()
        self.executor_patch.stop()
        self.graph_patch.stop()
    
    def test_agent_initialization(self):
        """Test agent initialization."""
        agent = ModernBaseAgent(
            llm=self.mock_llm,
            config=self.test_config,
            mcp_client=self.mock_mcp_client
        )
        
        self.assertEqual(agent.name, "Test Agent")
        self.assertEqual(agent.description, "A test agent")
        self.assertEqual(len(agent.memory), 0)
        
        # Verify the workflow was created
        self.mock_graph_class.assert_called_once()
        self.mock_graph.compile.assert_called_once()
    
    def test_use_tool_sync(self):
        """Test the use_tool_sync method."""
        agent = ModernBaseAgent(
            llm=self.mock_llm,
            config=self.test_config,
            mcp_client=self.mock_mcp_client
        )
        
        # Test with authorized tool
        self.mock_mcp_client.use_tool.return_value = {"status": "success", "result": "Tool result"}
        
        result = agent.use_tool_sync('memory-server', 'create_entities', {"test": "data"})
        self.assertEqual(result, {"status": "success", "result": "Tool result"})
        
        # Test with unauthorized tool
        result = agent.use_tool_sync('memory-server', 'unauthorized_tool', {"test": "data"})
        self.assertEqual(result["status"], "error")
        self.assertTrue("Permission denied" in result["error"]["message"])
    
    def test_store_memory(self):
        """Test storing items in agent memory."""
        agent = ModernBaseAgent(
            llm=self.mock_llm,
            config=self.test_config,
            mcp_client=self.mock_mcp_client
        )
        
        # Create a test memory item
        memory_item = AgentMemoryItem(
            input="Test input",
            output="Test output",
            tool_calls=[]
        )
        
        # Store the item in memory
        agent.store_memory(memory_item)
        
        # Verify it was stored
        self.assertEqual(len(agent.memory), 1)
        self.assertEqual(agent.memory[0].input, "Test input")
        self.assertEqual(agent.memory[0].output, "Test output")
        
        # Test memory limit
        for i in range(55):  # Add more than the 50 item limit
            agent.store_memory(AgentMemoryItem(
                input=f"Input {i}",
                output=f"Output {i}",
                tool_calls=[]
            ))
        
        # Verify the memory size is limited to 50 items
        self.assertEqual(len(agent.memory), 50)
        
        # Verify the oldest items were removed
        self.assertNotEqual(agent.memory[0].input, "Test input")
    
    async def async_test_process(self):
        """Test the async process method."""
        agent = ModernBaseAgent(
            llm=self.mock_llm,
            config=self.test_config,
            mcp_client=self.mock_mcp_client
        )
        
        response = await agent.process("Test request")
        
        self.assertIsInstance(response, AgentResponse)
        self.assertEqual(response.agent_name, "Test Agent")
        self.assertEqual(response.content, "Test response")
        self.assertEqual(len(agent.memory), 1)
    
    def test_process(self):
        """Test process method wrapper."""
        asyncio.run(self.async_test_process())
    
    def test_error_handling(self):
        """Test error handling in the process method."""
        # Configure the graph to return an error
        self.mock_compiled_graph.arun.return_value = {
            "input": "Test request",
            "result": None,
            "attempts": 3,
            "verified": False,
            "error": "Test error",
            "tool_calls": [],
            "next": "end"
        }
        
        agent = ModernBaseAgent(
            llm=self.mock_llm,
            config=self.test_config,
            mcp_client=self.mock_mcp_client
        )
        
        response = asyncio.run(agent.process("Test request"))
        
        self.assertIsInstance(response, AgentResponse)
        self.assertEqual(response.content, "")
        self.assertIsNotNone(response.error)
        self.assertTrue("Test error" in response.error)

if __name__ == '__main__':
    unittest.main()
