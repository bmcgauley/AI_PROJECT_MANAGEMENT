"""
Report Publisher Agent for the AI Project Management System.
Formats and finalizes reports for delivery, potentially using file system or Confluence tools.
"""

from typing import Any, Dict, Optional # Added Optional
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

from src.agents.base_agent import BaseAgent

class ReportPublisherAgent(BaseAgent):
    """
    Report Publisher agent that formats and finalizes reports for delivery.
    Can potentially use file system tools to save reports or Confluence tools to publish them.
    """
    
    def __init__(self, llm, mcp_client: Optional[Any] = None): # Added mcp_client
        """
        Initialize the report publisher agent.
        
        Args:
            llm: Language model to use for generating responses
            mcp_client: Optional client for interacting with MCP servers.
        """
        super().__init__(
            llm=llm,
            name="Report Publisher",
            description="Formats and finalizes reports for delivery, potentially using file system or Confluence tools.", # Updated description
            mcp_client=mcp_client # Pass mcp_client to base
        )
        
        # Define the prompt template for report publishing
        self.publish_prompt = PromptTemplate(
            input_variables=["request", "context", "report", "report_type", "audience"],
            template="""
            You are a Report Publisher with expertise in finalizing and formatting reports for delivery.
            Your role is to ensure reports are presentation-ready, professionally formatted, and tailored to their intended audience.
            
            Your expertise includes:
            - Professional document formatting
            - Executive summary creation
            - Visual presentation enhancement
            - Audience-appropriate communication
            - Consistency in style and branding
            - Final quality assurance
            
            Context from previous interactions:
            {context}
            
            Report type:
            {report_type}
            
            Target audience:
            {audience}
            
            Report to finalize:
            {report}
            
            User's request:
            {request}
            
            Finalize this report by:
            1. Adding any missing essential components (title page, table of contents, etc.)
            2. Creating or refining the executive summary
            3. Ensuring consistent formatting throughout
            4. Adding appropriate visual elements (if described)
            5. Tailoring the language and level of detail for the {audience} audience
            6. Adding distribution notes or confidentiality statements if appropriate
            
            Produce a publication-ready final version of the report that maintains the original content
            while enhancing its presentation and effectiveness for the intended audience.
            """
        )
        
        # Create the chain for publishing responses
        self.publish_chain = LLMChain(llm=llm, prompt=self.publish_prompt)
    
    def process(self, request: Dict[str, Any]) -> str:
        """
        Process a request to finalize and publish a report.
        
        Args:
            request: Dictionary containing the request details
            
        Returns:
            str: Finalized report ready for delivery
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
            
            # Get report to publish - this is required
            report = request.get('report', "")
            if not report:
                return "I need a report to publish. Please provide the report you'd like me to finalize."
            
            # Get report type if available
            report_type = request.get('report_type', "General Report")
            
            # Get target audience if available
            audience = request.get('audience', "General stakeholders")
            
            # Generate publishing response
            response = self.publish_chain.run(
                request=original_request,
                context=context,
                report=report,
                report_type=report_type,
                audience=audience
            )
            
            # Store this interaction
            self.store_memory({
                "request": original_request,
                "report_type": report_type,
                "audience": audience,
                "report_published": report[:100] + "..." if len(report) > 100 else report,
                "response": response,
                "type": "report_publish"
            })
            
            return response.strip()
        except Exception as e:
            error_message = f"Error finalizing report: {str(e)}"
            self.logger.error(error_message)
            return f"I apologize, but I encountered an error while finalizing the report: {str(e)}"
