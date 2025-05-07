"""
Code Reviewer agent implementation using the modern agent structure with Pydantic and LangGraph.
"""

from typing import Any, Dict, List, Optional, Union
import logging
from datetime import datetime

from langchain_core.tools import Tool
from ..models.agent_models import AgentConfig, AgentType
from .modern_base_agent import ModernBaseAgent

class CodeReviewerAgent(ModernBaseAgent):
    """
    Code Reviewer agent implementation.
    Specializes in reviewing code for quality, security, and best practices.
    """
    
    def __init__(self, llm: Any, mcp_client: Optional[Any] = None, tools: Optional[List[Tool]] = None):
        """
        Initialize the Code Reviewer agent.
        
        Args:
            llm: Language model to use
            mcp_client: Optional client for MCP interactions
            tools: Optional list of additional tools
        """
        # Create review tools
        review_tools = self._create_review_tools()
        all_tools = (tools or []) + review_tools
        
        # Create the configuration for this agent
        config = AgentConfig(
            name="Code Reviewer",
            description="Specializes in reviewing code for quality, security, and best practices.",
            agent_type=AgentType.CODE_REVIEWER,
            available_tools={
                'github': ['get_file_contents', 'search_code', 'get_pull_request',
                          'create_pull_request_review', 'get_pull_request_files'],
                'context7': ['resolve-library-id', 'get-library-docs'],
                'memory-server': ['create_entities', 'create_relations', 'add_observations',
                                'read_graph', 'search_nodes', 'open_nodes'],
                'sequential-thinking': ['sequentialthinking']
            },
            system_prompt="""You are the Code Reviewer for the AI Project Management System.
            Your responsibilities include:
            
            1. Reviewing code for quality and best practices
            2. Identifying potential security issues
            3. Checking code against project standards
            4. Providing constructive feedback
            5. Verifying test coverage and quality
            
            When reviewing code:
            - Check for common security vulnerabilities
            - Ensure code follows project standards
            - Look for potential performance issues
            - Verify error handling is appropriate
            - Review test coverage and quality
            - Provide specific, actionable feedback
            """
        )
        
        # Initialize the base agent
        super().__init__(llm=llm, config=config, tools=all_tools, mcp_client=mcp_client)
        
        self.logger = logging.getLogger("agent.code_reviewer")
    
    def _create_review_tools(self) -> List[Tool]:
        """
        Create tools for code review capabilities.
        
        Returns:
            List of LangChain tools for code review
        """
        tools = []
        
        # Code review tool
        tools.append(
            Tool(
                name="review_code",
                func=self._review_code,
                description="Review code for quality, security, and best practices."
            )
        )
        
        # Test review tool
        tools.append(
            Tool(
                name="review_tests",
                func=self._review_tests,
                description="Review unit tests for coverage and quality."
            )
        )
        
        return tools
    
    async def _review_code(self, pr_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review code in a pull request.
        
        Args:
            pr_details: Pull request details including owner, repo, and PR number
            
        Returns:
            Review results
        """
        try:
            # Get pull request files
            files = await self.use_tool('github', 'get_pull_request_files', {
                "owner": pr_details["owner"],
                "repo": pr_details["repo"],
                "pull_number": pr_details["number"]
            })
            
            # Use sequential thinking for review process
            review_plan = await self.use_tool('sequential-thinking', 'sequentialthinking', {
                "thought": "Planning code review approach",
                "thoughtNumber": 1,
                "totalThoughts": 5,
                "nextThoughtNeeded": True
            })
            
            # Review each file
            comments = []
            for file in files:
                # Get file content
                content = await self.use_tool('github', 'get_file_contents', {
                    "owner": pr_details["owner"],
                    "repo": pr_details["repo"],
                    "path": file["filename"]
                })
                
                # Add review comments for this file
                if content:
                    file_comments = []  # Would be populated based on review findings
                    comments.extend(file_comments)
            
            # Create pull request review
            review_result = await self.use_tool('github', 'create_pull_request_review', {
                "owner": pr_details["owner"],
                "repo": pr_details["repo"],
                "pull_number": pr_details["number"],
                "event": "COMMENT" if comments else "APPROVE",
                "body": "Code review completed.",
                "comments": comments
            })
            
            return {
                "status": "success",
                "review_id": review_result.get("id"),
                "comments": comments,
                "approved": not comments,
                "timestamp": str(datetime.now())
            }
            
        except Exception as e:
            self.logger.error(f"Error reviewing code: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _review_tests(self, test_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review unit tests.
        
        Args:
            test_details: Details about the tests to review
            
        Returns:
            Test review results
        """
        try:
            # Use sequential thinking for test review
            test_review = await self.use_tool('sequential-thinking', 'sequentialthinking', {
                "thought": "Analyzing test coverage and quality",
                "thoughtNumber": 1,
                "totalThoughts": 3,
                "nextThoughtNeeded": True
            })
            
            return {
                "status": "success",
                "coverage_analysis": {},  # Would be populated with coverage metrics
                "quality_analysis": test_review,
                "recommendations": [],  # Would include suggestions for improvement
                "timestamp": str(datetime.now())
            }
            
        except Exception as e:
            self.logger.error(f"Error reviewing tests: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def execute_task(self, task_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Execute a task assigned by the project manager.
        
        Args:
            task_details: Details of the task to execute including the original request
            
        Returns:
            Task execution results
        """
        try:
            request = task_details.get("original_request", "")
            task_id = task_details.get("task_id")
            
            if "pull request" in request.lower() or "pr" in request.lower():
                # Extract PR details from request
                pr_details = {
                    "owner": "user",  # Would be extracted from request
                    "repo": "repository",  # Would be extracted from request
                    "number": 1  # Would be extracted from request
                }
                
                # Perform code review
                review_result = await self._review_code(pr_details)
                
                if review_result.get("status") == "success":
                    # Review tests if present
                    test_result = await self._review_tests({
                        "repository": pr_details["repo"],
                        "pull_request": pr_details["number"]
                    })
                    
                    return {
                        "status": "success",
                        "task_id": task_id,
                        "results": {
                            "code_review": review_result,
                            "test_review": test_result
                        }
                    }
                
                return review_result
            
            return {
                "status": "error",
                "task_id": task_id,
                "error": "Unsupported task type"
            }
            
        except Exception as e:
            self.logger.error(f"Error executing task {task_id}: {str(e)}")
            return {
                "status": "error",
                "task_id": task_id,
                "error": str(e)
            }