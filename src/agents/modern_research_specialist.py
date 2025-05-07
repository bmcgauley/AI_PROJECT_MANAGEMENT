"""
Research Specialist agent implementation using the modern agent structure with Pydantic and LangGraph.
"""

from typing import Any, Dict, List, Optional, Union
import logging
import asyncio
from datetime import datetime

from langchain_core.tools import Tool
from ..models.agent_models import AgentConfig, AgentType
from .modern_base_agent import ModernBaseAgent

class ResearchSpecialistAgent(ModernBaseAgent):
    """
    Research Specialist agent implementation.
    Specializes in gathering information, conducting research, and analyzing trends and best practices.
    """
    
    def __init__(self, llm: Any, mcp_client: Optional[Any] = None, tools: Optional[List[Tool]] = None):
        """
        Initialize the Research Specialist agent.
        
        Args:
            llm: Language model to use
            mcp_client: Optional client for MCP interactions
            tools: Optional list of additional tools
        """
        # Create research-related tools
        research_tools = self._create_research_tools()
        all_tools = (tools or []) + research_tools
        
        # Create the configuration for this agent
        config = AgentConfig(
            name="Research Specialist",
            description="Specializes in gathering information, conducting research, and analyzing data for project requirements.",
            agent_type=AgentType.RESEARCH_SPECIALIST,
            available_tools={
                'brave-search': ['brave_web_search', 'brave_local_search'],
                'context7': ['resolve-library-id', 'get-library-docs'],
                'memory-server': ['create_entities', 'create_relations', 'add_observations', 
                                 'read_graph', 'search_nodes', 'open_nodes'],
                'sequential-thinking': ['sequentialthinking']
            },
            system_prompt="""You are the Research Specialist for the AI Project Management System.
            Your responsibilities include:
            
            1. Gathering relevant information from various sources
            2. Analyzing trends and patterns in data
            3. Identifying best practices and industry standards
            4. Summarizing complex information into clear, actionable insights
            5. Providing well-researched reports on requested topics
            
            When conducting research:
            - Prioritize reliable sources and recent information
            - Synthesize information from multiple perspectives
            - Verify facts when possible using multiple sources
            - Structure your findings in a clear, organized manner
            - Present both established practices and innovative approaches
            """
        )
        
        # Initialize the base agent
        super().__init__(llm=llm, config=config, tools=all_tools, mcp_client=mcp_client)
    
    def _create_research_tools(self) -> List[Tool]:
        """
        Create tools for research capabilities.
        
        Returns:
            List of LangChain tools for research
        """
        tools = []
        
        # Web search tool
        tools.append(
            Tool(
                name="search_web",
                func=self._search_web,
                description="Search the web for information on a topic. Requires a search query string."
            )
        )
        
        # Library documentation tool
        tools.append(
            Tool(
                name="get_library_docs",
                func=self._get_library_docs,
                description="Get documentation for a software library. Requires library name and optional topic."
            )
        )
        
        # Local search tool
        tools.append(
            Tool(
                name="search_local",
                func=self._search_local,
                description="Search for local businesses or services. Requires a search query with location."
            )
        )
        
        return tools
    
    async def _search_web(self, query: str) -> str:
        """
        Search the web for information.
        
        Args:
            query: Search query
            
        Returns:
            Search results
        """
        return await self.use_tool('brave-search', 'brave_web_search', {
            "query": query
        })
    
    async def _get_library_docs(self, library_name: str, topic: Optional[str] = None) -> str:
        """
        Get documentation for a software library.
        
        Args:
            library_name: Name of the library
            topic: Optional topic to focus on
            
        Returns:
            Library documentation
        """
        # First resolve the library ID
        resolve_result = await self.use_tool('context7', 'resolve-library-id', {
            "libraryName": library_name
        })
        
        if resolve_result.get("status") == "error":
            return f"Error resolving library: {resolve_result.get('error', {}).get('message', 'Unknown error')}"
            
        library_id = resolve_result.get("result", {}).get("libraryId")
        if not library_id:
            return f"Could not resolve library ID for {library_name}"
            
        # Now get the documentation
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
    
    async def _search_local(self, query: str) -> str:
        """
        Search for local businesses or services.
        
        Args:
            query: Search query with location information
            
        Returns:
            Local search results
        """
        return await self.use_tool('brave-search', 'brave_local_search', {
            "query": query
        })
    
    async def conduct_research(self, topic: str, depth: str = "standard") -> Dict[str, Any]:
        """
        Conduct comprehensive research on a topic.
        
        Args:
            topic: Topic to research
            depth: Research depth (quick, standard, comprehensive)
            
        Returns:
            Research results with sources and analysis
        """
        self.logger.info(f"Conducting {depth} research on: {topic}")
        
        try:
            # Perform web search
            web_search_task = asyncio.create_task(self._search_web(topic))
            
            # Try to get library documentation if it seems like a technical topic
            doc_task = None
            if any(tech_term in topic.lower() for tech_term in ["library", "framework", "api", "sdk", "language", "python", "javascript", "react", "node"]):
                # Extract potential library name
                import re
                potential_libs = re.findall(r'\b([A-Za-z0-9_-]+(?:\.[A-Za-z0-9_-]+)*)\b', topic)
                if potential_libs:
                    doc_task = asyncio.create_task(self._get_library_docs(potential_libs[0]))
            
            # Gather results
            search_result = await web_search_task
            doc_result = await doc_task if doc_task else "No library documentation requested"
            
            # Process and combine results
            combined_research = {
                "topic": topic,
                "depth": depth,
                "web_results": search_result,
                "library_documentation": doc_result if doc_task else None,
                "timestamp": str(datetime.now())
            }
            
            return combined_research
        except Exception as e:
            self.logger.error(f"Error conducting research on {topic}: {str(e)}")
            return {
                "error": f"Research error: {str(e)}",
                "topic": topic,
                "partial_results": {}
            }