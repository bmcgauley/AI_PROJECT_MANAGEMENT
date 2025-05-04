#!/usr/bin/env python3
"""
Unit tests for the orchestration module.
Tests agent initialization, crew setup, and task management functionality.
"""

import unittest
from unittest.mock import patch, MagicMock
import sys
import os
from pathlib import Path

# Add the src directory to the Python path
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../../src')))

from orchestration import OrchestratorEngine
from agents.base_agent import BaseAgent


class TestOrchestratorEngine(unittest.TestCase):
    """Test cases for the OrchestratorEngine class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        self.config = {
            "user_id": "test-user",
            "api_keys": {
                "openai": "test-key",
                "anthropic": "test-key"
            },
            "model_provider": "openai",
            "default_model": "gpt-3.5-turbo",
            "agent_configs": {
                "project_manager": {"role": "Project Manager", "model": "gpt-4"},
                "business_analyst": {"role": "Business Analyst", "model": "gpt-4"}
            }
        }
        
        self.orchestrator = OrchestratorEngine(self.config)
    
    @patch('orchestration.create_crew')
    @patch('orchestration.RPCAgent')
    def test_initialize_crew(self, mock_rpc_agent, mock_create_crew):
        """Test crew initialization with correct agent configuration."""
        # Setup mocks
        mock_crew = MagicMock()
        mock_create_crew.return_value = mock_crew
        mock_rpc_agent.return_value = MagicMock()
        
        # Call the method under test
        crew = self.orchestrator.initialize_crew()
        
        # Verify create_crew was called
        mock_create_crew.assert_called_once()
        
        # Verify RPCAgent was called for each agent in the config
        self.assertEqual(mock_rpc_agent.call_count, len(self.config["agent_configs"]))
        
        # Verify the returned crew is the mock crew
        self.assertEqual(crew, mock_crew)
    
    @patch('orchestration.OrchestratorEngine.load_agent_class')
    def test_initialize_agent(self, mock_load_agent):
        """Test agent initialization with correct configuration."""
        # Setup mock
        mock_agent_class = MagicMock()
        mock_agent_instance = MagicMock()
        mock_load_agent.return_value = mock_agent_class
        mock_agent_class.return_value = mock_agent_instance
        
        agent_config = {
            "role": "Test Role",
            "model": "test-model",
            "instructions": "Test instructions"
        }
        
        # Call the method under test
        agent = self.orchestrator.initialize_agent("test_agent", agent_config)
        
        # Verify load_agent_class was called with the correct agent name
        mock_load_agent.assert_called_once_with("test_agent")
        
        # Verify agent class constructor was called with the correct parameters
        mock_agent_class.assert_called_once_with(
            role=agent_config["role"],
            model_name=agent_config["model"],
            instructions=agent_config["instructions"],
            config=self.config
        )
        
        # Verify the returned agent is the mock instance
        self.assertEqual(agent, mock_agent_instance)
    
    def test_load_agent_class(self):
        """Test loading an agent class by name."""
        # Test with a known agent name
        agent_class = self.orchestrator.load_agent_class("base_agent")
        
        # Verify the returned class is the BaseAgent class
        self.assertEqual(agent_class, BaseAgent)
        
        # Test with an invalid agent name
        with self.assertRaises(ImportError):
            self.orchestrator.load_agent_class("nonexistent_agent")
    
    @patch('orchestration.OrchestratorEngine.initialize_agent')
    def test_setup_crew_tasks(self, mock_initialize_agent):
        """Test setting up crew tasks with correct configuration."""
        # Setup mock
        mock_crew = MagicMock()
        mock_agent = MagicMock()
        mock_initialize_agent.return_value = mock_agent
        
        # Set up test tasks
        test_tasks = [
            {
                "agent": "project_manager",
                "task": "Plan the project",
                "context": {"project_name": "Test Project"}
            },
            {
                "agent": "business_analyst",
                "task": "Analyze requirements",
                "context": {"requirements": ["req1", "req2"]}
            }
        ]
        
        # Call the method under test
        self.orchestrator.setup_crew_tasks(mock_crew, test_tasks)
        
        # Verify initialize_agent was called for each task
        self.assertEqual(mock_initialize_agent.call_count, len(test_tasks))
        
        # Verify crew.add_task was called for each task
        self.assertEqual(mock_crew.add_task.call_count, len(test_tasks))
    
    @patch('orchestration.OrchestratorEngine.initialize_crew')
    def test_run_task(self, mock_initialize_crew):
        """Test running a task with the crew."""
        # Setup mock
        mock_crew = MagicMock()
        mock_initialize_crew.return_value = mock_crew
        mock_result = {"status": "success", "output": "Task completed"}
        mock_crew.kickoff.return_value = mock_result
        
        # Test input
        query = "Create a project plan"
        
        # Call the method under test
        result = self.orchestrator.run_task(query)
        
        # Verify initialize_crew was called
        mock_initialize_crew.assert_called_once()
        
        # Verify crew.kickoff was called
        mock_crew.kickoff.assert_called_once_with(query)
        
        # Verify the result is the mock result
        self.assertEqual(result, mock_result)

    @patch('orchestration.OrchestratorEngine.initialize_crew')
    @patch('orchestration.mcp_client')
    def test_run_task_with_mcp(self, mock_mcp_client, mock_initialize_crew):
        """Test running a task with MCP integration."""
        # Setup mocks
        mock_crew = MagicMock()
        mock_initialize_crew.return_value = mock_crew
        mock_result = {"status": "success", "output": "Task completed with MCP"}
        mock_crew.kickoff.return_value = mock_result
        
        mock_mcp_instance = MagicMock()
        mock_mcp_client.MCPClient.return_value = mock_mcp_instance
        
        # Test input with MCP provider
        query = "Update Jira ticket PROJ-123"
        self.orchestrator.config["mcp_enabled"] = True
        self.orchestrator.config["mcp_providers"] = ["atlassian"]
        
        # Call the method under test
        result = self.orchestrator.run_task(query)
        
        # Verify initialize_crew was called
        mock_initialize_crew.assert_called_once()
        
        # Verify MCP client was initialized
        mock_mcp_client.MCPClient.assert_called_once_with(
            providers=self.orchestrator.config["mcp_providers"]
        )
        
        # Verify crew.kickoff was called
        mock_crew.kickoff.assert_called_once_with(query)
        
        # Verify the result is the mock result
        self.assertEqual(result, mock_result)


if __name__ == '__main__':
    unittest.main()