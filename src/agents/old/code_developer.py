"""
Code Developer Agent for the AI Project Management System.
Writes code based on specifications, potentially using file system or GitHub tools.
"""

from typing import Any, Dict, Optional # Added Optional
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

from src.agents.base_agent import BaseAgent

class CodeDeveloperAgent(BaseAgent):
    """
    Code Developer agent that writes code based on specifications.
    Can potentially use file system tools to write code or GitHub tools for version control.
    """
    
    def __init__(self, llm, mcp_client: Optional[Any] = None): # Added mcp_client
        """
        Initialize the code developer agent.
        
        Args:
            llm: Language model to use for generating responses
            mcp_client: Optional client for interacting with MCP servers.
        """
        super().__init__(
            llm=llm,
            name="Code Developer",
            description="Writes code based on specifications, potentially using file system or GitHub tools.", # Updated description
            mcp_client=mcp_client # Pass mcp_client to base
        )
        
        # Define the prompt template for code development
        self.development_prompt = PromptTemplate(
            input_variables=["request", "context", "specifications"],
            template="""
            You are a Code Developer with expertise in writing clean, efficient code based on specifications.
            Your role is to implement code that meets the given requirements and follows best practices.
            
            Your expertise includes:
            - Software architecture and design patterns
            - Multiple programming languages and frameworks
            - Test-driven development
            - Code optimization and performance
            - Security best practices
            - Documentation
            
            Context from previous interactions:
            {context}
            
            Specifications to implement:
            {specifications}
            
            User's request:
            {request}
            
            Based on these specifications, provide:
            1. Architecture or design approach
            2. Implementation code with necessary documentation
            3. Tests to verify functionality
            4. Installation or setup instructions if relevant
            5. Any considerations, limitations, or future improvements
            
            Make sure your code is complete, well-structured, and follows best practices for readability and maintainability.
            Use appropriate language(s) based on the specifications or what makes most sense for the task.
            """
        )
        
        # Create the chain for development responses
        self.development_chain = LLMChain(llm=llm, prompt=self.development_prompt)
    
    def process(self, request: Dict[str, Any]) -> str:
        """
        Process a request to develop code based on specifications.
        
        Args:
            request: Dictionary containing the request details
            
        Returns:
            str: Developed code and documentation
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
            
            # Get specifications if available, otherwise use the request
            specifications = request.get('specifications', original_request)
            
            # Generate development response
            response = self.development_chain.run(
                request=original_request,
                context=context,
                specifications=specifications
            )
            
            # Store this interaction
            self.store_memory({
                "request": original_request,
                "specifications": specifications,
                "response": response,
                "type": "code_development"
            })
            
            return response.strip()
        except Exception as e:
            error_message = f"Error generating code: {str(e)}"
            self.logger.error(error_message)
            return f"I apologize, but I encountered an error while developing code for your request: {str(e)}"
