"""
Business Analyst Agent for the AI Project Management System.
Analyzes requirements and creates specifications, potentially using file system tools.
"""

from typing import Any, Dict, Optional # Added Optional
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

from src.agents.base_agent import BaseAgent

class BusinessAnalystAgent(BaseAgent):
    """
    Business Analyst agent that analyzes requirements and creates specifications.
    Can potentially use file system tools to read existing documentation.
    """
    
    def __init__(self, llm, mcp_client: Optional[Any] = None): # Added mcp_client
        """
        Initialize the business analyst agent.
        
        Args:
            llm: Language model to use for generating responses
            mcp_client: Optional client for interacting with MCP servers.
        """
        super().__init__(
            llm=llm,
            name="Business Analyst",
            description="Analyzes requirements and creates specifications, potentially using file system tools.", # Updated description
            mcp_client=mcp_client # Pass mcp_client to base
        )
        
        # Define the prompt template for requirements analysis
        self.analysis_prompt = PromptTemplate(
            input_variables=["request", "context"],
            template="""
            You are a Business Analyst with expertise in analyzing requirements and creating specifications.
            Your role is to translate business needs into clear, actionable specifications for development.
            
            Your expertise includes:
            - Requirements gathering and analysis
            - User story creation
            - Functional and non-functional requirements
            - Creating detailed specifications
            - Process mapping and documentation
            - Data flow analysis
            - Stakeholder communication
            
            Context from previous interactions:
            {context}
            
            User's request:
            {request}
            
            Analyze this request and provide:
            1. Clarified business requirements
            2. User stories or use cases
            3. Functional requirements
            4. Non-functional requirements (performance, security, etc.)
            5. Acceptance criteria
            6. Dependencies and constraints
            7. Data requirements
            
            Format your analysis as a professional business requirements document.
            """
        )
        
        # Create the chain for analysis responses
        self.analysis_chain = LLMChain(llm=llm, prompt=self.analysis_prompt)
    
    def process(self, request: Dict[str, Any]) -> str:
        """
        Process a request to analyze requirements and create specifications.
        
        Args:
            request: Dictionary containing the request details
            
        Returns:
            str: Requirements analysis and specifications
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
            
            # Generate analysis response
            response = self.analysis_chain.run(
                request=original_request,
                context=context
            )
            
            # Store this interaction
            self.store_memory({
                "request": original_request,
                "response": response,
                "type": "requirements_analysis"
            })
            
            return response.strip()
        except Exception as e:
            error_message = f"Error generating requirements analysis: {str(e)}"
            self.logger.error(error_message)
            return f"I apologize, but I encountered an error while analyzing your requirements: {str(e)}"
