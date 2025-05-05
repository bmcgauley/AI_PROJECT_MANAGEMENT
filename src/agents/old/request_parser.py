"""
Request Parser Agent for the AI Project Management System.
Responsible for categorizing and extracting key information from user requests.
"""

from typing import Dict, Any, Optional
import json
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough, RunnableParallel

class RequestParserAgent:
    """
    Agent responsible for parsing and categorizing user requests.
    Determines request category and extracts key information.
    """
    
    def __init__(self, llm, mcp_client: Optional[Any] = None):
        """
        Initialize the Request Parser agent.
        
        Args:
            llm: Language model to use for parsing
            mcp_client: Optional MCP client for tool access
        """
        self.llm = llm
        self.mcp_client = mcp_client
        
        # Define categories aligned with agent specialties
        self.categories = [
            "Project Planning",     # Project Manager
            "Research",            # Research Specialist
            "Requirements",        # Business Analyst
            "Development",         # Code Developer
            "Code Review",         # Code Reviewer
            "Documentation",       # Report Drafter
            "Review",             # Report Reviewer
            "Publishing",         # Report Publisher
            "General Inquiry"      # Fallback
        ]
        
        # Create parser prompt
        self.parser_prompt = PromptTemplate(
            input_variables=["request", "categories"],
            template="""You are a request parser for an AI Project Management System.
            
            Categories available:
            {categories}
            
            For this request:
            {request}
            
            Respond with ONLY a valid JSON object in this format:
            {{
                "category": "<most relevant category>",
                "details": "<why you chose this category>",
                "priority": "<high|medium|low>",
                "identified_tasks": ["<task1>", "<task2>"]
            }}"""
        )
        
        # Create the chain for request parsing using RunnableParallel
        self.parser_chain = RunnableParallel(
            input_formatter=RunnablePassthrough(),
            context_builder=lambda x: {
                "request": x,
                "categories": "\n".join(self.categories)
            }
        ) | self.parser_prompt | llm

    def process(self, request: str) -> Dict[str, Any]:
        """
        Process and categorize a user request.
        
        Args:
            request: The user's request text
            
        Returns:
            Dictionary with parsed request details
        """
        try:
            # Get parser response
            response = self.parser_chain.invoke(request)
            
            # Clean and parse JSON response
            try:
                if isinstance(response, dict):
                    parsed = response
                else:
                    # Extract JSON if wrapped in code blocks
                    response_text = response
                    if "```json" in response_text:
                        response_text = response_text.split("```json")[1].split("```")[0]
                    elif "```" in response_text:
                        response_text = response_text.split("```")[1].split("```")[0]
                    
                    parsed = json.loads(response_text.strip())
                
            except (json.JSONDecodeError, IndexError, AttributeError):
                # Fallback to default parsing
                parsed = {
                    "category": "General Inquiry",
                    "details": "Failed to parse specific category",
                    "priority": "medium",
                    "identified_tasks": []
                }
            
            return parsed
            
        except Exception as e:
            # Return safe fallback on error
            return {
                "category": "General Inquiry",
                "details": f"Error during parsing: {str(e)}",
                "priority": "medium",
                "identified_tasks": []
            }
