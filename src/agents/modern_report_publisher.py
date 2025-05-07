"""
Report Publisher agent implementation using the modern agent structure with Pydantic and LangGraph.
"""

from typing import Any, Dict, List, Optional, Union
import logging
from datetime import datetime

from langchain_core.tools import Tool
from ..models.agent_models import AgentConfig, AgentType
from .modern_base_agent import ModernBaseAgent

class ReportPublisherAgent(ModernBaseAgent):
    """
    Report Publisher agent implementation.
    Specializes in publishing and distributing finalized documentation.
    """
    
    def __init__(self, llm: Any, mcp_client: Optional[Any] = None, tools: Optional[List[Tool]] = None):
        """
        Initialize the Report Publisher agent.
        
        Args:
            llm: Language model to use
            mcp_client: Optional client for MCP interactions
            tools: Optional list of additional tools
        """
        # Create publishing tools
        pub_tools = self._create_pub_tools()
        all_tools = (tools or []) + pub_tools
        
        # Create the configuration for this agent
        config = AgentConfig(
            name="Report Publisher",
            description="Specializes in publishing and distributing finalized documentation.",
            agent_type=AgentType.REPORT_PUBLISHER,
            available_tools={
                'atlassian': ['publish_confluence_page', 'get_confluence_page',
                             'update_confluence_page', 'get_confluence_space'],
                'github': ['create_or_update_file', 'create_release'],
                'memory-server': ['create_entities', 'create_relations', 'add_observations',
                                'read_graph', 'search_nodes', 'open_nodes'],
                'sequential-thinking': ['sequentialthinking']
            },
            system_prompt="""You are the Report Publisher for the AI Project Management System.
            Your responsibilities include:
            
            1. Publishing finalized documentation
            2. Managing document versions and releases
            3. Ensuring proper distribution
            4. Maintaining documentation organization
            5. Managing access controls and visibility
            
            When publishing documents:
            - Verify all reviews are complete
            - Apply proper formatting and styling
            - Set appropriate access permissions
            - Update document metadata
            - Ensure proper categorization
            - Notify relevant stakeholders
            """
        )
        
        # Initialize the base agent
        super().__init__(llm=llm, config=config, tools=all_tools, mcp_client=mcp_client)
        
        self.logger = logging.getLogger("agent.report_publisher")
    
    def _create_pub_tools(self) -> List[Tool]:
        """
        Create tools for publishing capabilities.
        
        Returns:
            List of LangChain tools for publishing
        """
        tools = []
        
        # Publish document tool
        tools.append(
            Tool(
                name="publish_document",
                func=self._publish_document,
                description="Publish a finalized document to appropriate platforms."
            )
        )
        
        # Version management tool
        tools.append(
            Tool(
                name="manage_versions",
                func=self._manage_versions,
                description="Manage document versions and create releases."
            )
        )
        
        return tools
    
    async def _publish_document(self, publish_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Publish a finalized document.
        
        Args:
            publish_details: Details about the document to publish
            
        Returns:
            Publication results
        """
        try:
            # Get the document content
            content = await self.use_tool('atlassian', 'get_confluence_page', {
                "page_id": publish_details.get("page_id")
            })
            
            if not content:
                raise ValueError("Document not found")
            
            # Use sequential thinking for publication process
            pub_plan = await self.use_tool('sequential-thinking', 'sequentialthinking', {
                "thought": f"Planning publication process for: {content.get('title')}",
                "thoughtNumber": 1,
                "totalThoughts": 3,
                "nextThoughtNeeded": True
            })
            
            # Publish to Confluence
            confluence_result = await self.use_tool('atlassian', 'publish_confluence_page', {
                "page_id": publish_details.get("page_id"),
                "space": publish_details.get("space", "DOCS"),
                "version_comment": "Published final version"
            })
            
            # Also publish to GitHub if specified
            github_result = None
            if publish_details.get("publish_to_github"):
                github_result = await self.use_tool('github', 'create_or_update_file', {
                    "owner": publish_details.get("github_owner"),
                    "repo": publish_details.get("github_repo"),
                    "path": f"docs/{content.get('title')}.md",
                    "content": content.get("content"),
                    "message": f"Publish {content.get('title')}",
                    "branch": "main"
                })
            
            # Store publication record in memory graph
            await self.use_tool('memory-server', 'create_entities', {
                "entities": [{
                    "name": f"publication_{datetime.now().strftime('%Y%m%d_%H%M%S')}",
                    "entityType": "publication",
                    "observations": [
                        f"Document: {content.get('title')}",
                        f"Published to: Confluence{', GitHub' if github_result else ''}",
                        f"Status: published"
                    ]
                }]
            })
            
            return {
                "status": "success",
                "document_id": publish_details.get("page_id"),
                "confluence_url": confluence_result.get("url"),
                "github_url": github_result.get("html_url") if github_result else None,
                "timestamp": str(datetime.now())
            }
            
        except Exception as e:
            self.logger.error(f"Error publishing document: {str(e)}")
            return {
                "status": "error",
                "error": str(e)
            }
    
    async def _manage_versions(self, version_details: Dict[str, Any]) -> Dict[str, Any]:
        """
        Manage document versions and create releases.
        
        Args:
            version_details: Details about version management action
            
        Returns:
            Version management results
        """
        try:
            if version_details.get("create_release"):
                # Create GitHub release if specified
                release_result = await self.use_tool('github', 'create_release', {
                    "owner": version_details.get("github_owner"),
                    "repo": version_details.get("github_repo"),
                    "tag": version_details.get("version"),
                    "name": f"Documentation Release {version_details.get('version')}",
                    "body": version_details.get("release_notes", ""),
                    "draft": False,
                    "prerelease": False
                })
                
                return {
                    "status": "success",
                    "version": version_details.get("version"),
                    "release_url": release_result.get("html_url"),
                    "timestamp": str(datetime.now())
                }
            
            return {
                "status": "error",
                "error": "No version management action specified"
            }
            
        except Exception as e:
            self.logger.error(f"Error managing versions: {str(e)}")
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
            
            if "publish" in request.lower():
                # Publish document
                publish_details = {
                    "page_id": "123",  # Would be extracted from request
                    "space": "DOCS",
                    "publish_to_github": True,
                    "github_owner": "user",
                    "github_repo": "documentation"
                }
                
                publish_result = await self._publish_document(publish_details)
                
                if publish_result.get("status") == "success" and "version" in request.lower():
                    # Create version release if requested
                    version_result = await self._manage_versions({
                        "create_release": True,
                        "github_owner": publish_details["github_owner"],
                        "github_repo": publish_details["github_repo"],
                        "version": "v1.0.0",  # Would be extracted from request
                        "release_notes": "Initial documentation release"
                    })
                    
                    return {
                        "status": "success",
                        "task_id": task_id,
                        "results": {
                            "publication": publish_result,
                            "version": version_result
                        }
                    }
                
                return publish_result
            
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