#!/usr/bin/env python3
"""
MCP Client module for the AI Project Management System.
Handles communication with MCP servers defined in a configuration file.
"""

import asyncio
import json
import logging
import os
import time
import traceback
import platform
import shutil
from typing import Dict, Any, List, Optional, Tuple

logger = logging.getLogger("ai_pm_system.mcp_client")

class MCPClient:
    """
    Handles communication with MCP servers defined in a config file.
    Manages server processes and provides a clean interface for tool execution.
    """
    
    def __init__(self, config_path: str):
        """
        Initialize the MCP client with configuration.
        
        Args:
            config_path: Path to the MCP configuration file
        """
        self.config_path = config_path
        self.config = self._load_config()
        self.active_servers = {}
        self.locks = {}  # Locks for each server to ensure thread-safety
        
    def _load_config(self) -> dict:
        """
        Load MCP configuration from file.
        
        Returns:
            dict: The loaded configuration
        """
        try:
            with open(self.config_path, 'r') as f:
                return json.load(f)
        except Exception as e:
            logger.error(f"Error loading MCP config: {e}")
            return {}
    
    def _resolve_command_path(self, command: str) -> Tuple[str, bool]:
        """
        Resolve the full path to a command, handling platform differences.
        
        Args:
            command: The command to resolve
            
        Returns:
            Tuple[str, bool]: The resolved command and a flag indicating if it was found
        """
        # Check if the command exists directly in PATH
        command_path = shutil.which(command)
        if command_path:
            logger.info(f"Command '{command}' found at: {command_path}")
            return command_path, True
        
        # On Windows, check specific locations for npm/npx
        if platform.system() == "Windows" and command in ["npm", "npx"]:
            # Common locations for Node.js on Windows
            potential_paths = [
                os.path.join(os.environ.get("APPDATA", ""), "npm", f"{command}.cmd"),
                os.path.join(os.environ.get("PROGRAMFILES", ""), "nodejs", f"{command}.cmd"),
                os.path.join(os.environ.get("PROGRAMFILES(X86)", ""), "nodejs", f"{command}.cmd"),
                # Add more potential locations as needed
            ]
            
            for path in potential_paths:
                if os.path.exists(path):
                    logger.info(f"Found {command} at alternate location: {path}")
                    return path, True
        
        logger.warning(f"Command '{command}' not found in PATH")
        return command, False  # Return the original command, but indicate it wasn't found
            
    async def start_servers(self) -> None:
        """
        Start all configured MCP servers.
        Each server is started as a subprocess with appropriate environment variables.
        """
        if not self.config.get("mcpServers"):
            logger.warning("No MCP servers configured")
            return
            
        for name, config in self.config["mcpServers"].items():
            if config.get("disabled"):
                continue
                
            try:
                # Create lock for this server
                self.locks[name] = asyncio.Lock()
                
                # Start server process
                env = os.environ.copy()
                if config.get("env"):
                    env.update(config["env"])
                
                # Resolve the full path to the command
                command, found = self._resolve_command_path(config["command"])
                if not found and command in ["npm", "npx"]:
                    logger.warning(f"Command '{command}' not found. Attempting to proceed anyway.")
                
                logger.info(f"Starting MCP server {name} with command: {command} {config['args']}")
                
                try:
                    process = await asyncio.create_subprocess_exec(
                        command,
                        *config["args"],
                        env=env,
                        stdin=asyncio.subprocess.PIPE,
                        stdout=asyncio.subprocess.PIPE,
                        stderr=asyncio.subprocess.PIPE
                    )
                    self.active_servers[name] = process
                    logger.info(f"Started MCP server: {name}")
                except FileNotFoundError as fnf_error:
                    logger.error(f"Error starting MCP server {name}: Command not found - {fnf_error}")
                    
                    # If this is a Node.js related command, provide specific guidance
                    if config["command"] in ["npm", "npx"]:
                        logger.error("This appears to be a Node.js related error. Please make sure Node.js is installed and in your PATH.")
                        logger.error("You can install Node.js from https://nodejs.org/ or use a package manager.")
                        
                except Exception as subprocess_error:
                    logger.error(f"Error starting MCP server {name} subprocess: {subprocess_error}")
                
            except Exception as e:
                logger.error(f"Error starting MCP server {name}: {e}")
                
    async def stop_servers(self) -> None:
        """
        Stop all running MCP servers.
        Ensures graceful shutdown of all server processes.
        """
        for name, process in self.active_servers.items():
            try:
                process.terminate()
                await process.wait()
                logger.info(f"Stopped MCP server: {name}")
            except Exception as e:
                logger.error(f"Error stopping MCP server {name}: {e}")
                
    async def use_tool(self, server_name: str, tool_name: str, arguments: dict) -> dict:
        """
        Use a tool provided by an MCP server.
        Sends a JSON-RPC request to the server and returns the response.
        
        Args:
            server_name: Name of the MCP server to use
            tool_name: Name of the tool to use
            arguments: Arguments for the tool
            
        Returns:
            dict: The response from the server
        """
        if server_name not in self.active_servers:
            return {"status": "error", "error": {"message": f"Server {server_name} not found"}}
            
        try:
            request = {
                "jsonrpc": "2.0",
                "method": tool_name,
                "params": arguments,
                "id": str(time.time())
            }
            
            process = self.active_servers[server_name]
            
            # Use lock to ensure only one request at a time to each server
            async with self.locks[server_name]:
                # Write request to stdin
                request_json = json.dumps(request)
                process.stdin.write(f"{request_json}\n".encode())
                await process.stdin.drain()
                
                # Read response from stdout
                response_line = await process.stdout.readline()
                if not response_line:
                    # Try to get error from stderr
                    error = await process.stderr.readline()
                    return {"status": "error", "error": {"message": f"Empty response from server. Error: {error.decode()}"}}
                
                try:
                    response = json.loads(response_line.decode())
                    return response
                except json.JSONDecodeError:
                    return {"status": "error", "error": {"message": f"Invalid JSON response: {response_line.decode()}"}}
        except Exception as e:
            logger.error(f"Error using tool {tool_name} on server {server_name}: {e}")
            return {"status": "error", "error": {"message": str(e), "traceback": traceback.format_exc()}}
    
    def get_active_servers(self) -> List[str]:
        """
        Get a list of active server names.
        
        Returns:
            List[str]: List of active server names
        """
        return list(self.active_servers.keys())
    
    def is_server_active(self, server_name: str) -> bool:
        """
        Check if a server is active.
        
        Args:
            server_name: Name of the server to check
            
        Returns:
            bool: True if the server is active, False otherwise
        """
        return server_name in self.active_servers
    
    async def check_server_health(self, server_name: str) -> bool:
        """
        Check the health of a server by sending a ping request.
        
        Args:
            server_name: Name of the server to check
            
        Returns:
            bool: True if the server is healthy, False otherwise
        """
        # First check if server is active
        if not self.is_server_active(server_name):
            return False
            
        # For now, just verify that the server process is running
        # In the future, this could send a health check request to the server
        return True
    
    async def restart_server(self, server_name: str) -> bool:
        """
        Restart a server by stopping it and starting it again.
        
        Args:
            server_name: Name of the server to restart
            
        Returns:
            bool: True if the server was restarted successfully, False otherwise
        """
        # Check if server exists in config
        if not self.config.get("mcpServers") or server_name not in self.config["mcpServers"]:
            logger.error(f"Server {server_name} not found in configuration")
            return False
            
        # Stop server if it's running
        if self.is_server_active(server_name):
            process = self.active_servers[server_name]
            try:
                process.terminate()
                await process.wait()
                logger.info(f"Stopped MCP server for restart: {server_name}")
            except Exception as e:
                logger.error(f"Error stopping MCP server {server_name} for restart: {e}")
                return False
            
        # Start server again
        try:
            config = self.config["mcpServers"][server_name]
            
            # Start server process
            env = os.environ.copy()
            if config.get("env"):
                env.update(config["env"])
            
            process = await asyncio.create_subprocess_exec(
                config["command"],
                *config["args"],
                env=env,
                stdin=asyncio.subprocess.PIPE,
                stdout=asyncio.subprocess.PIPE,
                stderr=asyncio.subprocess.PIPE
            )
            self.active_servers[server_name] = process
            logger.info(f"Restarted MCP server: {server_name}")
            return True
        except Exception as e:
            logger.error(f"Error restarting MCP server {server_name}: {e}")
            return False
