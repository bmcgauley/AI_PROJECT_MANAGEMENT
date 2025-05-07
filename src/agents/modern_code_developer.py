"""
Code Developer agent implementation using modern agent structure.
"""

from typing import Any, Dict, List, Optional
import logging
from datetime import datetime

from langchain_core.tools import Tool
from ..models.agent_models import AgentConfig, AgentType
from .modern_base_agent import ModernBaseAgent

class CodeDeveloperAgent(ModernBaseAgent):
    """
    Code Developer agent responsible for implementing features and writing code.
    """
    
    def __init__(self, llm: Any, mcp_client: Optional[Any] = None, 
                 tools: Optional[List[Tool]] = None):
        """
        Initialize the Code Developer agent.
        
        Args:
            llm: Language model to use
            mcp_client: Optional MCP client for interactions
            tools: Optional list of additional tools
        """
        development_tools = self._create_development_tools()
        all_tools = (tools or []) + development_tools
        
        config = AgentConfig(
            name="Code Developer",
            description="Implements features and writes code",
            agent_type=AgentType.CODE_DEVELOPER,
            available_tools={
                'file-operations': ['read_file', 'write_file', 'edit_file', 'list_directory'],
                'git-operations': ['create_branch', 'push_files'],
                'sequential-thinking': ['sequentialthinking'],
                'context7': ['resolve-library-id', 'get-library-docs']
            },
            system_prompt="""You are a Code Developer responsible for:
            
            1. Implementing new features
            2. Writing clean, maintainable code
            3. Following coding standards and best practices
            4. Creating unit tests
            5. Documenting code
            6. Handling technical debt
            
            Always ensure you:
            - Write well-documented code
            - Follow project coding standards
            - Create comprehensive unit tests
            - Handle edge cases and error conditions
            - Use appropriate design patterns
            - Report progress regularly
            """
        )
        
        super().__init__(llm=llm, config=config, tools=all_tools, mcp_client=mcp_client)
        self.logger = logging.getLogger("agent.code_developer")
        
    def _create_development_tools(self) -> List[Tool]:
        """Create tools for code development capabilities."""
        return [
            Tool(
                name="implement_feature",
                func=self._implement_feature,
                description="Implement a new feature based on requirements."
            ),
            Tool(
                name="create_tests",
                func=self._create_tests,
                description="Create unit tests for implemented features."
            ),
            Tool(
                name="refactor_code",
                func=self._refactor_code,
                description="Refactor existing code for better maintainability."
            )
        ]
        
    async def _implement_feature(self, feature_details: Dict[str, Any]) -> Dict[str, Any]:
        """Implement a new feature based on requirements."""
        try:
            task_id = feature_details.get("task_id")
            
            # Report starting implementation
            if self.mcp_client:
                await self.mcp_client.update_task_status({
                    "task_id": task_id,
                    "status": "implementing_feature",
                    "progress": 0.3,
                    "details": {"feature": feature_details.get("name")}
                })
            
            # Implementation logic here
            implementation = {
                "files_changed": [],
                "new_files": [],
                "tests_added": []
            }
            
            # Report completion
            if self.mcp_client:
                await self.mcp_client.update_task_status({
                    "task_id": task_id,
                    "status": "feature_implemented",
                    "progress": 0.6,
                    "details": implementation
                })
            
            return {
                "status": "success",
                "implementation": implementation
            }
            
        except Exception as e:
            self.logger.error(f"Error implementing feature: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def _create_tests(self, test_context: Dict[str, Any]) -> Dict[str, Any]:
        """Create unit tests for implemented features."""
        try:
            task_id = test_context.get("task_id")
            
            # Report test creation started
            if self.mcp_client:
                await self.mcp_client.update_task_status({
                    "task_id": task_id,
                    "status": "creating_tests",
                    "progress": 0.7,
                    "details": {"feature": test_context.get("feature_name")}
                })
            
            # Test creation logic here
            tests = {
                "unit_tests": [],
                "integration_tests": [],
                "test_coverage": 0.0
            }
            
            # Report test creation completed
            if self.mcp_client:
                await self.mcp_client.update_task_status({
                    "task_id": task_id,
                    "status": "tests_created",
                    "progress": 0.8,
                    "details": tests
                })
            
            return {
                "status": "success",
                "tests": tests
            }
            
        except Exception as e:
            self.logger.error(f"Error creating tests: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def _refactor_code(self, refactor_context: Dict[str, Any]) -> Dict[str, Any]:
        """Refactor existing code for better maintainability."""
        try:
            task_id = refactor_context.get("task_id")
            
            # Report refactoring started
            if self.mcp_client:
                await self.mcp_client.update_task_status({
                    "task_id": task_id,
                    "status": "refactoring",
                    "progress": 0.85,
                    "details": {"files": refactor_context.get("files")}
                })
            
            # Refactoring logic here
            refactoring = {
                "files_changed": [],
                "improvements": []
            }
            
            # Report refactoring completed
            if self.mcp_client:
                await self.mcp_client.update_task_status({
                    "task_id": task_id,
                    "status": "refactoring_completed",
                    "progress": 0.9,
                    "details": refactoring
                })
            
            return {
                "status": "success",
                "refactoring": refactoring
            }
            
        except Exception as e:
            self.logger.error(f"Error refactoring code: {str(e)}")
            return {"status": "error", "error": str(e)}
    
    async def execute_task(self, task_details: Dict[str, Any]) -> Dict[str, Any]:
        """Execute a code development task."""
        try:
            task_id = task_details.get("task_id", str(datetime.now().timestamp()))
            
            # Initial task status update
            if self.mcp_client:
                await self.mcp_client.update_task_status({
                    "task_id": task_id,
                    "status": "started",
                    "progress": 0.0,
                    "agent": "code_developer"
                })
            
            # Implement feature
            implementation_result = await self._implement_feature({
                "task_id": task_id,
                "name": task_details.get("feature_name"),
                "requirements": task_details.get("requirements")
            })
            
            if implementation_result.get("status") == "success":
                # Create tests
                tests_result = await self._create_tests({
                    "task_id": task_id,
                    "feature_name": task_details.get("feature_name"),
                    "implementation": implementation_result.get("implementation")
                })
                
                # Refactor if needed
                refactor_result = await self._refactor_code({
                    "task_id": task_id,
                    "files": implementation_result.get("implementation", {}).get("files_changed", [])
                })
                
                # Final task status update
                if self.mcp_client:
                    await self.mcp_client.update_task_status({
                        "task_id": task_id,
                        "status": "completed",
                        "progress": 1.0,
                        "details": {
                            "implementation": implementation_result.get("implementation"),
                            "tests": tests_result.get("tests"),
                            "refactoring": refactor_result.get("refactoring")
                        }
                    })
                
                return {
                    "status": "success",
                    "task_id": task_id,
                    "results": {
                        "implementation": implementation_result.get("implementation"),
                        "tests": tests_result.get("tests"),
                        "refactoring": refactor_result.get("refactoring")
                    }
                }
            
            return {
                "status": "error",
                "task_id": task_id,
                "error": "Failed to implement feature"
            }
            
        except Exception as e:
            self.logger.error(f"Error executing task: {str(e)}")
            return {
                "status": "error",
                "task_id": task_id,
                "error": str(e)
            }