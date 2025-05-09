"""
Atlassian tools utility module.
Provides utility classes for interacting with Atlassian products (Jira and Confluence)
through the MCP server.
"""

import logging
import asyncio
from typing import Dict, List, Any, Optional, Union
from datetime import datetime
import json

from ..mcp_client import MCPClient


class BaseAtlassianTools:
    """Base class for Atlassian tools."""
    
    def __init__(self, mcp_client: MCPClient):
        """
        Initialize the base Atlassian tools.
        
        Args:
            mcp_client: MCP client instance for communicating with the MCP server
        """
        self.mcp_client = mcp_client
        self.logger = logging.getLogger(f"utils.{self.__class__.__name__}")
    
    async def _send_mcp_request(self, method: str, params: Dict[str, Any] = None) -> Dict[str, Any]:
        """
        Send a request to the Atlassian MCP server.
        
        Args:
            method: Method name to call
            params: Method parameters
            
        Returns:
            Response from the MCP server
        
        Raises:
            Exception: If the MCP request fails
        """
        try:
            result = await self.mcp_client.send_request(
                server="atlassian",
                method=method,
                params=params or {}
            )
            return result.get("result", {})
        except Exception as e:
            self.logger.error(f"Error sending MCP request {method}: {str(e)}")
            raise


class JiraTools(BaseAtlassianTools):
    """Tools for interacting with Jira."""
    
    async def get_projects(self) -> List[Dict[str, Any]]:
        """
        Get all Jira projects accessible to the user.
        
        Returns:
            List of projects
        """
        result = await self._send_mcp_request("get_jira_projects")
        return result.get("projects", [])
    
    async def create_project(
        self, 
        name: str, 
        key: str = None, 
        description: str = None,
        lead_account_id: str = None, 
        project_type_key: str = "software"
    ) -> Dict[str, Any]:
        """
        Create a new Jira project.
        
        Args:
            name: Project name
            key: Project key (optional, will be auto-generated if not provided)
            description: Project description
            lead_account_id: Account ID of the project lead
            project_type_key: Type of project (software, business, etc.)
            
        Returns:
            Project creation result
        """
        params = {
            "name": name,
            "description": description,
            "project_type_key": project_type_key
        }
        
        # Add optional parameters if provided
        if key:
            params["key"] = key
        if lead_account_id:
            params["lead_account_id"] = lead_account_id
        
        result = await self._send_mcp_request("create_jira_project", params)
        return result.get("project", {})
    
    async def get_issues(
        self, 
        project_key: str = None, 
        jql: str = None, 
        max_results: int = 50
    ) -> List[Dict[str, Any]]:
        """
        Get Jira issues based on JQL or project key.
        
        Args:
            project_key: The project key to get issues from
            jql: JQL query to use instead of project_key
            max_results: Maximum number of results to return
            
        Returns:
            List of issues
        """
        params = {
            "max_results": max_results
        }
        
        if project_key:
            params["project_key"] = project_key
        if jql:
            params["jql"] = jql
        
        result = await self._send_mcp_request("get_jira_issues", params)
        return result.get("issues", [])
    
    async def create_issue(
        self, 
        project_key: str, 
        summary: str, 
        description: str = None,
        issue_type: str = "Task", 
        priority: str = "Medium"
    ) -> Dict[str, Any]:
        """
        Create a new Jira issue.
        
        Args:
            project_key: The project key
            summary: Issue summary
            description: Issue description
            issue_type: Issue type (Task, Bug, Story, etc.)
            priority: Issue priority (Lowest, Low, Medium, High, Highest)
            
        Returns:
            Issue creation result
        """
        params = {
            "project_key": project_key,
            "summary": summary,
            "issue_type": issue_type,
            "priority": priority
        }
        
        if description:
            params["description"] = description
        
        result = await self._send_mcp_request("create_jira_issue", params)
        return result.get("issue", {})
    
    async def update_progress(
        self, 
        issue_key: str, 
        progress: int, 
        note: str = None
    ) -> Dict[str, Any]:
        """
        Update the progress of a Jira issue.
        
        Args:
            issue_key: The issue key
            progress: Progress percentage (0-100)
            note: Optional note to add to the issue
            
        Returns:
            Update result
        """
        params = {
            "issue_key": issue_key,
            "progress": progress
        }
        
        if note:
            params["note"] = note
        
        result = await self._send_mcp_request("update_jira_progress", params)
        return result


class ConfluenceTools(BaseAtlassianTools):
    """Tools for interacting with Confluence."""
    
    async def get_spaces(self) -> List[Dict[str, Any]]:
        """
        Get all Confluence spaces accessible to the user.
        
        Returns:
            List of spaces
        """
        result = await self._send_mcp_request("get_confluence_spaces")
        return result.get("spaces", [])
    
    async def create_page(
        self, 
        space_key: str, 
        title: str, 
        content: str
    ) -> Dict[str, Any]:
        """
        Create a new Confluence page.
        
        Args:
            space_key: The space key
            title: Page title
            content: Page content in storage format (HTML)
            
        Returns:
            Page creation result
        """
        params = {
            "space_key": space_key,
            "title": title,
            "content": content
        }
        
        result = await self._send_mcp_request("create_confluence_page", params)
        return result.get("page", {})
    
    def html_to_confluent_storage_format(self, html_content: str) -> str:
        """
        Convert HTML content to Confluence storage format.
        
        Args:
            html_content: HTML content
            
        Returns:
            Content in Confluence storage format
        """
        # This is a simple implementation; in a real system you might need
        # more sophisticated conversion, but Confluence generally accepts HTML
        return html_content
    
    def markdown_to_confluence_storage_format(self, markdown_content: str) -> str:
        """
        Convert Markdown content to Confluence storage format.
        
        Args:
            markdown_content: Markdown content
            
        Returns:
            Content in Confluence storage format
        
        Note:
            This is a simple implementation. In a real system,
            you might want to use a proper Markdown to HTML converter
            like markdown2 or python-markdown.
        """
        # This is a minimal implementation for demonstration
        # Replace headers
        html_content = markdown_content
        
        # Headers - h1 to h6
        for i in range(6, 0, -1):
            pattern = '#' * i + ' '
            html_content = html_content.replace(pattern, f'<h{i}>')
            
            # Close the header tag at the end of line
            lines = html_content.split('\n')
            for j, line in enumerate(lines):
                if f'<h{i}>' in line and f'</h{i}>' not in line:
                    lines[j] = line.replace('\n', f'</h{i}>\n')
            html_content = '\n'.join(lines)
        
        # Bold
        html_content = html_content.replace('**', '<strong>')
        
        # Italic
        html_content = html_content.replace('*', '<em>')
        
        # Code blocks
        html_content = html_content.replace('```', '<pre><code>')
        
        # Lists
        lines = html_content.split('\n')
        in_list = False
        
        for i, line in enumerate(lines):
            if line.strip().startswith('- '):
                if not in_list:
                    lines[i] = '<ul>\n<li>' + line.strip()[2:] + '</li>'
                    in_list = True
                else:
                    lines[i] = '<li>' + line.strip()[2:] + '</li>'
            elif in_list and not line.strip().startswith('- '):
                lines[i-1] += '\n</ul>'
                in_list = False
        
        if in_list:
            lines[-1] += '\n</ul>'
            
        html_content = '\n'.join(lines)
        
        return html_content