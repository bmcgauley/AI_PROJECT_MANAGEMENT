"""
Report Reviewer Agent for the AI Project Management System.
Reviews and refines reports, potentially using file system or Confluence tools.
"""

from typing import Any, Dict, Optional # Added Optional
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

from src.agents.base_agent import BaseAgent

class ReportReviewerAgent(BaseAgent):
    """
    Report Reviewer agent that reviews and refines reports.
    Can potentially use file system tools to read reports or Confluence tools to fetch content.
    """
    
    def __init__(self, llm, mcp_client: Optional[Any] = None): # Added mcp_client
        """
        Initialize the report reviewer agent.
        
        Args:
            llm: Language model to use for generating responses
            mcp_client: Optional client for interacting with MCP servers.
        """
        super().__init__(
            llm=llm,
            name="Report Reviewer",
            description="Reviews and refines reports, potentially using file system or Confluence tools.", # Updated description
            mcp_client=mcp_client # Pass mcp_client to base
        )
        
        # Define the prompt template for report review
        self.review_prompt = PromptTemplate(
            input_variables=["request", "context", "report", "report_type"],
            template="""
            You are a Report Reviewer with expertise in evaluating and improving project documentation.
            Your role is to ensure reports are clear, accurate, professional, and fulfill their intended purpose.
            
            Your expertise includes:
            - Professional writing and editing
            - Technical accuracy review
            - Clarity and readability assessment
            - Completeness and comprehensiveness evaluation
            - Formatting and presentation standards
            - Stakeholder communication effectiveness
            
            Context from previous interactions:
            {context}
            
            Report type:
            {report_type}
            
            Report to review:
            {report}
            
            User's request:
            {request}
            
            Provide a comprehensive review including:
            1. Overall assessment of the report quality
            2. Strengths of the report
            3. Areas for improvement, categorized by:
               - Content issues (missing information, inaccuracies)
               - Structure issues (organization, flow)
               - Language issues (clarity, tone, grammar)
               - Formatting issues (presentation, readability)
            4. Specific suggestions for improvement with examples
            5. Revised sections where appropriate
            
            Be constructive and specific in your feedback, with the goal of enhancing the report's effectiveness.
            """
        )
        
        # Create the chain for review responses
        self.review_chain = LLMChain(llm=llm, prompt=self.review_prompt)
    
    def process(self, request: Dict[str, Any]) -> str:
        """
        Process a request to review a report.
        
        Args:
            request: Dictionary containing the request details
            
        Returns:
            str: Report review and refinement suggestions
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
            
            # Get report to review - this is required
            report = request.get('report', "")
            if not report:
                return "I need a report to review. Please provide the report you'd like me to evaluate."
            
            # Get report type if available
            report_type = request.get('report_type', "General Report")
            
            # Generate review response
            response = self.review_chain.run(
                request=original_request,
                context=context,
                report=report,
                report_type=report_type
            )
            
            # Store this interaction
            self.store_memory({
                "request": original_request,
                "report_type": report_type,
                "report_reviewed": report[:100] + "..." if len(report) > 100 else report,
                "response": response,
                "type": "report_review"
            })
            
            return response.strip()
        except Exception as e:
            error_message = f"Error generating report review: {str(e)}"
            self.logger.error(error_message)
            return f"I apologize, but I encountered an error while reviewing the report: {str(e)}"
