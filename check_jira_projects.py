#!/usr/bin/env python3
"""
Script to fetch Jira projects and tasks through direct API calls to Jira.
This script uses a direct approach without relying on the MCP server.
"""

import os
import sys
import json
import base64
import logging
import asyncio
import aiohttp
from typing import Dict, Any, Optional, List

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("check_jira_projects")

class JiraClient:
    """Client for direct interaction with Jira API."""
    
    def __init__(self):
        """Initialize the Jira client with credentials from environment or file."""
        # Load credentials from mcp.json
        credentials = self._load_credentials()
        
        self.jira_url = credentials.get("JIRA_URL", "").rstrip("/")
        self.jira_username = credentials.get("JIRA_USERNAME", "")
        self.jira_api_token = credentials.get("JIRA_API_TOKEN", "")
        
        # Create auth header
        if self.jira_username and self.jira_api_token:
            auth_str = f"{self.jira_username}:{self.jira_api_token}"
            self.auth_header = base64.b64encode(auth_str.encode()).decode()
        else:
            self.auth_header = ""
        
        self.session = None
        
        # Validate that we have the required credentials
        if not all([self.jira_url, self.jira_username, self.jira_api_token]):
            logger.error("Missing required Jira credentials")
            raise ValueError("Missing required Jira credentials")
    
    def _load_credentials(self) -> Dict[str, str]:
        """Load Jira credentials from mcp.json file."""
        try:
            project_root = os.path.dirname(os.path.abspath(__file__))
            config_path = os.path.join(project_root, "mcp.json")
            
            with open(config_path, 'r') as f:
                config = json.load(f)
            
            # Extract credentials from the atlassian server config
            if "mcpServers" in config and "atlassian" in config["mcpServers"]:
                return config["mcpServers"]["atlassian"].get("env", {})
            
            return {}
        except Exception as e:
            logger.error(f"Error loading credentials: {e}")
            return {}
    
    async def initialize(self):
        """Initialize the HTTP session with timeout settings."""
        # Use a timeout of 30 seconds for all operations
        timeout = aiohttp.ClientTimeout(total=30)
        self.session = aiohttp.ClientSession(timeout=timeout)
    
    async def close(self):
        """Close the HTTP session."""
        if self.session:
            await self.session.close()
    
    async def test_connection(self):
        """Test the connection to Jira."""
        url = f"{self.jira_url}/rest/api/3/myself"
        headers = {
            "Authorization": f"Basic {self.auth_header}",
            "Accept": "application/json"
        }
        
        logger.info("Testing connection to Jira...")
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    user_data = await response.json()
                    display_name = user_data.get("displayName", "Unknown User")
                    logger.info(f"Successfully connected to Jira as {display_name}")
                    return True
                else:
                    error_text = await response.text()
                    logger.error(f"Error connecting to Jira: {response.status} - {error_text}")
                    raise RuntimeError(f"Failed to connect to Jira. Status: {response.status}, Error: {error_text}")
        except asyncio.TimeoutError:
            logger.error("Connection to Jira timed out")
            raise RuntimeError("Connection to Jira timed out. Please check your network connection.")
        except Exception as e:
            logger.error(f"Exception testing connection to Jira: {str(e)}")
            raise
    
    async def get_projects(self) -> List[Dict[str, Any]]:
        """
        Get all Jira projects accessible to the user.
        
        Returns:
            List of projects
        """
        url = f"{self.jira_url}/rest/api/3/project"
        headers = {
            "Authorization": f"Basic {self.auth_header}",
            "Accept": "application/json"
        }
        
        logger.info(f"Fetching projects from: {url}")
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    projects = await response.json()
                    logger.info(f"Retrieved {len(projects)} Jira projects")
                    return projects
                else:
                    error_text = await response.text()
                    logger.error(f"Error getting Jira projects: {response.status} - {error_text}")
                    raise RuntimeError(f"Failed to get projects. Status: {response.status}, Error: {error_text}")
        except asyncio.TimeoutError:
            logger.error("Request to get Jira projects timed out")
            raise RuntimeError("Request to get Jira projects timed out")
        except Exception as e:
            logger.error(f"Exception getting Jira projects: {str(e)}")
            raise
    
    async def get_issues(self, project_key: str) -> List[Dict[str, Any]]:
        """
        Get issues for a specific project.
        
        Args:
            project_key: The project key
            
        Returns:
            List of issues
        """
        import urllib.parse
        jql = f"project = {project_key}"
        jql_encoded = urllib.parse.quote(jql)
        
        url = f"{self.jira_url}/rest/api/3/search?jql={jql_encoded}&maxResults=50"
        headers = {
            "Authorization": f"Basic {self.auth_header}",
            "Accept": "application/json"
        }
        
        logger.info(f"Fetching issues for project {project_key}")
        
        try:
            async with self.session.get(url, headers=headers) as response:
                if response.status == 200:
                    response_data = await response.json()
                    issues = response_data.get("issues", [])
                    logger.info(f"Retrieved {len(issues)} Jira issues for project {project_key}")
                    
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
                    raise RuntimeError(f"Failed to get issues. Status: {response.status}, Error: {error_text}")
        except asyncio.TimeoutError:
            logger.error(f"Request to get issues for project {project_key} timed out")
            raise RuntimeError(f"Request to get issues for project {project_key} timed out")
        except Exception as e:
            logger.error(f"Exception getting Jira issues: {str(e)}")
            raise

