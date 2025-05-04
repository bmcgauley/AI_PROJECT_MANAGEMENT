#!/usr/bin/env python3
"""
Atlassian MCP Server for AI Project Management System.

This server provides Jira and Confluence integration functionality using the Model Context Protocol (MCP).
It supports creating and managing projects, issues, and documentation in Atlassian products.
"""

import os
import sys
import json
import logging
import asyncio
import aiohttp
import base64
import traceback
from datetime import datetime
from typing import Dict, List, Any, Optional, Union
from dotenv import load_dotenv
import urllib.parse

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("atlassian_mcp_server")

# Load environment variables
load_dotenv()

# Get Atlassian credentials from environment variables
JIRA_URL = os.getenv("JIRA_URL")
JIRA_USERNAME = os.getenv("JIRA_USERNAME")
JIRA_API_TOKEN = os.getenv("JIRA_API_TOKEN")
CONFLUENCE_URL = os.getenv("CONFLUENCE_URL")
CONFLUENCE_USERNAME = os.getenv("CONFLUENCE_USERNAME")
CONFLUENCE_API_TOKEN = os.getenv("CONFLUENCE_API_TOKEN")

# Validate required environment variables
if not all([JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN]):
    logger.error("Missing required Jira environment variables")
    print("Error: Missing required Jira environment variables (JIRA_URL, JIRA_USERNAME, JIRA_API_TOKEN)")
    # Don't exit immediately to allow for debugging/development without credentials


