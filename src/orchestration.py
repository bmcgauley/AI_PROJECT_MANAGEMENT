#!/usr/bin/env python3
"""
Orchestration module for the AI Project Management System.
Handles agent initialization, crew setup, and task management.
"""

import logging
import os
import asyncio
from typing import Dict, List, Tuple, Any, Optional, Callable
from datetime import datetime

from langchain_ollama import OllamaLLM
from crewai import Agent, Task, Crew, Process

from src.config import get_agent_config, get_ollama_config
from src.mcp_client import MCPClient
from src.agents.chat_coordinator import ChatCoordinatorAgent
from src.agents.project_manager import ProjectManagerAgent

# Set up logging
logger = logging.getLogger("ai_pm_system.orchestration")

class AgentOrchestrator:
    """
    Manages agent initialization, crew setup, and task assignment.
    Provides an interface for creating specialized agents and crews.
    """
    
    def __init__(self, llm: Optional[Any] = None, mcp_client: Optional[MCPClient] = None):
        """
        Initialize the orchestrator.
        
        Args:
            llm: Optional language model to use for agents
            mcp_client: Optional MCP client for tool execution
        """
        self.llm = llm
        self.mcp_client = mcp_client
        self.agents_dict = {}  # Dictionary of agent name -> agent object
        self.agent_descriptions = {}  # Dictionary of agent name -> description
        self.agent_states = {}  # Dictionary of agent name -> state
        self.chat_coordinator = None  # Main interface agent
        self.base_agents = {}  # Dictionary of traditional agent instances
        
    async def initialize_system(self, event_callback: Optional[Callable] = None) -> Dict[str, Any]:
        """
        Initialize the complete agent system including the ChatCoordinatorAgent interface.
        
        Args:
            event_callback: Optional callback for WebSocket events
            
        Returns:
            Dict[str, Any]: System components including coordinator and agents
        """
        if not self.llm:
            # Initialize LLM if not provided
            self.llm = self._initialize_llm()
        
        # Initialize specialized agents with Crew.ai framework
        await self.initialize_agents()
        
        # Initialize project manager agent with direct Jira access
        self._create_base_project_manager()
        
        # Create the chat coordinator agent
        self._create_chat_coordinator(event_callback)
        
        # Add agents to the chat coordinator
        for name, agent in self.agents_dict.items():
            self.chat_coordinator.add_crew_agent(name, agent)
        
        # Add base agents to the chat coordinator
        for name, agent in self.base_agents.items():
            self.chat_coordinator.add_agent(name, agent)
        
        logger.info("Initialized complete agent system with ChatCoordinatorAgent interface")
        
        return {
            "coordinator": self.chat_coordinator,
            "crew_agents": self.agents_dict,
            "base_agents": self.base_agents
        }
    
    def _create_base_project_manager(self) -> ProjectManagerAgent:
        """
        Create the base Project Manager agent for direct Jira integration.
        
        Returns:
            ProjectManagerAgent: The Project Manager agent
        """
        pm_agent = ProjectManagerAgent(llm=self.llm, mcp_client=self.mcp_client)
        
        self.base_agents["project manager"] = pm_agent
        logger.info("Initialized base Project Manager agent with Jira integration")
        
        return pm_agent
    
    def _create_chat_coordinator(self, event_callback: Optional[Callable] = None) -> ChatCoordinatorAgent:
        """
        Create the Chat Coordinator agent that serves as the main interface.
        
        Args:
            event_callback: Optional callback for WebSocket events
            
        Returns:
            ChatCoordinatorAgent: The Chat Coordinator agent
        """
        self.chat_coordinator = ChatCoordinatorAgent(
            llm=self.llm, 
            mcp_client=self.mcp_client
        )
        
        # Set event callback if provided
        if event_callback:
            self.chat_coordinator.set_event_callback(event_callback)
        
        logger.info("Initialized ChatCoordinatorAgent as main interface")
        
        return self.chat_coordinator
        
    async def initialize_agents(self) -> Dict[str, Agent]:
        """
        Initialize all agent types.
        
        Returns:
            Dict[str, Agent]: Dictionary of initialized agents
        """
        if not self.llm:
            # Initialize LLM if not provided
            self.llm = self._initialize_llm()
        
        # Create all specialized agents
        self._create_project_manager()
        self._create_research_specialist()
        self._create_business_analyst()
        self._create_code_developer()
        self._create_code_reviewer()
        self._create_report_drafter()
        self._create_report_reviewer()
        self._create_report_publisher()
        
        # Update agent states to idle
        for agent_name in self.agents_dict.keys():
            self.agent_states[agent_name] = "idle"
            
        logger.info(f"Initialized {len(self.agents_dict)} agents")
        
        return self.agents_dict
    
    def _initialize_llm(self) -> OllamaLLM:
        """
        Initialize the Ollama LLM.
        
        Returns:
            OllamaLLM: Initialized Ollama LLM
        """
        ollama_config = get_ollama_config()
        
        # Initialize Ollama LLM
        llm = OllamaLLM(
            base_url=ollama_config["base_url"],
            model=f"ollama/{ollama_config['model_name']}",  # Using ollama/ prefix to specify the provider
            temperature=0.7,
            request_timeout=120.0,
            model_kwargs={
                "system": ollama_config["system_message"]
            }
        )
        
        return llm
    
    def _create_project_manager(self) -> Agent:
        """
        Create the Project Manager agent.
        
        Returns:
            Agent: The Project Manager agent
        """
        config = get_agent_config("project_manager")
        
        agent = Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            verbose=config.get("verbose", True),
            allow_delegation=config.get("allow_delegation", True),
            llm=self.llm
        )
        
        self.agents_dict["Project Manager"] = agent
        self.agent_descriptions["Project Manager"] = "Manages projects efficiently and coordinates team efforts"
        
        return agent
    
    def _create_research_specialist(self) -> Agent:
        """
        Create the Research Specialist agent.
        
        Returns:
            Agent: The Research Specialist agent
        """
        config = get_agent_config("research_specialist")
        
        agent = Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            verbose=config.get("verbose", True),
            allow_delegation=config.get("allow_delegation", False),
            llm=self.llm
        )
        
        self.agents_dict["Research Specialist"] = agent
        self.agent_descriptions["Research Specialist"] = "Finds and analyzes information from various sources to support project decisions"
        
        return agent
    
    def _create_business_analyst(self) -> Agent:
        """
        Create the Business Analyst agent.
        
        Returns:
            Agent: The Business Analyst agent
        """
        config = get_agent_config("business_analyst")
        
        agent = Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            verbose=config.get("verbose", True),
            allow_delegation=config.get("allow_delegation", False),
            llm=self.llm
        )
        
        self.agents_dict["Business Analyst"] = agent
        self.agent_descriptions["Business Analyst"] = "Analyzes requirements and creates specifications based on project needs"
        
        return agent
    
    def _create_code_developer(self) -> Agent:
        """
        Create the Code Developer agent.
        
        Returns:
            Agent: The Code Developer agent
        """
        config = get_agent_config("code_developer")
        
        agent = Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            verbose=config.get("verbose", True),
            allow_delegation=config.get("allow_delegation", False),
            llm=self.llm
        )
        
        self.agents_dict["Code Developer"] = agent
        self.agent_descriptions["Code Developer"] = "Writes efficient, clean code based on specifications"
        
        return agent
    
    def _create_code_reviewer(self) -> Agent:
        """
        Create the Code Reviewer agent.
        
        Returns:
            Agent: The Code Reviewer agent
        """
        config = get_agent_config("code_reviewer")
        
        agent = Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            verbose=config.get("verbose", True),
            allow_delegation=config.get("allow_delegation", False),
            llm=self.llm
        )
        
        self.agents_dict["Code Reviewer"] = agent
        self.agent_descriptions["Code Reviewer"] = "Reviews code for quality, security, and best practices"
        
        return agent
    
    def _create_report_drafter(self) -> Agent:
        """
        Create the Report Drafter agent.
        
        Returns:
            Agent: The Report Drafter agent
        """
        config = get_agent_config("report_drafter")
        
        agent = Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            verbose=config.get("verbose", True),
            allow_delegation=config.get("allow_delegation", False),
            llm=self.llm
        )
        
        self.agents_dict["Report Drafter"] = agent
        self.agent_descriptions["Report Drafter"] = "Creates clear, comprehensive reports and documentation"
        
        return agent
    
    def _create_report_reviewer(self) -> Agent:
        """
        Create the Report Reviewer agent.
        
        Returns:
            Agent: The Report Reviewer agent
        """
        config = get_agent_config("report_reviewer")
        
        agent = Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            verbose=config.get("verbose", True),
            allow_delegation=config.get("allow_delegation", False),
            llm=self.llm
        )
        
        self.agents_dict["Report Reviewer"] = agent
        self.agent_descriptions["Report Reviewer"] = "Reviews reports for accuracy, clarity, and completeness"
        
        return agent
    
    def _create_report_publisher(self) -> Agent:
        """
        Create the Report Publisher agent.
        
        Returns:
            Agent: The Report Publisher agent
        """
        config = get_agent_config("report_publisher")
        
        agent = Agent(
            role=config["role"],
            goal=config["goal"],
            backstory=config["backstory"],
            verbose=config.get("verbose", True),
            allow_delegation=config.get("allow_delegation", False),
            llm=self.llm
        )
        
        self.agents_dict["Report Publisher"] = agent
        self.agent_descriptions["Report Publisher"] = "Formats and distributes reports to stakeholders"
        
        return agent
    
    def create_default_crew(self) -> Crew:
        """
        Create the default crew with all agents.
        
        Returns:
            Crew: The default crew
        """
        # Create a general task for the Project Manager
        general_task = Task(
            description="Handle general project management inquiries and coordinate responses",
            expected_output="A complete and helpful response to the user's inquiry",
            agent=self.agents_dict["Project Manager"]
        )
        
        # Create crew instance with all agents
        crew_instance = Crew(
            agents=list(self.agents_dict.values()),
            tasks=[general_task],  # Default task
            verbose=True,
            process=Process.sequential,
            manager_llm=self.llm,
        )
        
        return crew_instance
    
    def create_crew_for_request(
        self, 
        primary_agent_name: str, 
        task_description: str, 
        involved_agent_names: List[str] = None
    ) -> Tuple[Crew, Task]:
        """
        Create a crew for a specific request.
        
        Args:
            primary_agent_name: Name of the primary agent for this request
            task_description: Description of the task
            involved_agent_names: Optional list of agent names to include in the crew
            
        Returns:
            Tuple[Crew, Task]: The created crew and main task
        """
        if primary_agent_name not in self.agents_dict:
            raise ValueError(f"Agent {primary_agent_name} not found")
            
        # Use the specified agents or just the primary agent
        if involved_agent_names:
            # Filter to include only valid agent names
            valid_agent_names = [name for name in involved_agent_names if name in self.agents_dict]
            crew_agents = [self.agents_dict[name] for name in valid_agent_names]
        else:
            crew_agents = [self.agents_dict[primary_agent_name]]
        
        # Make PM the first agent if included (for coordination)
        if "Project Manager" in involved_agent_names and len(crew_agents) > 1:
            pm_index = involved_agent_names.index("Project Manager")
            pm_agent = crew_agents[pm_index]
            crew_agents.remove(pm_agent)
            crew_agents.insert(0, pm_agent)
        
        # Create the main task with the primary agent
        main_task = Task(
            description=task_description,
            expected_output="A complete and helpful response that addresses all aspects of the request",
            agent=self.agents_dict[primary_agent_name]
        )
        
        # Create a crew for this specific request
        request_crew = Crew(
            agents=crew_agents,
            tasks=[main_task],
            verbose=True,
            process=Process.sequential if len(crew_agents) == 1 else Process.hierarchical,
        )
        
        return request_crew, main_task
    
    def get_agent_descriptions(self) -> Dict[str, str]:
        """
        Get descriptions for all agents.
        
        Returns:
            Dict[str, str]: Dictionary of agent name -> description
        """
        return self.agent_descriptions
    
    def get_agent_states(self) -> Dict[str, str]:
        """
        Get states for all agents.
        
        Returns:
            Dict[str, str]: Dictionary of agent name -> state
        """
        return self.agent_states
    
    def update_agent_state(self, agent_name: str, state: str) -> None:
        """
        Update the state of an agent.
        
        Args:
            agent_name: Name of the agent
            state: New state for the agent
        """
        if agent_name in self.agent_states:
            self.agent_states[agent_name] = state
        else:
            logger.warning(f"Attempted to update state of unknown agent: {agent_name}")
