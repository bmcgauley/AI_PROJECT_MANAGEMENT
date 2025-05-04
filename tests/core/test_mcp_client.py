#!/usr/bin/env python3
"""
Unit tests for the MCP client module of the AI Project Management System.
Tests server management and tool execution functionality.
"""

import unittest
import asyncio
import json
import os
import tempfile
from unittest.mock import patch, MagicMock, AsyncMock, mock_open

from src.mcp_client import MCPClient


class TestMCPClient(unittest.TestCase):
    """Test cases for the MCPClient class."""

    def setUp(self):
        """Set up test fixtures before each test method."""
        # Create a temporary config file
        self.temp_config = tempfile.NamedTemporaryFile(delete=False)
        self.config_path = self.temp_config.name
        
        # Sample config content
        self.config_content = {
            "mcpServers": {
                "atlassian": {
                    "command": "python3",
                    "args": ["-m", "src.mcp_servers.atlassian_server"],
                    "env": {
                        "JIRA_API_TOKEN": "test_token",
                        "JIRA_BASE_URL": "https://test.atlassian.net"
                    }
                },
                "disabled_server": {
                    "command": "python3",
                    "args": ["-m", "src.mcp_servers.disabled_server"],
                    "disabled": True
                }
            }
        }
        
        # Write config to the temp file
        with open(self.config_path, 'w') as f:
            json.dump(self.config_content, f)
        
        # Create client instance
        self.client = MCPClient(self.config_path)

    def tearDown(self):
        """Clean up test fixtures after each test method."""
        # Remove the temporary config file
        os.unlink(self.config_path)

    def test_load_config(self):
        """Test loading the configuration from file."""
        config = self.client._load_config()
        self.assertEqual(config, self.config_content)
        
        # Test with invalid config path
        client_with_invalid_path = MCPClient("/invalid/path")
        config = client_with_invalid_path._load_config()
        self.assertEqual(config, {})

    @patch('asyncio.create_subprocess_exec', new_callable=AsyncMock)
    async def test_start_servers(self, mock_create_subprocess):
        """Test starting MCP servers."""
        # Setup mock process
        mock_process = AsyncMock()
        mock_create_subprocess.return_value = mock_process
        
        # Call method
        await self.client.start_servers()
        
        # Verify that only enabled servers were started
        self.assertEqual(len(self.client.active_servers), 1)
        self.assertIn('atlassian', self.client.active_servers)
        self.assertNotIn('disabled_server', self.client.active_servers)
        
        # Verify that create_subprocess_exec was called with correct args
        mock_create_subprocess.assert_called_once()
        call_args = mock_create_subprocess.call_args.args
        self.assertEqual(call_args[0], "python3")
        self.assertEqual(call_args[1], "-m")
        self.assertEqual(call_args[2], "src.mcp_servers.atlassian_server")
        
        # Verify that environment variables were set
        call_kwargs = mock_create_subprocess.call_args.kwargs
        env = call_kwargs.get('env', {})
        self.assertEqual(env.get('JIRA_API_TOKEN'), "test_token")
        self.assertEqual(env.get('JIRA_BASE_URL'), "https://test.atlassian.net")

    @patch('asyncio.create_subprocess_exec', new_callable=AsyncMock)
    async def test_start_servers_exception(self, mock_create_subprocess):
        """Test error handling when starting servers."""
        # Setup mock to raise exception
        mock_create_subprocess.side_effect = Exception("Test exception")
        
        # Call method - should not raise exception
        await self.client.start_servers()
        
        # Verify that no servers were started
        self.assertEqual(len(self.client.active_servers), 0)

    async def test_stop_servers(self):
        """Test stopping MCP servers."""
        # Setup mock processes
        mock_process1 = AsyncMock()
        mock_process2 = AsyncMock()
        
        # Add processes to active_servers
        self.client.active_servers = {
            'server1': mock_process1,
            'server2': mock_process2
        }
        
        # Call method
        await self.client.stop_servers()
        
        # Verify that terminate was called for each process
        mock_process1.terminate.assert_called_once()
        mock_process2.terminate.assert_called_once()
        
        # Verify that wait was called for each process
        mock_process1.wait.assert_called_once()
        mock_process2.wait.assert_called_once()

    async def test_stop_servers_exception(self):
        """Test error handling when stopping servers."""
        # Setup mock process that raises exception
        mock_process = AsyncMock()
        mock_process.terminate.side_effect = Exception("Test exception")
        
        # Add process to active_servers
        self.client.active_servers = {'server': mock_process}
        
        # Call method - should not raise exception
        await self.client.stop_servers()

    async def test_use_tool_server_not_found(self):
        """Test using a tool from a non-existent server."""
        # Call method with non-existent server
        result = await self.client.use_tool("nonexistent", "tool", {})
        
        # Verify error response
        self.assertEqual(result["status"], "error")
        self.assertIn("Server nonexistent not found", result["error"]["message"])

    @patch('asyncio.Lock')
    async def test_use_tool(self, mock_lock):
        """Test using a tool from a server."""
        # Setup mock lock
        mock_lock_instance = AsyncMock()
        mock_lock.return_value = mock_lock_instance
        mock_lock_instance.__aenter__.return_value = None
        mock_lock_instance.__aexit__.return_value = None
        
        # Setup mock process
        mock_process = AsyncMock()
        mock_process.stdout.readline.return_value = b'{"jsonrpc": "2.0", "result": {"status": "success"}, "id": "1"}\n'
        
        # Add process to active_servers
        self.client.active_servers = {'server': mock_process}
        self.client.locks = {'server': mock_lock_instance}
        
        # Call method
        result = await self.client.use_tool("server", "tool", {"arg": "value"})
        
        # Verify that process.stdin.write was called with correct args
        mock_process.stdin.write.assert_called_once()
        
        # Verify result
        self.assertEqual(result["result"]["status"], "success")

    @patch('asyncio.Lock')
    async def test_use_tool_empty_response(self, mock_lock):
        """Test using a tool with empty response."""
        # Setup mock lock
        mock_lock_instance = AsyncMock()
        mock_lock.return_value = mock_lock_instance
        mock_lock_instance.__aenter__.return_value = None
        mock_lock_instance.__aexit__.return_value = None
        
        # Setup mock process
        mock_process = AsyncMock()
        mock_process.stdout.readline.return_value = b''
        mock_process.stderr.readline.return_value = b'Error message'
        
        # Add process to active_servers
        self.client.active_servers = {'server': mock_process}
        self.client.locks = {'server': mock_lock_instance}
        
        # Call method
        result = await self.client.use_tool("server", "tool", {"arg": "value"})
        
        # Verify error response
        self.assertEqual(result["status"], "error")
        self.assertIn("Empty response from server", result["error"]["message"])

    @patch('asyncio.Lock')
    async def test_use_tool_invalid_json(self, mock_lock):
        """Test using a tool with invalid JSON response."""
        # Setup mock lock
        mock_lock_instance = AsyncMock()
        mock_lock.return_value = mock_lock_instance
        mock_lock_instance.__aenter__.return_value = None
        mock_lock_instance.__aexit__.return_value = None
        
        # Setup mock process
        mock_process = AsyncMock()
        mock_process.stdout.readline.return_value = b'Invalid JSON'
        
        # Add process to active_servers
        self.client.active_servers = {'server': mock_process}
        self.client.locks = {'server': mock_lock_instance}
        
        # Call method
        result = await self.client.use_tool("server", "tool", {"arg": "value"})
        
        # Verify error response
        self.assertEqual(result["status"], "error")
        self.assertIn("Invalid JSON response", result["error"]["message"])

    @patch('asyncio.Lock')
    async def test_use_tool_exception(self, mock_lock):
        """Test error handling when using a tool."""
        # Setup mock lock
        mock_lock_instance = AsyncMock()
        mock_lock.return_value = mock_lock_instance
        mock_lock_instance.__aenter__.side_effect = Exception("Test exception")
        
        # Setup mock process
        mock_process = AsyncMock()
        
        # Add process to active_servers
        self.client.active_servers = {'server': mock_process}
        self.client.locks = {'server': mock_lock_instance}
        
        # Call method
        result = await self.client.use_tool("server", "tool", {"arg": "value"})
        
        # Verify error response
        self.assertEqual(result["status"], "error")
        self.assertEqual(result["error"]["message"], "Test exception")

    def test_get_active_servers(self):
        """Test getting a list of active server names."""
        # Setup active servers
        self.client.active_servers = {
            'server1': MagicMock(),
            'server2': MagicMock()
        }
        
        # Call method
        servers = self.client.get_active_servers()
        
        # Verify result
        self.assertEqual(set(servers), {'server1', 'server2'})

    def test_is_server_active(self):
        """Test checking if a server is active."""
        # Setup active servers
        self.client.active_servers = {'server': MagicMock()}
        
        # Call method
        is_active = self.client.is_server_active('server')
        is_inactive = self.client.is_server_active('nonexistent')
        
        # Verify results
        self.assertTrue(is_active)
        self.assertFalse(is_inactive)

    async def test_check_server_health(self):
        """Test checking server health."""
        # Setup active servers
        self.client.active_servers = {'server': MagicMock()}
        
        # Call method for active server
        is_healthy = await self.client.check_server_health('server')
        
        # Call method for inactive server
        is_inactive_healthy = await self.client.check_server_health('nonexistent')
        
        # Verify results
        self.assertTrue(is_healthy)  # Placeholder implementation always returns True for active servers
        self.assertFalse(is_inactive_healthy)

    @patch('asyncio.create_subprocess_exec', new_callable=AsyncMock)
    async def test_restart_server(self, mock_create_subprocess):
        """Test restarting a server."""
        # Setup mock process
        mock_old_process = AsyncMock()
        mock_new_process = AsyncMock()
        mock_create_subprocess.return_value = mock_new_process
        
        # Add server to config and active_servers
        self.client.config = self.config_content
        self.client.active_servers = {'atlassian': mock_old_process}
        self.client.locks = {'atlassian': AsyncMock()}
        
        # Call method
        success = await self.client.restart_server('atlassian')
        
        # Verify result
        self.assertTrue(success)
        
        # Verify that old process was terminated
        mock_old_process.terminate.assert_called_once()
        mock_old_process.wait.assert_called_once()
        
        # Verify that new process was started
        mock_create_subprocess.assert_called_once()

    async def test_restart_nonexistent_server(self):
        """Test restarting a non-existent server."""
        # Call method with non-existent server
        success = await self.client.restart_server('nonexistent')
        
        # Verify result
        self.assertFalse(success)


if __name__ == '__main__':
    unittest.main()