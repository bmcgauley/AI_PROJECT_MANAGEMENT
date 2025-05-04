#!/usr/bin/env python3
"""
Tests for the Atlassian MCP Server implementation.
"""

import os
import sys
import json
import unittest
import asyncio
from unittest.mock import Mock, patch, AsyncMock, MagicMock
from io import StringIO

# Ensure we can import from the project root
sys.path.insert(0, os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

# Import the server module
import mcp_servers.atlassian_server as atlassian_server
from mcp_servers.atlassian_server import AtlassianClient, handle_mcp_request


class AsyncTestCase(unittest.TestCase):
    """Base class for async test cases."""
    
    def setUp(self):
        self.loop = asyncio.new_event_loop()
        asyncio.set_event_loop(self.loop)
        
    def tearDown(self):
        self.loop.close()
        
    def async_test(self, coro):
        return self.loop.run_until_complete(coro)


class TestAtlassianClient(AsyncTestCase):
    """Test the Atlassian client implementation."""
    
    def setUp(self):
        """Set up test environment."""
        super().setUp()
        # Mock environment variables
        self.env_patcher = patch.dict('os.environ', {
            'JIRA_URL': 'https://test-jira.atlassian.net',
            'JIRA_USERNAME': 'test@example.com',
            'JIRA_API_TOKEN': 'test-api-token',
            'CONFLUENCE_URL': 'https://test-confluence.atlassian.net',
            'CONFLUENCE_USERNAME': 'test@example.com',
            'CONFLUENCE_API_TOKEN': 'test-api-token'
        })
        self.env_patcher.start()
        
        # Create client
        self.client = AtlassianClient(
            jira_url='https://test-jira.atlassian.net',
            jira_username='test@example.com',
            jira_api_token='test-api-token',
            confluence_url='https://test-confluence.atlassian.net',
            confluence_username='test@example.com',
            confluence_api_token='test-api-token'
        )
    
    def tearDown(self):
        """Clean up after tests."""
        self.env_patcher.stop()
        super().tearDown()
    
    def test_initialization(self):
        """Test client initialization."""
        async def test_init():
            # Check initial state
            self.assertIsNone(self.client.session)
            
            # Mock the session creation and closing
            mock_session = AsyncMock()
            
            with patch('aiohttp.ClientSession', return_value=mock_session):
                # Initialize session
                await self.client.initialize()
                
                # Check session was created
                self.assertIsNotNone(self.client.session)
                
                # Close session
                await self.client.close()
                
                # Check session.close was called
                mock_session.close.assert_called_once()
                
                # Check session was set to None after closing
                self.assertIsNone(self.client.session)
            
        self.async_test(test_init())
    
    @patch('aiohttp.ClientSession.get')
    def test_get_jira_projects_success(self, mock_get):
        """Test successful retrieval of Jira projects."""
        async def test_get_projects():
            # Mock response
            mock_response = AsyncMock()
            mock_response.status = 200
            mock_response.json.return_value = [
                {"id": "10000", "key": "TEST", "name": "Test Project", "projectTypeKey": "software"},
                {"id": "10001", "key": "DEV", "name": "Development", "projectTypeKey": "software"}
            ]
            mock_get.return_value.__aenter__.return_value = mock_response
            
            # Mock session
            mock_session = AsyncMock()
            mock_session.get = mock_get
            
            with patch.object(self.client, 'session', mock_session):
                # Test function
                projects = await self.client.get_jira_projects()
                
                # Check results
                self.assertEqual(len(projects), 2)
                self.assertEqual(projects[0]['key'], 'TEST')
                self.assertEqual(projects[1]['name'], 'Development')
            
        self.async_test(test_get_projects())
    
    @patch('aiohttp.ClientSession.get')
    def test_get_jira_projects_error(self, mock_get):
        """Test error handling when retrieving Jira projects."""
        async def test_get_projects_error():
            # Mock error response
            mock_response = AsyncMock()
            mock_response.status = 401
            mock_response.text = AsyncMock(return_value="Unauthorized")
            mock_get.return_value.__aenter__.return_value = mock_response
            
            # Mock session
            mock_session = AsyncMock()
            mock_session.get = mock_get
            
            with patch.object(self.client, 'session', mock_session):
                # Test function
                projects = await self.client.get_jira_projects()
                
                # Check results - should be empty list on error
                self.assertEqual(projects, [])
            
        self.async_test(test_get_projects_error())
    
    @patch('aiohttp.ClientSession.post')
    def test_create_jira_project(self, mock_post):
        """Test creation of a Jira project."""
        async def test_create_project():
            # Mock response
            mock_response = AsyncMock()
            mock_response.status = 201
            mock_response.json.return_value = {
                "id": "10002",
                "key": "NEW",
                "name": "New Project",
                "self": "https://test-jira.atlassian.net/rest/api/3/project/10002"
            }
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Mock session
            mock_session = AsyncMock()
            mock_session.post = mock_post
            
            with patch.object(self.client, 'session', mock_session):
                # Test function
                result = await self.client.create_jira_project(
                    name="New Project",
                    key="NEW",
                    description="Test project description"
                )
                
                # Check results
                self.assertTrue(result['success'])
                self.assertEqual(result['project']['id'], '10002')
                self.assertEqual(result['project']['key'], 'NEW')
            
        self.async_test(test_create_project())
    
    @patch('aiohttp.ClientSession.post')
    def test_create_jira_issue(self, mock_post):
        """Test creation of a Jira issue."""
        async def test_create_issue():
            # Mock response
            mock_response = AsyncMock()
            mock_response.status = 201
            mock_response.json.return_value = {
                "id": "10100",
                "key": "TEST-1",
                "self": "https://test-jira.atlassian.net/rest/api/3/issue/10100"
            }
            mock_post.return_value.__aenter__.return_value = mock_response
            
            # Mock session
            mock_session = AsyncMock()
            mock_session.post = mock_post
            
            with patch.object(self.client, 'session', mock_session):
                # Test function
                result = await self.client.create_jira_issue(
                    project_key="TEST",
                    summary="Test Issue",
                    description="Test issue description",
                    issue_type="Task"
                )
                
                # Check results
                self.assertTrue(result['success'])
                self.assertEqual(result['issue']['key'], 'TEST-1')
            
        self.async_test(test_create_issue())


class TestMCPHandler(AsyncTestCase):
    """Test the MCP request handler."""
    
    @patch('mcp_servers.atlassian_server.AtlassianClient')
    def test_handle_get_projects_request(self, MockClient):
        """Test handling of get_jira_projects request."""
        async def test_get_projects_handler():
            # Setup mock client
            mock_client = AsyncMock()
            mock_client.get_jira_projects.return_value = [
                {"id": "10000", "key": "TEST", "name": "Test Project"}
            ]
            MockClient.return_value = mock_client
            
            # Create request
            request = {
                "jsonrpc": "2.0",
                "method": "get_jira_projects",
                "params": {},
                "id": "test-1"
            }
            
            # Test function
            response = await handle_mcp_request(request)
            
            # Check response
            self.assertEqual(response['jsonrpc'], '2.0')
            self.assertEqual(response['id'], 'test-1')
            self.assertIn('result', response)
            self.assertIn('projects', response['result'])
            self.assertEqual(len(response['result']['projects']), 1)
            self.assertEqual(response['result']['projects'][0]['key'], 'TEST')
            
        self.async_test(test_get_projects_handler())
    
    @patch('mcp_servers.atlassian_server.AtlassianClient')
    def test_handle_create_project_request(self, MockClient):
        """Test handling of create_jira_project request."""
        async def test_create_project_handler():
            # Setup mock client
            mock_client = AsyncMock()
            mock_client.create_jira_project.return_value = {
                "success": True,
                "project": {
                    "id": "10002",
                    "key": "NEW",
                    "name": "New Project"
                }
            }
            MockClient.return_value = mock_client
            
            # Create request
            request = {
                "jsonrpc": "2.0",
                "method": "create_jira_project",
                "params": {
                    "name": "New Project",
                    "key": "NEW",
                    "description": "Test project"
                },
                "id": "test-2"
            }
            
            # Test function
            response = await handle_mcp_request(request)
            
            # Check response
            self.assertEqual(response['jsonrpc'], '2.0')
            self.assertEqual(response['id'], 'test-2')
            self.assertIn('result', response)
            self.assertIn('project', response['result'])
            self.assertEqual(response['result']['project']['project']['key'], 'NEW')
            
        self.async_test(test_create_project_handler())
    
    @patch('mcp_servers.atlassian_server.AtlassianClient')
    def test_handle_invalid_method_request(self, MockClient):
        """Test handling of invalid method request."""
        async def test_invalid_method_handler():
            # Setup mock client
            mock_client = AsyncMock()
            MockClient.return_value = mock_client
            
            # Create request with invalid method
            request = {
                "jsonrpc": "2.0",
                "method": "invalid_method",
                "params": {},
                "id": "test-error"
            }
            
            # Test function
            response = await handle_mcp_request(request)
            
            # Check response - should have error
            self.assertEqual(response['jsonrpc'], '2.0')
            self.assertEqual(response['id'], 'test-error')
            self.assertIn('error', response)
            self.assertEqual(response['error']['code'], -32601)  # Method not found
            
        self.async_test(test_invalid_method_handler())
    
    @patch('mcp_servers.atlassian_server.AtlassianClient')
    def test_handle_exception_in_request(self, MockClient):
        """Test handling of exception during request processing."""
        async def test_exception_handler():
            # Setup mock client that raises exception
            mock_client = AsyncMock()
            mock_client.get_jira_projects.side_effect = Exception("Test exception")
            MockClient.return_value = mock_client
            
            # Create request
            request = {
                "jsonrpc": "2.0",
                "method": "get_jira_projects",
                "params": {},
                "id": "test-exception"
            }
            
            # Test function
            response = await handle_mcp_request(request)
            
            # Check response - should have error
            self.assertEqual(response['jsonrpc'], '2.0')
            self.assertEqual(response['id'], 'test-exception')
            self.assertIn('error', response)
            self.assertEqual(response['error']['code'], -32603)  # Internal error
            self.assertIn('Test exception', response['error']['message'])
            
        self.async_test(test_exception_handler())


if __name__ == '__main__':
    unittest.main()
