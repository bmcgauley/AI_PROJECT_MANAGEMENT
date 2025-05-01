from typing import Any, Dict, Optional # Added Optional
from langchain.prompts import PromptTemplate
from langchain_core.runnables import RunnablePassthrough

class RequestParserAgent:
    """
    Agent responsible for parsing and categorizing user requests.
    Determines if a request is related to project management and what category it falls into.
    """
    
    def __init__(self, llm, mcp_client: Optional[Any] = None): # Added mcp_client
        """
        Initialize the request parser agent.
        
        Args:
            llm: Language model to use for parsing
            mcp_client: Optional client for interacting with MCP servers (currently unused by this agent).
        """
        self.llm = llm
        self.mcp_client = mcp_client # Store mcp_client even if unused
        
        # Define the prompt template for parsing requests
        self.parser_prompt = PromptTemplate(
            input_variables=["request"],
            template="""
            You are a request classifier for a project management system. Your job is to determine:
            1. If the request is related to project management
            2. What category of project management the request falls into
            
            Categories include:
            - Task Management (creating, updating tasks)
            - Sprint Planning
            - Reporting (RAID logs, SOAP, project charters)
            - Resource Allocation
            - Risk Management
            - Stakeholder Communication
            - Code Review (if related to project quality management)
            - Testing (if related to project quality management)
            - Deployment (if related to project implementation)
            - General Project Inquiry
            
            For the following request:
            
            {request}
            
            Provide your analysis as valid JSON with the following structure:
            {{
                "relevant": true/false,
                "category": "category_name",
                "details": "brief explanation of why you categorized it this way",
                "priority": "high/medium/low"
            }}
            
            Only return the JSON, nothing else.
            """
        )
        
        # Create the runnable chain for parsing using the newer approach
        self.parser_chain = (
            {"request": RunnablePassthrough()} 
            | self.parser_prompt 
            | llm
        )
    
    def process(self, request):
        """
        Process a user request to determine if it's project management related and categorize it.
        
        Args:
            request: The user's request text
            
        Returns:
            dict: Parsed information about the request
        """
        try:
            # Get the raw response from the LLM using invoke instead of run
            response = self.parser_chain.invoke(request)
            
            # Clean up and parse the response
            import json
            try:
                # Try to parse the JSON response
                cleaned_response = response.strip()
                # Handle potential triple backticks in the output
                if cleaned_response.startswith("```json"):
                    cleaned_response = cleaned_response[7:]
                if cleaned_response.endswith("```"):
                    cleaned_response = cleaned_response[:-3]
                
                parsed_response = json.loads(cleaned_response.strip())
                
                return parsed_response
            except json.JSONDecodeError:
                print(f"Failed to parse JSON response: {response}")
                # Return a default response if JSON parsing fails
                return {
                    "relevant": True,
                    "category": "General Project Inquiry",
                    "details": "Failed to parse the response but treating as a general inquiry",
                    "priority": "medium"
                }
            
        except Exception as e:
            print(f"Error parsing request: {str(e)}")
            # Return a default response in case of error
            return {
                "relevant": False,
                "category": "Unknown",
                "details": f"Error parsing request: {str(e)}",
                "priority": "low"
            }
