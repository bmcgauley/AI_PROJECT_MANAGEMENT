"""
Report Drafter Agent for the AI Project Management System.
Creates project documentation and reports, potentially using file system or Confluence tools.
"""

from typing import Any, Dict, Optional # Added Optional
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

from src.agents.base_agent import BaseAgent

class ReportDrafterAgent(BaseAgent):
    """
    Report Drafter agent that creates project documentation and reports.
    Can potentially use file system tools to save reports or Confluence tools to create pages.
    """
    
    def __init__(self, llm, mcp_client: Optional[Any] = None): # Added mcp_client
        """
        Initialize the report drafter agent.
        
        Args:
            llm: Language model to use for generating responses
            mcp_client: Optional client for interacting with MCP servers.
        """
        super().__init__(
            llm=llm,
            name="Report Drafter",
            description="Creates project documentation and reports, potentially using file system or Confluence tools.", # Updated description
            mcp_client=mcp_client # Pass mcp_client to base
        )
        
        # Define the prompt template for report drafting
        self.report_prompt = PromptTemplate(
            input_variables=["request", "context", "report_type", "content"],
            template="""
            You are a Report Drafter with expertise in creating professional project documentation and reports.
            Your role is to produce clear, comprehensive, and well-structured documentation for project management.
            
            Your expertise includes:
            - Project charter creation
            - Requirements documentation
            - Technical specifications
            - Status reports
            - Risk assessment reports
            - Project closure reports
            - Executive summaries
            - Meeting minutes and action items
            
            Context from previous interactions:
            {context}
            
            Report type to create:
            {report_type}
            
            Content to include:
            {content}
            
            User's request:
            {request}
            
            Create a professional, well-structured {report_type} that includes:
            1. Appropriate title and headings
            2. Executive summary if appropriate
            3. Main content organized in logical sections
            4. Necessary supporting information
            5. Conclusions or next steps if applicable
            
            Format the report appropriately for its type and ensure it's professional, clear, and actionable.
            Use appropriate formatting, including headers, bullet points, and sections to improve readability.
            """
        )
        
        # Create the chain for report responses
        self.report_chain = LLMChain(llm=llm, prompt=self.report_prompt)
    
    def process(self, request: Dict[str, Any]) -> str:
        """
        Process a request to draft a report or documentation.
        
        Args:
            request: Dictionary containing the request details
            
        Returns:
            str: Drafted report or documentation
        """
        try:
            # Extract information from the request
            if 'original_text' in request:
                original_request = request['original_text']
            elif 'original_request' in request:
                original_request = request['original_request']
            else:
                original_request = str(request)
            
            # Get context if available
            context = request.get('context', "No previous context available.")
            
            # Get report type if available, otherwise infer from request
            report_type = request.get('report_type', "General Report")
            
            # Get content to include if available
            content = request.get('content', "No specific content provided.")
            
            # Generate report
            response = self.report_chain.run(
                request=original_request,
                context=context,
                report_type=report_type,
                content=content
            )
            
            # Store this interaction
            self.store_memory({
                "request": original_request,
                "report_type": report_type,
                "response": response,
                "type": "report_draft"
            })
            
            return response.strip()
        except Exception as e:
            error_message = f"Error generating report: {str(e)}"
            self.logger.error(error_message)
            return f"I apologize, but I encountered an error while drafting the report: {str(e)}"
