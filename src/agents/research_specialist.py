"""
Research Specialist Agent for the AI Project Management System.
Gathers information and best practices for project requirements.
"""

from typing import Any, Dict
from typing import Any, Dict
from typing import Any, Dict, Optional # Added Optional
from langchain.prompts import PromptTemplate
from langchain.chains import LLMChain

from src.agents.base_agent import BaseAgent

class ResearchSpecialistAgent(BaseAgent):
    """
    Research Specialist agent that gathers information and best practices
    for project requirements, potentially using web search tools.
    """
    
    def __init__(self, llm, mcp_client: Optional[Any] = None): # Added mcp_client
        """
        Initialize the research specialist agent.
        
        Args:
            llm: Language model to use for generating responses
            mcp_client: Optional client for interacting with MCP servers.
        """
        super().__init__(
            llm=llm,
            name="Research Specialist",
            description="Gathers information and best practices for project requirements, can use web search tools.", # Updated description
            mcp_client=mcp_client # Pass mcp_client to base
        )
        
        # Define the prompt template for research
        self.research_prompt = PromptTemplate(
            input_variables=["request", "context", "search_results"],
            template="""
            You are a Research Specialist AI agent. Your goal is to provide comprehensive research findings based on user requests.
            You have access to a web search tool ('brave_web_search') via an MCP client.
            
            **Instructions:**
            1. Analyze the user's request: {request}
            2. Review the conversation context: {context}
            3. **Decide if a web search is necessary.** Perform a search if the request involves:
                - Recent events or information (past ~1 year).
                - Highly specific technical details or library documentation.
                - Information about current market trends or competitor analysis.
                - Topics outside of general knowledge expected from a large language model.
            4. **If a search was performed**, use the provided search results below to inform your response:
               {search_results}
            5. **If no search was performed**, state that and rely on your internal knowledge.
            6. Synthesize the information (from internal knowledge and/or search results) into a structured report.
            
            **Report Structure:**
            - **Summary:** Briefly summarize the key findings.
            - **Best Practices/Standards:** Detail relevant industry best practices or standards.
            - **Challenges & Solutions:** Outline common challenges and potential solutions.
            - **Helpful Resources:** List any relevant resources (articles, tools, websites). Mention if these came from search results.
            - **Recommendations:** Suggest next steps or further investigation if needed.

            **Your Expertise Includes:**
            - Project management methodologies (Agile, Scrum, Waterfall, etc.)
            - Industry-specific best practices
            - Regulatory and compliance requirements
            - Technical standards and specifications
            - Market trends and competitive analysis
            
            Context from previous interactions:
            {context}

            Web search results (if available):
            {search_results}
            
            User's request:
            {request}
            
            Based on the user's request and any provided web search results, provide comprehensive research findings. Include:
            1. Summary of key findings (incorporating search results if provided).
            2. Industry best practices and standards related to the request.
            3. Common challenges and how to address them.
            4. Resources that might be helpful.
            5. Recommendations for further investigation if needed
            
            Present your findings in a clear, organized manner with section headings.
            """
        )
        
        # Create the chain for research responses
        self.research_chain = LLMChain(llm=llm, prompt=self.research_prompt)

    async def process(self, request: Dict[str, Any]) -> str: # Changed to async def
        """
        Process a request to research information and best practices.
        Potentially uses the brave_web_search tool via MCP client.
        
        Args:
            request: Dictionary containing the request details
            
        Returns:
            str: Research findings and recommendations
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

            search_results_text = "No web search performed or MCP client not available."
            search_performed = False

            # --- Use MCP Client for Web Search ---
            if self.mcp_client:
                self.logger.info(f"Attempting web search for: {original_request[:50]}...")
                try:
                    # Use the placeholder MCP client to simulate a search
                    search_response = await self.mcp_client.use_tool(
                        server_name="brave-search",
                        tool_name="brave_web_search",
                        arguments={"query": original_request}
                    )
                    
                    if search_response.get("status") == "success" and "result" in search_response:
                        results = search_response["result"].get("results", [])
                        if results:
                            formatted_results = []
                            for i, res in enumerate(results):
                                formatted_results.append(f"{i+1}. Title: {res.get('title', 'N/A')}")
                                formatted_results.append(f"   URL: {res.get('url', 'N/A')}")
                                formatted_results.append(f"   Description: {res.get('description', 'N/A')}\n")
                            search_results_text = "Web Search Results:\n" + "\n".join(formatted_results)
                            search_performed = True
                            self.logger.info(f"Successfully simulated web search, found {len(results)} results.")
                        else:
                            search_results_text = "Web search performed, but no results found."
                            self.logger.info("Simulated web search returned no results.")
                    else:
                        error_msg = search_response.get("error", {}).get("message", "Unknown error")
                        search_results_text = f"Web search failed: {error_msg}"
                        self.logger.error(f"Simulated web search failed: {error_msg}")
                        
                except Exception as tool_error:
                    self.logger.error(f"Error calling MCP tool: {str(tool_error)}")
                    search_results_text = f"Error occurred during web search attempt: {str(tool_error)}"
            # --- End MCP Client Usage ---

            # Generate research response using the chain, including search results
            # Use invoke for async compatibility with Langchain runnables
            response = await self.research_chain.ainvoke({ # Changed to await ainvoke
                "request": original_request,
                "context": context,
                "search_results": search_results_text
            })
            
            # Extract the actual response text if using invoke which returns a dict/object
            response_text = response if isinstance(response, str) else response.get('text', str(response))

            # Store this interaction
            self.store_memory({
                "request": original_request,
                "search_performed": search_performed,
                "search_results_summary": search_results_text[:200] + "..." if len(search_results_text) > 200 else search_results_text,
                "response": response_text
            })

            return response_text.strip()
        except Exception as e:
            error_message = f"Error generating research response: {str(e)}"
            self.logger.error(error_message)
            return f"I apologize, but I encountered an error while researching your request: {str(e)}"
