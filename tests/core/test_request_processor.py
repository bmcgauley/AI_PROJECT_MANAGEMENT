#!/usr/bin/env python3
"""
Tests for the request_processor module.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock, AsyncMock

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.request_processor import RequestProcessor

class TestRequestProcessor(unittest.TestCase):
    """Tests for the RequestProcessor class."""
    
    def setUp(self):
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
        
        # Create mock MCP client
        self.mock_mcp_client = MagicMock()
        
        # Create RequestProcessor instance with mocks
        self.processor = RequestProcessor(
            orchestrator=self.mock_orchestrator,
            mcp_client=self.mock_mcp_client
        )
    
    def test_classify_request_project_management(self):
        """Test request classification for project management requests."""
        # Test project management related request
        request = "Create a project timeline for the new mobile app development"
        classification = self.processor._classify_request(request)
        
        self.assertEqual(classification["primary_agent"], "Project Manager")
        self.assertIn("Project Manager", classification["involved_agents"])
        self.assertTrue(classification["is_pm_request"])
        self.assertFalse(classification["is_jira_request"])
    
    def test_classify_request_jira(self):
        """Test request classification for Jira-related requests."""
        # Test Jira-related request
        request = "Create a new Jira project named 'Mobile App'"
        classification = self.processor._classify_request(request)
        
        self.assertEqual(classification["primary_agent"], "Project Manager")
        self.assertIn("Project Manager", classification["involved_agents"])
        self.assertTrue(classification["is_pm_request"])
        self.assertTrue(classification["is_jira_request"])
    
    def test_classify_request_development(self):
        """Test request classification for development requests."""
        # Test code development request
        request = "Write a Python function to parse CSV files"
        classification = self.processor._classify_request(request)
        
        self.assertEqual(classification["primary_agent"], "Code Developer")
        self.assertIn("Code Developer", classification["involved_agents"])
        self.assertIn("Code Reviewer", classification["involved_agents"])
        self.assertTrue(classification["is_development"])
    
    def test_classify_request_research(self):
        """Test request classification for research requests."""
        # Test research request
        request = "Research the latest trends in AI project management"
        classification = self.processor._classify_request(request)
        
        self.assertEqual(classification["primary_agent"], "Research Specialist")
        self.assertIn("Research Specialist", classification["involved_agents"])
        self.assertTrue(classification["is_research"])
    
    def test_classify_request_analysis(self):
        """Test request classification for business analysis requests."""
        # Test business analysis request
        request = "Analyze the requirements for our new customer portal"
        classification = self.processor._classify_request(request)
        
        self.assertEqual(classification["primary_agent"], "Business Analyst")
        self.assertIn("Business Analyst", classification["involved_agents"])
        self.assertTrue(classification["is_analysis"])
    
    def test_classify_request_reporting(self):
        """Test request classification for reporting requests."""
        # Test reporting request
        request = "Create a report on our Q2 project deliverables"
        classification = self.processor._classify_request(request)
        
        self.assertEqual(classification["primary_agent"], "Report Drafter")
        self.assertIn("Report Drafter", classification["involved_agents"])
        self.assertIn("Report Reviewer", classification["involved_agents"])
        self.assertIn("Report Publisher", classification["involved_agents"])
        self.assertTrue(classification["is_reporting"])
    
    def test_classify_request_mixed(self):
        """Test request classification for mixed-type requests."""
        # Test mixed request (development + project management)
        request = "Create a project plan for developing a Python module for CSV parsing"
        classification = self.processor._classify_request(request)
        
        # Since it mentions project plan first, PM should be primary, but Code Developer should be involved
        self.assertEqual(classification["primary_agent"], "Project Manager")
        self.assertIn("Project Manager", classification["involved_agents"])
        self.assertTrue(classification["is_pm_request"])
    
    @patch("src.request_processor.RequestProcessor._process_jira_creation")
    @patch("src.request_processor.RequestProcessor._classify_request")
    async def test_process_request_success(self, mock_classify, mock_process_jira):
        """Test successful request processing."""
        # Setup mocks for successful request processing
        mock_classify.return_value = {
            "primary_agent": "Project Manager",
            "involved_agents": ["Project Manager", "Business Analyst"],
            "is_jira_request": False,
            "is_pm_request": True,
            "is_research": False,
            "is_development": False,
            "is_reporting": False,
            "is_analysis": False
        }
        
        # Mock crew creation and execution
        mock_crew = MagicMock()
        mock_crew.kickoff.return_value = "Task completed successfully"
        
        self.mock_orchestrator.create_crew_for_request.return_value = (mock_crew, MagicMock())
        mock_process_jira.return_value = "Task completed successfully"
        
        # Mock event handler
        mock_event_handler = AsyncMock()
        
        # Process a request
        result = await self.processor.process_request(
            "Create a project timeline",
            request_id="test-123",
            event_handler=mock_event_handler
        )
        
        # Verify the result
        self.assertEqual(result["status"], "success")
        self.assertEqual(result["processed_by"], "Project Manager")
        self.assertEqual(result["response"], "Task completed successfully")
        self.assertEqual(result["request_id"], "test-123")
        
        # Verify event handler was called
        mock_event_handler.assert_called()
    
    @patch("src.request_processor.RequestProcessor._classify_request")
    async def test_process_request_no_agents(self, mock_classify):
        """Test request processing when agents are not initialized."""
        # Reset the agents_dict to simulate uninitialized agents
        self.mock_orchestrator.agents_dict = {}
        
        # Process a request
        result = await self.processor.process_request(
            "Create a project timeline",
            request_id="test-123"
        )
        
        # Verify the error response
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["processed_by"], "System")
        self.assertIn("not initialized", result["response"])
        
        # Verify classify_request was not called
        mock_classify.assert_not_called()
    
    @patch("src.request_processor.RequestProcessor._classify_request")
    async def test_process_request_exception(self, mock_classify):
        """Test request processing when an exception occurs."""
        # Setup mocks for exception case
        mock_classify.return_value = {
            "primary_agent": "Project Manager",
            "involved_agents": ["Project Manager"],
            "is_jira_request": False,
            "is_pm_request": True,
            "is_research": False,
            "is_development": False,
            "is_reporting": False,
            "is_analysis": False
        }
        
        # Mock crew creation to raise an exception
        self.mock_orchestrator.create_crew_for_request.side_effect = Exception("Test error")
        
        # Mock event handler
        mock_event_handler = AsyncMock()
        
        # Process a request
        result = await self.processor.process_request(
            "Create a project timeline",
            request_id="test-123",
            event_handler=mock_event_handler
        )
        
        # Verify the error response
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["processed_by"], "System")
        self.assertIn("Test error", result["response"])
        
        # Verify event handler was called for the error
        mock_event_handler.assert_called_with(
            "request_error", 
            message="Error processing request: Test error",
            request_id="test-123"
        )
    
    async def test_process_jira_creation_no_jira(self):
        """Test Jira processing when not a Jira request."""
        result = await self.processor._process_jira_creation(
            "Create a document",
            "Task completed",
            is_jira_request=False,
            event_handler=None,
            request_id="test-123"
        )
        
        # Verify the result is unchanged when not a Jira request
        self.assertEqual(result, "Task completed")
    
    @patch("src.request_processor.datetime")
    async def test_process_jira_creation_success(self, mock_datetime):
        """Test successful Jira project creation."""
        # Mock datetime
        mock_datetime.now.return_value.strftime.return_value = "2025-05-04"
        
        # Mock MCP client for successful project creation
        mock_response = {
            "result": {
                "project": {
                    "key": "TEST",
                    "name": "Test Project"
                }
            }
        }
        self.mock_mcp_client.use_tool = AsyncMock(return_value=mock_response)
        
        # Mock event handler
        mock_event_handler = AsyncMock()
        
        # Process a Jira creation request
        result = await self.processor._process_jira_creation(
            "Create a project named TestProject",
            "Task analysis completed",
            is_jira_request=True,
            event_handler=mock_event_handler,
            request_id="test-123"
        )
        
        # Verify the result includes success message
        self.assertIn("Task analysis completed", result)
        self.assertIn("I've created the Jira project", result)
        self.assertIn("TEST", result)
        
        # Verify MCP client was called correctly
        self.mock_mcp_client.use_tool.assert_called_with(
            "atlassian", 
            "create_jira_project", 
            {"name": "TestProject", "description": "Project created by AI Project Management System on 2025-05-04"}
        )
    
    async def test_process_jira_creation_failure(self):
        """Test Jira project creation when it fails."""
        # Mock MCP client for failed project creation
        mock_response = {"result": {}}  # No project in result
        self.mock_mcp_client.use_tool = AsyncMock(return_value=mock_response)
        
        # Mock event handler
        mock_event_handler = AsyncMock()
        
        # Process a Jira creation request
        result = await self.processor._process_jira_creation(
            "Create a project named TestProject",
            "Task analysis completed",
            is_jira_request=True,
            event_handler=mock_event_handler,
            request_id="test-123"
        )
        
        # Verify the result includes failure message
        self.assertIn("Task analysis completed", result)
        self.assertIn("encountered an issue", result)
        self.assertIn("check your Atlassian credentials", result)
    
    async def test_process_jira_creation_exception(self):
        """Test Jira project creation when an exception occurs."""
        # Mock MCP client to raise an exception
        self.mock_mcp_client.use_tool = AsyncMock(
            side_effect=Exception("API error")
        )
        
        # Mock event handler
        mock_event_handler = AsyncMock()
        
        # Process a Jira creation request
        result = await self.processor._process_jira_creation(
            "Create a project named TestProject",
            "Task analysis completed",
            is_jira_request=True,
            event_handler=mock_event_handler,
            request_id="test-123"
        )
        
        # Verify the result is unchanged
        self.assertEqual(result, "Task analysis completed")
        
        # Verify event handler was called for the error
        mock_event_handler.assert_called_with(
            "workflow_step", 
            message="Error creating Jira project: API error",
            request_id="test-123"
        )

if __name__ == '__main__':
    unittest.main()
