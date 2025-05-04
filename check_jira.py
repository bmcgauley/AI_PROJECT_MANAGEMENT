#!/usr/bin/env python3
"""
Script to fetch Jira projects and issues through the Atlassian MCP server.
Uses the project's existing MCP client implementation.
"""

import os
import sys
import json
import asyncio
import logging
from typing import Dict, Any, Optional

# Add the project root to the Python path so we can import project modules
project_root = os.path.dirname(os.path.abspath(__file__))
sys.path.insert(0, project_root)

# Import the project's MCPClient class
from src.mcp_client import MCPClient

# Configure logging
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("check_jira")

async def check_jira_info():
    """Fetch and display Jira projects and tasks information."""
    logger.info("Initializing MCP client...")
    
    # Initialize the MCP client from the project with the correct config path
    config_path = os.path.join(project_root, "mcp.json")
    mcp_client = MCPClient(config_path)
    await mcp_client.initialize()
    
    try:
        # Get Jira projects
        logger.info("Fetching Jira projects...")
        projects_response = await mcp_client.use_tool("atlassian", "get_jira_projects", {})
        
        if "result" not in projects_response or "projects" not in projects_response["result"]:
            logger.error(f"Failed to retrieve Jira projects: {json.dumps(projects_response, indent=2)}")
            return
        
        projects = projects_response["result"]["projects"]
        logger.info(f"Found {len(projects)} Jira projects")
        
        # Display projects
        print("\n=== Your Jira Projects ===")
        if not projects:
            print("No projects found in your Jira account.")
            return
        
        for i, project in enumerate(projects, 1):
            print(f"{i}. {project.get('name')} (Key: {project.get('key')})")
        
        # Get issues for each project
        for project in projects:
            project_key = project.get("key")
            project_name = project.get("name")
            
            print(f"\n=== Tasks in Project: {project_name} ({project_key}) ===")
            
            logger.info(f"Fetching issues for project {project_key}...")
            issues_response = await mcp_client.use_tool(
                "atlassian", 
                "get_jira_issues", 
                {"project_key": project_key}
            )
            
            if "result" not in issues_response or "issues" not in issues_response["result"]:
                print(f"  Failed to retrieve tasks from this project.")
                logger.error(f"Failed to retrieve issues for project {project_key}: {json.dumps(issues_response, indent=2)}")
                continue
            
            issues = issues_response["result"]["issues"]
            if not issues:
                print("  No tasks found in this project.")
                continue
            
            # Display issues with more comprehensive information
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
        logger.error(f"Error checking Jira information: {str(e)}", exc_info=True)
    
    finally:
        # Close the MCP client properly
        await mcp_client.cleanup()

if __name__ == "__main__":
    # Run the async function
    asyncio.run(check_jira_info())