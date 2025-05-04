"""
Unit tests for ProjectManagerAgent including Jira integration functionality.
Tests the agent's ability to handle project management requests and interact with Jira through MCP.
"""

import unittest
import os
import json
import asyncio
from unittest.mock import MagicMock, patch
from langchain.llms.fake import FakeListLLM

from src.agents.project_manager import ProjectManagerAgent
from src.mcp_client import MCPClient


class TestProjectManagerAgent(unittest.TestCase):
    """Test cases for the ProjectManagerAgent class."""
    
    def setUp(self):
        """Set up test environment before each test."""
        # Create a fake LLM for testing
        self.responses = [
            "I'll help you with your project management needs.",
            "Here's my analysis of your project's risk factors.",
            "Let me help you plan your next sprint."
        ]
        self.fake_llm = FakeListLLM(responses=self.responses)
        
        # Mock the MCPClient
        self.mock_mcp_client = MagicMock(spec=MCPClient)
        
        # Set up the ProjectManagerAgent with the mock MCP client
        self.agent = ProjectManagerAgent(
            llm=self.fake_llm,
            mcp_client=self.mock_mcp_client
        )
    
    def test_initialization(self):
        """Test that ProjectManagerAgent initializes correctly."""
        self.assertEqual(self.agent.name, "Project Manager")
        self.assertIn("PMBOK", self.agent.description)
    
    def test_process_regular_request(self):
        """Test processing a regular project management request."""
        request = {
            "original_text": "Help me manage my project risks",
            "parsed_request": {
                "category": "Risk Management",
                "details": "Need help with project risks"
            }
        }
        
        # Process the request
        response = self.agent.process(request)
        
        # Verify response
        self.assertIsInstance(response, str)
        self.assertGreater(len(response), 0)
    
    def test_store_memory(self):
        """Test that the agent stores interactions in memory."""
        memory_item = {
            "request": "Test request",
            "response": "Test response",
            "category": "Test"
        }
        
        # Store in memory
        self.agent.store_memory(memory_item)
        
        # Verify it's stored
        self.assertIn(memory_item, self.agent.memory)
    
    @patch('src.agents.project_manager.asyncio.run')
    def test_jira_request_handling(self, mock_asyncio_run):
        """Test that Jira-specific requests are handled correctly."""
        # Configure mock
        mock_asyncio_run.return_value = "Jira projects processed successfully"
        
        # Setup agent with enabled Jira
        self.mock_mcp_client.is_server_active.return_value = True  # Make Jira enabled
        agent = ProjectManagerAgent(
            llm=self.fake_llm,
            mcp_client=self.mock_mcp_client
        )
        
        # Check that Jira is enabled
        self.assertTrue(agent.jira_enabled)
        
        # Process a Jira request
        request = {
            "original_text": "Show me my Jira projects",
            "parsed_request": {
                "category": "Jira Request",
                "details": "List Jira projects"
            }
        }
        
        response = agent.process(request)
        
        # Verify that process_jira_request was called via asyncio.run
        mock_asyncio_run.assert_called_once()
        self.assertEqual(response, "Jira projects processed successfully")
    
    @patch('src.agents.project_manager.ProjectManagerAgent.use_tool')
    async def test_get_jira_projects(self, mock_use_tool):
        """Test getting Jira projects through MCP."""
        # Setup mock response
        mock_projects = [
            {"name": "Project 1", "key": "PROJ1"},
            {"name": "Project 2", "key": "PROJ2"}
        ]
        mock_response = {
            "result": {
                "projects": mock_projects
            }
        }
        mock_use_tool.return_value = mock_response
        
        # Set Jira as enabled
        self.agent.jira_enabled = True
        
        # Call method
        projects = await self.agent.get_jira_projects()
        
        # Verify
        mock_use_tool.assert_called_once_with("atlassian", "get_jira_projects", {})
        self.assertEqual(projects, mock_projects)
    
    @patch('src.agents.project_manager.ProjectManagerAgent.use_tool')
    async def test_get_jira_issues(self, mock_use_tool):
        """Test getting Jira issues for a project through MCP."""
        # Setup mock response
        mock_issues = [
            {"key": "PROJ-1", "summary": "Issue 1", "status": "To Do"},
            {"key": "PROJ-2", "summary": "Issue 2", "status": "In Progress"}
        ]
        mock_response = {
            "result": {
                "issues": mock_issues
            }
        }
        mock_use_tool.return_value = mock_response
        
        # Set Jira as enabled
        self.agent.jira_enabled = True
        
        # Call method
        issues = await self.agent.get_jira_issues("PROJ")
        
        # Verify
        mock_use_tool.assert_called_once_with("atlassian", "get_jira_issues", {"project_key": "PROJ"})
        self.assertEqual(issues, mock_issues)
    
    @patch('src.agents.project_manager.ProjectManagerAgent.use_tool')
    async def test_create_jira_issue(self, mock_use_tool):
        """Test creating a Jira issue through MCP."""
        # Setup mock response
        mock_issue_data = {
            "success": True,
            "issue": {
                "key": "PROJ-123",
                "self": "https://central-authority.atlassian.net/rest/api/3/issue/PROJ-123"
            }
        }
        mock_response = {
            "result": {
                "issue": mock_issue_data
            }
        }
        mock_use_tool.return_value = mock_response
        
        # Set Jira as enabled
        self.agent.jira_enabled = True
        
        # Call method
        result = await self.agent.create_jira_issue(
            project_key="PROJ",
            summary="Test Issue",
            description="This is a test issue",
            issue_type="Task"
        )
        
        # Verify
        mock_use_tool.assert_called_once_with(
            "atlassian", 
            "create_jira_issue", 
            {
                "project_key": "PROJ",
                "summary": "Test Issue",
                "description": "This is a test issue",
                "issue_type": "Task",
                "priority": "Medium"
            }
        )
        self.assertEqual(result, mock_issue_data)
    
    async def async_process_jira_request_test(self, request_type):
        """Helper for testing process_jira_request with different request types."""
        # Set Jira as enabled
        self.agent.jira_enabled = True
        
        if request_type == "list_projects":
            # Setup for list projects request
            self.agent.get_jira_projects = MagicMock()
            self.agent.get_jira_projects.return_value = [
                {"name": "Project 1", "key": "PROJ1"},
                {"name": "Project 2", "key": "PROJ2"}
            ]
            request_text = "list my jira projects"
        
        elif request_type == "list_issues":
            # Setup for list issues request
            self.agent.get_jira_projects = MagicMock()
            self.agent.get_jira_projects.return_value = [{"name": "Project 1", "key": "PROJ1"}]
            self.agent.get_jira_issues = MagicMock()
            self.agent.get_jira_issues.return_value = [
                {"key": "PROJ1-1", "summary": "Issue 1", "status": "To Do"}
            ]
            request_text = "list tasks in project PROJ1"
        
        elif request_type == "create_issue":
            # Setup for create issue request
            self.agent.get_jira_projects = MagicMock()
            self.agent.get_jira_projects.return_value = [{"name": "Project 1", "key": "PROJ1"}]
            self.agent.create_jira_issue = MagicMock()
            self.agent.create_jira_issue.return_value = {
                "success": True,
                "issue": {"key": "PROJ1-123"}
            }
            request_text = "create a task in project PROJ1 with summary Fix the login page"
        else:
            request_text = "tell me about jira"
        
        # Call process_jira_request
        response = await self.agent.process_jira_request(request_text)
        
        return response
    
    def test_process_jira_request_list_projects(self):
        """Test processing a request to list Jira projects."""
        response = asyncio.run(self.async_process_jira_request_test("list_projects"))
        self.assertIn("I found 2 projects", response)
    
    def test_process_jira_request_list_issues(self):
        """Test processing a request to list issues in a project."""
        response = asyncio.run(self.async_process_jira_request_test("list_issues"))
        self.assertIn("PROJ1-1", response)
    
    def test_process_jira_request_create_issue(self):
        """Test processing a request to create an issue."""
        response = asyncio.run(self.async_process_jira_request_test("create_issue"))
        self.assertIn("Successfully created", response)
    
    def test_jira_help_response(self):
        """Test generation of help response for generic Jira requests."""
        response = self.agent._generate_jira_help_response("How does Jira work?")
        self.assertIn("Here are some things I can help you with", response)
    
    def test_format_jira_response(self):
        """Test formatting a list of Jira operations into a cohesive response."""
        operations = [
            "Operation 1 completed",
            "Operation 2 completed"
        ]
        response = self.agent._format_jira_response(operations)
        self.assertIn("I've processed your Jira request", response)
        self.assertIn("Operation 1 completed", response)
        self.assertIn("Operation 2 completed", response)
    
    def test_jira_disabled(self):
        """Test behavior when Jira integration is disabled."""
        # Set Jira as disabled
        self.agent.jira_enabled = False
        
        # Attempt to get projects
        result = asyncio.run(self.agent.get_jira_projects())
        
        # Should return empty list
        self.assertEqual(result, [])


if __name__ == "__main__":
    unittest.main()