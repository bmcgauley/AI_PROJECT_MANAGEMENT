"""
Report Drafter agent implementation using the modern agent structure with Pydantic and LangGraph.
"""

from typing import Any, Dict, List, Optional, Union
import logging
from datetime import datetime

from langchain_core.tools import Tool
from ..models.agent_models import AgentConfig, AgentType
from .modern_base_agent import ModernBaseAgent

class ReportDrafterAgent(ModernBaseAgent):
    """
    Report Drafter agent implementation.
    Specializes in creating clear, comprehensive documentation and reports.
    """
    
    def __init__(self, llm: Any, mcp_client: Optional[Any] = None, tools: Optional[List[Tool]] = None):
        """
        Initialize the Report Drafter agent.
        
        Args:
            llm: Language model to use
            mcp_client: Optional client for MCP interactions
            tools: Optional list of additional tools
        """
        # Create documentation tools
        doc_tools = self._create_doc_tools()
        all_tools = (tools or []) + doc_tools
        
        # Create the configuration for this agent
        config = AgentConfig(
            name="Report Drafter",
            description="Specializes in creating clear, comprehensive documentation and reports.",
            agent_type=AgentType.REPORT_DRAFTER,
            available_tools={
                'brave-search': ['brave_web_search'],
                'atlassian': ['create_confluence_page', 'update_confluence_page',
                             'search_confluence', 'get_confluence_page'],
                'memory-server': ['create_entities', 'create_relations', 'add_observations',
                                'read_graph', 'search_nodes', 'open_nodes'],
                'sequential-thinking': ['sequentialthinking']
            },
            system_prompt="""You are the Report Drafter for the AI Project Management System.
            Your responsibilities include:
            
            1. Creating clear, comprehensive documentation
            2. Writing various types of project reports
            3. Organizing information effectively
            4. Maintaining consistent documentation style
            5. Following documentation templates and standards
            
            When drafting documents:
            - Structure information logically and clearly
            - Use consistent formatting and style
            - Include all necessary sections and details
            - Follow project documentation standards
            - Write for the intended audience
            - Include relevant diagrams and examples
            """
        )
        
        # Initialize the base agent
        super().__init__(llm=llm, config=config, tools=all_tools, mcp_client=mcp_client)
        
        self.logger = logging.getLogger("agent.report_drafter")
    
    def _create_doc_tools(self) -> List[Tool]:
        """
        Create tools for documentation capabilities.
        
        Returns:
            List of LangChain tools for documentation
        """
        tools = []
        
        # Report drafting tool
        tools.append(
            Tool(
                name="draft_report",
                func=self._draft_report,
                description="Create a new report draft based on provided information."
            )
        )
        
        # Documentation update tool
        tools.append(
            Tool(
                name="update_documentation",
                func=self._update_documentation,
                description="Update existing documentation with new information."
            )
        )
        
        return tools
    
    async def _draft_report(self, report_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Create a new report draft.
        
        Args:
            report_details: Details about the report to create
            
        Returns:
            Draft report details
        """
        try:
            # Use sequential thinking to plan report structure
            report_plan = await self.use_tool('sequential-thinking', 'sequentialthinking', {
                "thought": f"Planning structure for report: {report_details.get('title')}",
                "thoughtNumber": 1,
                "totalThoughts": 5,
                "nextThoughtNeeded": True
            })
            
            # Search for relevant information
            search_results = await self.use_tool('brave-search', 'brave_web_search', {
                "query": f"report template {report_details.get('type', 'general')} best practices"
            })
            
            # Create the report in Confluence
            confluence_result = await self.use_tool('atlassian', 'create_confluence_page', {
                "title": report_details.get("title"),
                "content": "Draft report content",  # Would be generated based on plan
                "space": report_details.get("space", "DOCS")
            })
            
            # Store report metadata in memory graph
            await self.use_tool('memory-server', 'create_entities', {
                "entities": [{
                    "name": f"report_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "entityType": "report",
                    "observations": [
                        f"Title: {report_details.get('title')}",
                        f"Type: {report_details.get('type', 'general')}",
                        f"Status: draft"
                    ]
                }]
            })
            
            return {
                "status": "success",
                "report_id": confluence_result.get("id"),
                "report_url": confluence_result.get("url"),
                "structure": report_plan,
                "timestamp": str(datetime.now())
            }
            
        except Exception as e:
            self.logger.error(f"Error drafting report: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _update_documentation(self, update_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Update existing documentation.
        
        Args:
            update_details: Details about the documentation to update
            
        Returns:
            Update results
        """
        try:
            # Get existing content
            current_content = await self.use_tool('atlassian', 'get_confluence_page', {
                "page_id": update_details.get("page_id")
            })
            
            if not current_content:
                raise ValueError("Page not found")
            
            # Update the content
            update_result = await self.use_tool('atlassian', 'update_confluence_page', {
                "page_id": update_details.get("page_id"),
                "title": current_content.get("title"),
                "content": "Updated content",  # Would merge current with new content
                "version": current_content.get("version", {}).get("number", 1) + 1
            })
            
            return {
                "status": "success",
                "page_id": update_details.get("page_id"),
                "version": update_result.get("version", {}).get("number"),
                "timestamp": str(datetime.now())
            }
            
        except Exception as e:
            self.logger.error(f"Error updating documentation: {str(e)}")
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
            
            if "report" in request.lower() or "document" in request.lower():
                # Create new report/documentation
                report_details = {
                    "title": f"Report for Task {task_id}",
                    "type": "task_report",
                    "space": "DOCS"
                }
                
                draft_result = await self._draft_report(report_details)
                
                return {
                    "status": "success",
                    "task_id": task_id,
                    "results": draft_result
                }
            elif "update" in request.lower():
                # Update existing documentation
                update_details = {
                    "page_id": "123",  # Would be extracted from request
                    "changes": request
                }
                
                update_result = await self._update_documentation(update_details)
                
                return {
                    "status": "success",
                    "task_id": task_id,
                    "results": update_result
                }
            
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