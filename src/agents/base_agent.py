"""
Base Agent class for the AI Project Management System.
All specialized agents inherit from this class.
"""

from abc import ABC, abstractmethod
from typing import Any, Dict, List, Optional
import logging
import asyncio

# Set up logging
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(name)s - %(levelname)s - %(message)s')

class BaseAgent(ABC):
    """
    Abstract base class for all agents in the system.
    Provides common functionality and enforces interface requirements.
    Includes support for an MCP client.
    """
    
    def __init__(self, llm, name: str, description: str, mcp_client: Optional[Any] = None):
        """
        Initialize the base agent.
        
        Args:
            llm: Language model to use for responses
            name: Name identifier for the agent
            description: Description of the agent's role and capabilities
            mcp_client: Optional client for interacting with MCP servers.
        """
        self.llm = llm
        self.name = name
        self.description = description
        self.mcp_client = mcp_client # Added MCP client instance
        self.logger = logging.getLogger(f"agent.{name}")
        self.logger.info(f"Initialized {name} agent")
        self.memory = []  # Simple memory to store past interactions
        
        # Define tool access permissions for different agent types
        self.available_tools = {
            # Default tools for all agents
            'memory-server': ['create_entities', 'create_relations', 'add_observations', 
                             'read_graph', 'search_nodes', 'open_nodes'],
            'sequential-thinking': ['sequentialthinking'],
        }
        
        # Add specialized tools based on agent type
        if "research" in name.lower():
            self.available_tools.update({
                'brave-search': ['brave_web_search', 'brave_local_search'],
                'context7': ['resolve-library-id', 'get-library-docs'],
            })
        elif "project manager" in name.lower():
            self.available_tools.update({
                'atlassian': ['create_jira_issue', 'update_jira_issue', 'search_jira_issues',
                             'create_confluence_page', 'update_confluence_page']
            })
        elif "code" in name.lower():
            self.available_tools.update({
                'github': ['create_repository', 'get_file_contents', 'create_or_update_file',
                         'search_code', 'push_files', 'create_pull_request'],
                'context7': ['resolve-library-id', 'get-library-docs'],
            })
        elif "business analyst" in name.lower():
            self.available_tools.update({
                'brave-search': ['brave_web_search', 'brave_local_search'],
                'atlassian': ['search_jira_issues', 'search_confluence']
            })
    
    @abstractmethod
    def process(self, request: Dict[str, Any]) -> Any:
        """
        Process a request and generate a response.
        Must be implemented by all concrete agent classes.
        
        Args:
            request: The request to process
            
        Returns:
            The agent's response
        """
        pass
    
    def store_memory(self, interaction: Dict[str, Any]) -> None:
        """
        Store an interaction in the agent's memory.
        
        Args:
            interaction: Dictionary containing the interaction details
        """
        self.memory.append(interaction)
        # Keep memory at a reasonable size by removing oldest entries if too large
        if len(self.memory) > 50:
            self.memory.pop(0)
    
    def get_memory(self, limit: Optional[int] = None) -> List[Dict[str, Any]]:
        """
        Retrieve the agent's memory of past interactions.
        
        Args:
            limit: Optional limit on the number of memory items to return
            
        Returns:
            List of past interactions
        """
        if limit:
            return self.memory[-limit:]
        return self.memory
        
    async def use_tool(self, server: str, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Use an MCP tool with the specified server.
        
        Args:
            server: MCP server name
            tool: Tool name to use
            arguments: Arguments for the tool
            
        Returns:
            The result from the tool
        """
        if not self.mcp_client:
            self.logger.warning(f"Cannot use {tool} - no MCP client available")
            return {"status": "error", "error": {"message": "No MCP client available"}}
            
        # Check if the agent has access to this tool
        if server not in self.available_tools or tool not in self.available_tools[server]:
            self.logger.warning(f"{self.name} does not have permission to use {tool} on {server}")
            return {
                "status": "error", 
                "error": {"message": f"Permission denied: {self.name} cannot access {tool}"}
            }
            
        try:
            result = await self.mcp_client.use_tool(server, tool, arguments)
            return result
        except Exception as e:
            self.logger.error(f"Error using tool {tool} on {server}: {str(e)}")
            return {"status": "error", "error": {"message": str(e)}}
    
    def use_tool_sync(self, server: str, tool: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """
        Synchronous wrapper for use_tool.
        
        Args:
            server: MCP server name
            tool: Tool name to use
            arguments: Arguments for the tool
            
        Returns:
            The result from the tool
        """
        try:
            loop = asyncio.get_event_loop()
        except RuntimeError:
            loop = asyncio.new_event_loop()
            asyncio.set_event_loop(loop)
            
        return loop.run_until_complete(self.use_tool(server, tool, arguments))
        
    async def search_web(self, query: str, count: int = 5) -> str:
        """
        Search the web using the brave-search MCP tool.
        
        Args:
            query: Search query
            count: Number of results to return
            
        Returns:
            Formatted search results as a string
        """
        if 'brave-search' not in self.available_tools:
            return "Web search not available for this agent."
            
        try:
            results = await self.use_tool('brave-search', 'brave_web_search', {
                "query": query,
                "count": count
            })
            
            if results.get("status") == "error":
                return f"Search error: {results.get('error', {}).get('message', 'Unknown error')}"
                
            search_results = results.get("result", {}).get("web", {}).get("results", [])
            if not search_results:
                return "No search results found."
                
            formatted_results = []
            for i, result in enumerate(search_results, 1):
                title = result.get("title", "No title")
                url = result.get("url", "")
                description = result.get("description", "No description")
                formatted_results.append(f"{i}. {title}\n   URL: {url}\n   {description}\n")
                
            return "\n".join(formatted_results)
        except Exception as e:
            self.logger.error(f"Error searching web: {str(e)}")
            return f"Error searching web: {str(e)}"
            
    async def get_library_docs(self, library_name: str, topic: Optional[str] = None) -> str:
        """
        Get documentation for a library.
        
        Args:
            library_name: Name of the library
            topic: Optional topic to focus on
            
        Returns:
            Documentation as a string
        """
        if 'context7' not in self.available_tools:
            return "Library documentation not available for this agent."
            
        try:
            # First resolve the library ID
            resolve_result = await self.use_tool('context7', 'resolve-library-id', {
                "libraryName": library_name
            })
            
            if resolve_result.get("status") == "error":
                return f"Library resolution error: {resolve_result.get('error', {}).get('message', 'Unknown error')}"
                
            library_id = resolve_result.get("result", {}).get("libraryId")
            if not library_id:
                return f"Could not find library ID for {library_name}."
                
            # Then get the documentation
            doc_args = {
                "context7CompatibleLibraryID": library_id,
                "tokens": 5000
            }
            
            if topic:
                doc_args["topic"] = topic
                
            doc_result = await self.use_tool('context7', 'get-library-docs', doc_args)
            
            if doc_result.get("status") == "error":
                return f"Documentation error: {doc_result.get('error', {}).get('message', 'Unknown error')}"
                
            return doc_result.get("result", {}).get("documentation", "No documentation available.")
        except Exception as e:
            self.logger.error(f"Error getting library docs: {str(e)}")
            return f"Error getting library documentation: {str(e)}"
            
    async def create_jira_issue(self, title: str, description: str, 
                               issue_type: str = "Task", 
                               priority: str = "Medium") -> Dict[str, Any]:
        """
        Create a Jira issue.
        
        Args:
            title: Issue title
            description: Issue description
            issue_type: Type of issue (Task, Bug, Story, etc.)
            priority: Issue priority
            
        Returns:
            Result of the operation
        """
        if 'atlassian' not in self.available_tools:
            return {"status": "error", "message": "Jira integration not available for this agent."}
            
        try:
            result = await self.use_tool('atlassian', 'create_jira_issue', {
                "title": title,
                "description": description,
                "issue_type": issue_type,
                "priority": priority
            })
            
            return result
        except Exception as e:
            self.logger.error(f"Error creating Jira issue: {str(e)}")
            return {"status": "error", "message": f"Error creating Jira issue: {str(e)}"}
            
    def _format_log(self, message: str) -> None:
        """
        Format and log a message.
        
        Args:
            message: The message to log
        """
        self.logger.info(f"{self.name}: {message}")
    
    def __str__(self) -> str:
        """String representation of the agent."""
        return f"{self.name} - {self.description}"
