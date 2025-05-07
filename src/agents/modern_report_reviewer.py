"""
Report Reviewer agent implementation using the modern agent structure with Pydantic and LangGraph.
"""

from typing import Any, Dict, List, Optional, Union
import logging
from datetime import datetime

from langchain_core.tools import Tool
from ..models.agent_models import AgentConfig, AgentType
from .modern_base_agent import ModernBaseAgent

class ReportReviewerAgent(ModernBaseAgent):
    """
    Report Reviewer agent implementation.
    Specializes in reviewing and providing feedback on documentation and reports.
    """
    
    def __init__(self, llm: Any, mcp_client: Optional[Any] = None, tools: Optional[List[Tool]] = None):
        """
        Initialize the Report Reviewer agent.
        
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
            name="Report Reviewer",
            description="Specializes in reviewing and improving documentation quality.",
            agent_type=AgentType.REPORT_REVIEWER,
            available_tools={
                'brave-search': ['brave_web_search'],
                'atlassian': ['get_confluence_page', 'add_confluence_comment',
                             'update_confluence_page'],
                'memory-server': ['create_entities', 'create_relations', 'add_observations',
                                'read_graph', 'search_nodes', 'open_nodes'],
                'sequential-thinking': ['sequentialthinking']
            },
            system_prompt="""You are the Report Reviewer for the AI Project Management System.
            Your responsibilities include:
            
            1. Reviewing documentation for clarity and completeness
            2. Ensuring consistency in documentation style
            3. Verifying technical accuracy of content
            4. Providing constructive feedback
            5. Maintaining documentation quality standards
            
            When reviewing documents:
            - Check for clarity and readability
            - Verify technical accuracy
            - Ensure consistent terminology
            - Look for missing information
            - Provide specific, actionable feedback
            - Consider the target audience
            """
        )
        
        # Initialize the base agent
        super().__init__(llm=llm, config=config, tools=all_tools, mcp_client=mcp_client)
        
        self.logger = logging.getLogger("agent.report_reviewer")
    
    def _create_review_tools(self) -> List[Tool]:
        """
        Create tools for documentation review capabilities.
        
        Returns:
            List of LangChain tools for documentation review
        """
        tools = []
        
        # Report review tool
        tools.append(
            Tool(
                name="review_report",
                func=self._review_report,
                description="Review a report or document for quality and completeness."
            )
        )
        
        # Feedback tool
        tools.append(
            Tool(
                name="provide_feedback",
                func=self._provide_feedback,
                description="Provide structured feedback on documentation."
            )
        )
        
        return tools
    
    async def _review_report(self, report_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Review a report or document.
        
        Args:
            report_details: Details about the report to review
            
        Returns:
            Review results
        """
        try:
            # Get the document content
            content = await self.use_tool('atlassian', 'get_confluence_page', {
                "page_id": report_details.get("page_id")
            })
            
            if not content:
                raise ValueError("Document not found")
            
            # Use sequential thinking for review process
            review_analysis = await self.use_tool('sequential-thinking', 'sequentialthinking', {
                "thought": f"Analyzing document: {content.get('title')}",
                "thoughtNumber": 1,
                "totalThoughts": 5,
                "nextThoughtNeeded": True
            })
            
            # Add review comments
            await self.use_tool('atlassian', 'add_confluence_comment', {
                "page_id": report_details.get("page_id"),
                "comment": "Review comments would go here"  # Would be based on analysis
            })
            
            return {
                "status": "success",
                "document_id": report_details.get("page_id"),
                "review_analysis": review_analysis,
                "suggestions": [],  # Would be populated based on analysis
                "timestamp": str(datetime.now())
            }
            
        except Exception as e:
            self.logger.error(f"Error reviewing report: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _provide_feedback(self, feedback_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Provide structured feedback on documentation.
        
        Args:
            feedback_details: Details about the feedback to provide
            
        Returns:
            Feedback results
        """
        try:
            # Store feedback in memory graph
            await self.use_tool('memory-server', 'create_entities', {
                "entities": [{
                    "name": f"feedback_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "entityType": "documentation_feedback",
                    "observations": [
                        f"Document: {feedback_details.get('document_id')}",
                        f"Feedback: {feedback_details.get('feedback')}",
                        f"Status: pending"
                    ]
                }]
            })
            
            # Add feedback to document
            await self.use_tool('atlassian', 'add_confluence_comment', {
                "page_id": feedback_details.get("document_id"),
                "comment": feedback_details.get("feedback")
            })
            
            return {
                "status": "success",
                "document_id": feedback_details.get("document_id"),
                "feedback_provided": True,
                "timestamp": str(datetime.now())
            }
            
        except Exception as e:
            self.logger.error(f"Error providing feedback: {str(e)}")
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
            
            if "review" in request.lower():
                # Review document
                review_details = {
                    "page_id": "123",  # Would be extracted from request
                    "type": "documentation"
                }
                
                review_result = await self._review_report(review_details)
                
                if review_result.get("status") == "success":
                    # Provide feedback based on review
                    feedback_result = await self._provide_feedback({
                        "document_id": review_details["page_id"],
                        "feedback": "Feedback based on review"  # Would be based on review_result
                    })
                    
                    return {
                        "status": "success",
                        "task_id": task_id,
                        "results": {
                            "review": review_result,
                            "feedback": feedback_result
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