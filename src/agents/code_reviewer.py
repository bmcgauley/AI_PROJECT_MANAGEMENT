"""
Code Reviewer Agent for the AI Project Management System.
Reviews and suggests improvements to code, potentially using file system or GitHub tools.
"""

from typing import Any, Dict, Optional # Added Optional
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

from src.agents.base_agent import BaseAgent

class CodeReviewerAgent(BaseAgent):
    """
    Code Reviewer agent that reviews and suggests improvements to code.
    Can potentially use file system tools to read code or GitHub tools to fetch code/post reviews.
    """
    
    def __init__(self, llm, mcp_client: Optional[Any] = None): # Added mcp_client
        """
        Initialize the code reviewer agent.
        
        Args:
            llm: Language model to use for generating responses
            mcp_client: Optional client for interacting with MCP servers.
        """
        super().__init__(
            llm=llm,
            name="Code Reviewer",
            description="Reviews and suggests improvements to code, potentially using file system or GitHub tools.", # Updated description
            mcp_client=mcp_client # Pass mcp_client to base
        )
        
        # Define the prompt template for code review
        self.review_prompt = PromptTemplate(
            input_variables=["request", "context", "code", "specifications"],
            template="""
            You are a Code Reviewer with expertise in evaluating code quality and suggesting improvements.
            Your role is to provide constructive feedback on code to ensure it meets requirements,
            follows best practices, and is maintainable.
            
            Your expertise includes:
            - Code quality and readability
            - Performance optimization
            - Security vulnerabilities
            - Adherence to design patterns and principles
            - Test coverage and quality
            - Documentation completeness
            
            Context from previous interactions:
            {context}
            
            Original specifications:
            {specifications}
            
            Code to review:
            {code}
            
            User's request:
            {request}
            
            Provide a comprehensive code review including:
            1. Summary of the code quality
            2. Strengths and positive aspects
            3. Issues and concerns (categorized by severity)
              - Critical: Must be fixed immediately
              - Important: Should be addressed before production
              - Minor: Style or best practice improvements
            4. Specific recommendations with examples
            5. Overall assessment of whether the code meets the specifications
            
            Be specific and constructive in your feedback, focusing on helping the developer improve the code.
            Provide code examples for suggested improvements where appropriate.
            """
        )
        
        # Create the chain for review responses
        self.review_chain = LLMChain(llm=llm, prompt=self.review_prompt)
    
    def process(self, request: Dict[str, Any]) -> str:
        """
        Process a request to review code.
        
        Args:
            request: Dictionary containing the request details
            
        Returns:
            str: Code review and recommendations
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
            
            # Get code to review - this is required
            code = request.get('code', "")
            if not code:
                return "I need code to review. Please provide the code you'd like me to evaluate."
            
            # Get specifications if available
            specifications = request.get('specifications', "No specific requirements provided.")
            
            # Generate review response
            response = self.review_chain.run(
                request=original_request,
                context=context,
                code=code,
                specifications=specifications
            )
            
            # Store this interaction
            self.store_memory({
                "request": original_request,
                "code_reviewed": code[:100] + "..." if len(code) > 100 else code,
                "response": response,
                "type": "code_review"
            })
            
            return response.strip()
        except Exception as e:
            error_message = f"Error generating code review: {str(e)}"
            self.logger.error(error_message)
            return f"I apologize, but I encountered an error while reviewing the code: {str(e)}"