async def main():
    """
    Main function to check Jira projects and tasks.
    
    Initializes the Jira client, retrieves and displays projects and tasks,
    then cleans up resources.
    """
    client = None
    try:
        print("\n=== Connecting to Jira... ===")
        client = JiraClient()
        
        # Initialize the session
        await client.initialize()
        
        # Test the connection first
        print("Testing connection to Jira...")
        await client.test_connection()
        
        # Get all projects
        print("\n=== Your Jira Projects ===")
        projects = await client.get_projects()
        
        if not projects:
            print("No projects found in your Jira account.")
            return
        
        # Display projects
        for i, project in enumerate(projects, 1):
            project_name = project.get("name", "Unknown")
            project_key = project.get("key", "Unknown")
            print(f"{i}. {project_name} (Key: {project_key})")
        
        # Get and display issues for each project
        for project in projects:
            project_name = project.get("name", "Unknown")
            project_key = project.get("key", "Unknown")
            
            print(f"\n=== Tasks in Project: {project_name} ({project_key}) ===")
            
            # Get issues for this project
            try:
                issues = await client.get_issues(project_key)
                
                if not issues:
                    print("  No tasks found in this project.")
                    continue
                
                # Display the issues with detailed information
                for j, issue in enumerate(issues, 1):
                    key = issue.get("key", "N/A")
                    summary = issue.get("summary", "No summary")
                    status = issue.get("status", "Unknown")
                    priority = issue.get("priority", "Unknown")
                    issue_type = issue.get("issueType", "Task")
                    assignee = issue.get("assignee", "Unassigned")
                    
                    print(f"  {j}. [{key}] {summary}")
                    print(f"     Type: {issue_type} | Status: {status} | Priority: {priority} | Assignee: {assignee}")
            except Exception as e:
                print(f"  Error retrieving tasks for this project: {str(e)}")
                continue
    
    except Exception as e:
        logger.error(f"Error checking Jira projects and tasks: {str(e)}", exc_info=True)
        print(f"\n❌ Error: {str(e)}")
        print("\nPlease make sure:")
        print("1. Your Jira credentials in mcp.json are correct")
        print("2. Your network connection to Jira is working")
        print("3. The Jira URL is correct and accessible")
    
    finally:
        if client:
            await client.close()

if __name__ == "__main__":
    asyncio.run(main())