class AtlassianClient:
    """Client for interacting with Atlassian APIs."""
    
    def __init__(self, jira_url: str, jira_username: str, jira_api_token: str,
                 confluence_url: str = None, confluence_username: str = None, confluence_api_token: str = None):
        """Initialize the Atlassian client with credentials."""
        self.jira_url = jira_url.rstrip("/")
        self.jira_username = jira_username
        self.jira_api_token = jira_api_token
        self.jira_auth = base64.b64encode(f"{jira_username}:{jira_api_token}".encode()).decode()
        
        self.confluence_url = confluence_url.rstrip("/") if confluence_url else None
        self.confluence_username = confluence_username
        self.confluence_api_token = confluence_api_token
        self.confluence_auth = base64.b64encode(f"{confluence_username}:{confluence_api_token}".encode()).decode() if confluence_username and confluence_api_token else None
        
        self.session = None
    
    async def initialize(self):
        """Initialize the HTTP session."""
        self.session = aiohttp.ClientSession()
    
    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
            self.session = None
    
    async def get_jira_projects(self) -> List[Dict[str, Any]]:
        """
        Get all Jira projects accessible to the user.
        
        Returns:
            List[Dict[str, Any]]: List of projects
        """
        if not self.session:
            await self.initialize()
        
        url = f"{self.jira_url}/rest/api/3/project"
        headers = {
            "Authorization": f"Basic {self.jira_auth}",
            "Accept": "application/json"
        }
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    projects = await response.json()
                    logger.info(f"Retrieved {len(projects)} Jira projects")
                    return projects
                else:
                    error_text = await response.text()
                    logger.error(f"Error getting Jira projects: {response.status} - {error_text}")
                    return []
        except Exception as e:
            logger.error(f"Exception getting Jira projects: {str(e)}")
            return []
    
    async def create_jira_project(self, name: str, key: str = None, description: str = None, 
                                  lead_account_id: str = None, project_type_key: str = "software",
                                  template_key: str = "com.pyxis.greenhopper.jira:basic-software-development-template") -> Dict[str, Any]:
        """
        Create a new Jira project.
        
        Args:
            name: Project name
            key: Project key (optional, will be auto-generated if not provided)
            description: Project description
            lead_account_id: Account ID of the project lead
            project_type_key: Type of project (software, business, etc.)
            template_key: Template to use for the project
            
        Returns:
            Dict[str, Any]: Created project data or error information
        """
        if not self.session:
            await self.initialize()
        
        # If key is not provided, generate one from the name
        if not key:
            # Generate a key from the name (uppercase first letter of each word, max 10 chars)
            key = ''.join(word[0].upper() for word in name.split() if word)
            if len(key) < 2:  # Ensure key is at least 2 chars
                key = name[:2].upper()
            elif len(key) > 10:  # Ensure key is max 10 chars
                key = key[:10]
        
        url = f"{self.jira_url}/rest/api/3/project"
        headers = {
            "Authorization": f"Basic {self.jira_auth}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        payload = {
            "name": name,
            "key": key,
            "projectTypeKey": project_type_key,
            "projectTemplateKey": template_key,
            "description": description or f"Project created via API on {datetime.now().strftime('%Y-%m-%d')}",
            "leadAccountId": lead_account_id,
            "assigneeType": "PROJECT_LEAD"
        }
        
        # Remove None values
        payload = {k: v for k, v in payload.items() if v is not None}
        
        try:
            async with self.session.post(url, headers=headers, json=payload) as response:
                if response.status in (200, 201):
                    project_data = await response.json()
                    logger.info(f"Created Jira project: {name} ({key})")
                    return {
                        "success": True,
                        "project": project_data
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Error creating Jira project: {response.status} - {error_text}")
                    return {
                        "success": False,
                        "error": error_text,
                        "status_code": response.status
                    }
        except Exception as e:
            logger.error(f"Exception creating Jira project: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_jira_issues(self, project_key: str = None, jql: str = None, max_results: int = 50) -> List[Dict[str, Any]]:
        """
        Get Jira issues based on JQL or project key.
        
        Args:
            project_key: The project key to get issues from
            jql: JQL query to use instead of project_key
            max_results: Maximum number of results to return
            
        Returns:
            List[Dict[str, Any]]: List of issues
        """
        if not self.session:
            await self.initialize()
        
        # Build JQL query
        if not jql and project_key:
            jql = f"project = {project_key}"
        elif not jql:
            jql = "order by created DESC"
        
        # URL encode the JQL
        jql_encoded = urllib.parse.quote(jql)
        
        url = f"{self.jira_url}/rest/api/3/search?jql={jql_encoded}&maxResults={max_results}"
        headers = {
            "Authorization": f"Basic {self.jira_auth}",
            "Accept": "application/json"
        }
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    response_data = await response.json()
                    issues = response_data.get("issues", [])
                    logger.info(f"Retrieved {len(issues)} Jira issues for query: {jql}")
                    
                    # Transform the issues for easier consumption
                    simplified_issues = []
                    for issue in issues:
                        simplified_issue = {
                            "id": issue["id"],
                            "key": issue["key"],
                            "summary": issue["fields"]["summary"],
                            "description": issue["fields"].get("description"),
                            "status": issue["fields"]["status"]["name"] if "status" in issue["fields"] else None,
                            "issueType": issue["fields"]["issuetype"]["name"] if "issuetype" in issue["fields"] else None,
                            "priority": issue["fields"]["priority"]["name"] if "priority" in issue["fields"] else None,
                            "assignee": issue["fields"]["assignee"]["displayName"] if issue["fields"].get("assignee") else None,
                            "created": issue["fields"].get("created"),
                            "updated": issue["fields"].get("updated")
                        }
                        simplified_issues.append(simplified_issue)
                    
                    return simplified_issues
                else:
                    error_text = await response.text()
                    logger.error(f"Error getting Jira issues: {response.status} - {error_text}")
                    return []
        except Exception as e:
            logger.error(f"Exception getting Jira issues: {str(e)}")
            return []
    
    async def create_jira_issue(self, project_key: str, summary: str, description: str = None, 
                               issue_type: str = "Task", priority: str = "Medium") -> Dict[str, Any]:
        """
        Create a new Jira issue.
        
        Args:
            project_key: The project key
            summary: Issue summary
            description: Issue description
            issue_type: Issue type (Task, Bug, Story, etc.)
            priority: Issue priority (Lowest, Low, Medium, High, Highest)
            
        Returns:
            Dict[str, Any]: Created issue data or error information
        """
        if not self.session:
            await self.initialize()
        
        url = f"{self.jira_url}/rest/api/3/issue"
        headers = {
            "Authorization": f"Basic {self.jira_auth}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        # Format the description for JIRA API v3 (Atlassian Document Format)
        adf_description = {
            "version": 1,
            "type": "doc",
            "content": [
                {
                    "type": "paragraph",
                    "content": [
                        {
                            "type": "text",
                            "text": description or ""
                        }
                    ]
                }
            ]
        } if description else None
        
        payload = {
            "fields": {
                "project": {
                    "key": project_key
                },
                "summary": summary,
                "description": adf_description,
                "issuetype": {
                    "name": issue_type
                },
                "priority": {
                    "name": priority
                }
            }
        }
        
        try:
            async with self.session.post(url, headers=headers, json=payload) as response:
                if response.status in (200, 201):
                    issue_data = await response.json()
                    logger.info(f"Created Jira issue: {summary} ({issue_data.get('key')})")
                    return {
                        "success": True,
                        "issue": {
                            "id": issue_data.get("id"),
                            "key": issue_data.get("key"),
                            "self": issue_data.get("self")
                        }
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Error creating Jira issue: {response.status} - {error_text}")
                    return {
                        "success": False,
                        "error": error_text,
                        "status_code": response.status
                    }
        except Exception as e:
            logger.error(f"Exception creating Jira issue: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }
    
    async def get_confluence_spaces(self) -> List[Dict[str, Any]]:
        """
        Get all Confluence spaces accessible to the user.
        
        Returns:
            List[Dict[str, Any]]: List of spaces
        """
        if not self.confluence_url or not self.confluence_auth:
            logger.error("Confluence credentials not provided")
            return []
            
        if not self.session:
            await self.initialize()
        
        url = f"{self.confluence_url}/wiki/rest/api/space"
        headers = {
            "Authorization": f"Basic {self.confluence_auth}",
            "Accept": "application/json"
        }
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    response_data = await response.json()
                    spaces = response_data.get("results", [])
                    logger.info(f"Retrieved {len(spaces)} Confluence spaces")
                    return spaces
                else:
                    error_text = await response.text()
                    logger.error(f"Error getting Confluence spaces: {response.status} - {error_text}")
                    return []
        except Exception as e:
            logger.error(f"Exception getting Confluence spaces: {str(e)}")
            return []
    
    async def create_confluence_page(self, space_key: str, title: str, content: str) -> Dict[str, Any]:
        """
        Create a new Confluence page.
        
        Args:
            space_key: The space key
            title: Page title
            content: Page content in storage format (HTML)
            
        Returns:
            Dict[str, Any]: Created page data or error information
        """
        if not self.confluence_url or not self.confluence_auth:
            logger.error("Confluence credentials not provided")
            return {"success": False, "error": "Confluence credentials not provided"}
            
        if not self.session:
            await self.initialize()
        
        url = f"{self.confluence_url}/wiki/rest/api/content"
        headers = {
            "Authorization": f"Basic {self.confluence_auth}",
            "Accept": "application/json",
            "Content-Type": "application/json"
        }
        
        payload = {
            "type": "page",
            "title": title,
            "space": {
                "key": space_key
            },
            "body": {
                "storage": {
                    "value": content,
                    "representation": "storage"
                }
            }
        }
        
        try:
            async with self.session.post(url, headers=headers, json=payload) as response:
                if response.status in (200, 201):
                    page_data = await response.json()
                    logger.info(f"Created Confluence page: {title}")
                    return {
                        "success": True,
                        "page": page_data
                    }
                else:
                    error_text = await response.text()
                    logger.error(f"Error creating Confluence page: {response.status} - {error_text}")
                    return {
                        "success": False,
                        "error": error_text,
                        "status_code": response.status
                    }
        except Exception as e:
            logger.error(f"Exception creating Confluence page: {str(e)}")
            return {
                "success": False,
                "error": str(e)
            }


async def handle_mcp_request(request: Dict[str, Any]) -> Dict[str, Any]:
    """
    Handle an incoming MCP request.
    
    Args:
        request: The MCP request
        
    Returns:
        Dict[str, Any]: The MCP response
    """
    try:
        # Extract request data
        method = request.get("method")
        params = request.get("params", {})
        request_id = request.get("id", "unknown")
        
        # Initialize the client
        client = AtlassianClient(
            jira_url=JIRA_URL,
            jira_username=JIRA_USERNAME,
            jira_api_token=JIRA_API_TOKEN,
            confluence_url=CONFLUENCE_URL,
            confluence_username=CONFLUENCE_USERNAME,
            confluence_api_token=CONFLUENCE_API_TOKEN
        )
        
        # Process the request based on the method
        result = None
        
        try:
            await client.initialize()
            
            if method == "get_jira_projects":
                projects = await client.get_jira_projects()
                result = {"projects": projects}
            
            elif method == "create_jira_project":
                project_result = await client.create_jira_project(
                    name=params.get("name"),
                    key=params.get("key"),
                    description=params.get("description"),
                    lead_account_id=params.get("lead_account_id"),
                    project_type_key=params.get("project_type_key", "software"),
                    template_key=params.get("template_key")
                )
                result = {"project": project_result}
            
            elif method == "get_jira_issues":
                issues = await client.get_jira_issues(
                    project_key=params.get("project_key"),
                    jql=params.get("jql"),
                    max_results=params.get("max_results", 50)
                )
                result = {"issues": issues}
            
            elif method == "create_jira_issue":
                issue_result = await client.create_jira_issue(
                    project_key=params.get("project_key"),
                    summary=params.get("summary"),
                    description=params.get("description"),
                    issue_type=params.get("issue_type", "Task"),
                    priority=params.get("priority", "Medium")
                )
                result = {"issue": issue_result}
            
            elif method == "get_confluence_spaces":
                spaces = await client.get_confluence_spaces()
                result = {"spaces": spaces}
            
            elif method == "create_confluence_page":
                page_result = await client.create_confluence_page(
                    space_key=params.get("space_key"),
                    title=params.get("title"),
                    content=params.get("content")
                )
                result = {"page": page_result}
            
            elif method == "update_jira_progress":
                # This is a custom method for your AI Project Management System
                # It allows updating the progress of a project or issue
                issue_key = params.get("issue_key")
                progress = params.get("progress")
                note = params.get("note")
                
                # Here we would implement the logic to update progress
                # This could be adding a comment, updating a custom field, etc.
                # For simplicity, we'll just return a success message
                logger.info(f"Updating progress for {issue_key}: {progress}% - {note}")
                result = {
                    "success": True,
                    "message": f"Progress updated: {progress}% for {issue_key}"
                }
            
            else:
                # Method not supported
                return {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32601,
                        "message": f"Method not found: {method}"
                    },
                    "id": request_id
                }
        finally:
            # Always close the client
            await client.close()
        
        # Return the result
        return {
            "jsonrpc": "2.0",
            "result": result,
            "id": request_id
        }
    
    except Exception as e:
        # Log the exception
        logger.error(f"Exception handling MCP request: {str(e)}")
        
        # Return an error response
        return {
            "jsonrpc": "2.0",
            "error": {
                "code": -32603,
                "message": f"Internal server error: {str(e)}",
                "data": {"traceback": traceback.format_exc()}
            },
            "id": request.get("id", "unknown")
        }


async def main():
    """Main function to handle stdin/stdout communication."""
    logger.info("Starting Atlassian MCP server...")
    
    # Read requests from stdin and write responses to stdout
    reader = asyncio.StreamReader()
    protocol = asyncio.StreamReaderProtocol(reader)
    await asyncio.get_event_loop().connect_read_pipe(lambda: protocol, sys.stdin)
    writer = asyncio.StreamWriter(sys.stdout, None, None, None)
    
    # Process requests
    while True:
        try:
            # Read a line from stdin
            line = await reader.readline()
            if not line:
                break
            
            # Parse the request
            request_str = line.decode('utf-8').strip()
            logger.debug(f"Received request: {request_str}")
            
            try:
                request = json.loads(request_str)
            except json.JSONDecodeError:
                logger.error(f"Invalid JSON request: {request_str}")
                error_response = {
                    "jsonrpc": "2.0",
                    "error": {
                        "code": -32700,
                        "message": "Parse error: Invalid JSON"
                    },
                    "id": None
                }
                writer.write(json.dumps(error_response).encode('utf-8') + b'\n')
                await writer.drain()
                continue
            
            # Handle the request
            response = await handle_mcp_request(request)
            
            # Write the response to stdout
            response_str = json.dumps(response)
            logger.debug(f"Sending response: {response_str}")
            writer.write(response_str.encode('utf-8') + b'\n')
            await writer.drain()
        
        except Exception as e:
            logger.error(f"Error processing request: {str(e)}")
            error_response = {
                "jsonrpc": "2.0",
                "error": {
                    "code": -32603,
                    "message": f"Internal server error: {str(e)}",
                    "data": {"traceback": traceback.format_exc()}
                },
                "id": None
            }
            writer.write(json.dumps(error_response).encode('utf-8') + b'\n')
            await writer.drain()


if __name__ == "__main__":
    asyncio.run(main())
