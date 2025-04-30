"""
Project Manager Agent for the AI Project Management System.
PMBOK/PMP certified agent for project planning, task management, and Jira integration.
"""

from typing import Any, Dict, Optional # Added Optional
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough

from src.agents.base_agent import BaseAgent

class ProjectManagerAgent(BaseAgent):
    """
    Agent acting as a PMBOK certified PMP professional who handles
    project management related requests, potentially using Jira or Confluence tools.
    """
    
    def __init__(self, llm, mcp_client: Optional[Any] = None): # Added mcp_client
        """
        Initialize the project manager agent.
        
        Args:
            llm: Language model to use for generating responses
            mcp_client: Optional client for interacting with MCP servers (e.g., Atlassian).
        """
        super().__init__(
            llm=llm,
            name="Project Manager",
            description="PMBOK/PMP certified agent for project planning, task management, and potentially Jira/Confluence integration via MCP.", # Updated description
            mcp_client=mcp_client # Pass mcp_client to base
        )
        
        # Define the prompt template for the project manager
        self.pm_prompt = PromptTemplate(
            input_variables=["request", "context", "category", "details"],
            template="""
            You are a PMBOK certified Project Management Professional (PMP) AI assistant.
            Your expertise is in project management best practices, methodologies, and tools.
            
            You can help with:
            - Project planning and scheduling
            - Task breakdown and management
            - Risk assessment and mitigation
            - Resource allocation
            - Stakeholder management
            - Project reporting and documentation
            - Jira integration for task tracking
            
            Context from previous interactions:
            {context}
            
            The user's request is categorized as: {category}
            Additional details: {details}
            
            The original request is:
            {request}
            
            Based on your expertise in PMBOK standards and project management best practices,
            provide a detailed, professional response addressing the request. Include:
            
            1. A brief acknowledgment of the request
            2. Your expert analysis or recommendation
            3. Next steps or action items if applicable
            4. Any relevant PMBOK framework references
            
            Remember to maintain a professional tone and focus on delivering actionable insights.
            """
        )
        
        # Create the chain for project management responses using the newer approach
        self.pm_chain = self.pm_prompt | llm
        
        # For handling Jira integration
        self.jira_enabled = False
        try:
            # Check if Jira credentials are available
            # This would typically come from environment variables
            # and be set up in a real implementation
            self.jira_enabled = False  # For now, assume no Jira integration
        except Exception as e:
            self.logger.warning(f"Jira integration not available: {str(e)}")
    
    def process(self, request: Dict[str, Any]) -> str:
        """
        Process a categorized request to generate a project management response.
        
        Args:
            request: Dictionary containing the parsed request details
            
        Returns:
            str: The project manager's response
        """
        try:
            # Extract information from the request
            if 'original_text' in request:
                original_request = request['original_text']
            elif 'original_request' in request:
                original_request = request['original_request']
            else:
                original_request = str(request)
            
            # Get parsed information if available
            if 'parsed_request' in request:
                parsed_request = request['parsed_request']
                category = parsed_request.get("category", "General Project Inquiry")
                details = parsed_request.get("details", "No specific details provided")
            else:
                category = "General Project Inquiry"
                details = "No specific details provided"
            
            # Get context if available
            context = request.get('context', "No previous context available.")
            
            # Check if this is a Jira-specific request
            is_jira_request = 'jira' in original_request.lower() or 'ticket' in original_request.lower()
            
            # Handle Jira-specific requests if Jira is enabled
            if is_jira_request and self.jira_enabled:
                # This would call a Jira-specific method in a real implementation
                self.logger.info("Processing Jira-specific request")
                # Placeholder for Jira integration
                response = "I can help you with your Jira request, but Jira integration is not fully implemented yet. I can still advise on best practices for Jira usage in project management."
            else:
                # Generate response using the PM chain with invoke instead of run
                response = self.pm_chain.invoke({
                    "request": original_request,
                    "context": context,
                    "category": category,
                    "details": details
                })
            
            # Store this interaction
            self.store_memory({
                "request": original_request,
                "response": response,
                "category": category
            })
            
            return response.strip()
        except Exception as e:
            error_message = f"Error generating PM response: {str(e)}"
            self.logger.error(error_message)
            return f"I apologize, but I encountered an error while processing your request: {str(e)}"
