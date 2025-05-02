#!/usr/bin/env python3
"""
Main entry point for the AI Project Management System.
Sets up the agents and starts the interaction loop with Ollama.
"""

import os
import sys
import asyncio
import logging
import json
from typing import Dict, List, Optional, Union, Any
import traceback

# Force stdout to be unbuffered for immediate display of output
sys.stdout.reconfigure(write_through=True)  # Python 3.7+

from dotenv import load_dotenv
from langchain.callbacks.streaming_stdout import StreamingStdOutCallbackHandler
from langchain_ollama import OllamaLLM

# Fix import path for running directly
if __name__ == "__main__":
    # Ensure the package root is in the path
    project_root = os.path.abspath(os.path.join(os.path.dirname(__file__), '..'))
    if project_root not in sys.path:
        sys.path.insert(0, project_root)

# Now import agents and other modules
from src.agents.chat_coordinator import ChatCoordinatorAgent
from src.agents.project_manager import ProjectManagerAgent
from src.agents.research_specialist import ResearchSpecialistAgent
from src.agents.business_analyst import BusinessAnalystAgent
from src.agents.code_developer import CodeDeveloperAgent
from src.agents.code_reviewer import CodeReviewerAgent
from src.agents.report_drafter import ReportDrafterAgent
from src.agents.report_reviewer import ReportReviewerAgent
from src.agents.report_publisher import ReportPublisherAgent

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(), # Use LOG_LEVEL from .env
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ai_pm_system")


# --- Real MCPClient Implementation ---
class MCPClient:
    """Handles communication with MCP servers defined in a config file via stdio."""
    def __init__(self, config_path="mcp.json"):
        self.config_path = config_path
        self.logger = logging.getLogger("MCPClient")
        self.servers_config = {}
        self.server_processes = {} # Stores asyncio.subprocess.Process objects
        self._load_config()

    def _load_config(self):
        """Loads server configurations from the JSON file."""
        try:
            # Determine absolute path relative to this script's location
            base_dir = os.path.dirname(os.path.abspath(__file__))
            abs_config_path = os.path.join(base_dir, '..', self.config_path) # Assumes mcp.json is in parent dir
            
            self.logger.info(f"Attempting to load MCP config from: {abs_config_path}")
            with open(abs_config_path, 'r') as f:
                config = json.load(f)
            self.servers_config = config.get("mcpServers", {})
            self.logger.info(f"Loaded configuration for servers: {list(self.servers_config.keys())}")
        except FileNotFoundError:
            self.logger.error(f"MCP configuration file not found at {abs_config_path}")
            self.servers_config = {}
        except json.JSONDecodeError:
            self.logger.error(f"Error decoding JSON from {abs_config_path}")
            self.servers_config = {}
        except Exception as e:
            self.logger.error(f"Unexpected error loading MCP config: {e}")
            self.servers_config = {}

    async def start_servers(self):
        """Starts the subprocesses for all configured and enabled servers."""
        self.logger.info("Starting MCP server subprocesses...")
        for name, config in self.servers_config.items():
            if config.get("disabled", False):
                self.logger.info(f"Skipping disabled server: {name}")
                continue
            if config.get("transportType") != "stdio":
                self.logger.warning(f"Skipping server '{name}' with unsupported transport type: {config.get('transportType')}")
                continue

            try:
                command = config.get("command")
                args = config.get("args", [])
                env = {**os.environ, **config.get("env", {})} # Merge OS env with config env

                self.logger.info(f"Starting server '{name}': {command} {' '.join(args)}")
                
                # Create the subprocess
                process = await asyncio.create_subprocess_exec(
                    command,
                    *args,
                    stdin=asyncio.subprocess.PIPE,
                    stdout=asyncio.subprocess.PIPE,
                    stderr=asyncio.subprocess.PIPE, # Capture stderr for debugging
                    env=env,
                    # Set creationflags on Windows to avoid console window pop-ups
                    creationflags=subprocess.CREATE_NO_WINDOW if sys.platform == "win32" else 0
                )
                self.server_processes[name] = {
                    "process": process,
                    "config": config,
                    "lock": asyncio.Lock() # Lock to prevent concurrent writes/reads if needed
                }
                self.logger.info(f"Server '{name}' started successfully (PID: {process.pid}).")
                # Start a task to log stderr for this process
                asyncio.create_task(self._log_stderr(name, process.stderr))

            except FileNotFoundError:
                 self.logger.error(f"Failed to start server '{name}': Command not found '{command}'. Check path.")
            except Exception as e:
                self.logger.error(f"Failed to start server '{name}': {e}")
        self.logger.info("Finished starting MCP server subprocesses.")

    async def _log_stderr(self, server_name: str, stderr: asyncio.StreamReader):
        """Continuously logs stderr output from a server process."""
        while True:
            try:
                line = await stderr.readline()
                if not line:
                    break # EOF
                self.logger.warning(f"[{server_name} stderr]: {line.decode().strip()}")
            except Exception as e:
                self.logger.error(f"Error reading stderr for {server_name}: {e}")
                break
        self.logger.info(f"Stderr logging stopped for {server_name}.")


    async def stop_servers(self):
        """Terminates all running server subprocesses."""
        self.logger.info("Stopping MCP server subprocesses...")
        for name, server_info in self.server_processes.items():
            process = server_info["process"]
            if process.returncode is None: # Check if process is still running
                self.logger.info(f"Terminating server '{name}' (PID: {process.pid})...")
                try:
                    process.terminate()
                    await asyncio.wait_for(process.wait(), timeout=5.0)
                    self.logger.info(f"Server '{name}' terminated.")
                except asyncio.TimeoutError:
                    self.logger.warning(f"Server '{name}' did not terminate gracefully, killing...")
                    process.kill()
                    await process.wait()
                    self.logger.warning(f"Server '{name}' killed.")
                except Exception as e:
                    self.logger.error(f"Error stopping server '{name}': {e}")
        self.server_processes.clear()
        self.logger.info("All MCP server subprocesses stopped.")

    async def use_tool(self, server_name: str, tool_name: str, arguments: Dict[str, Any]) -> Dict[str, Any]:
        """Sends a tool request to the specified server and returns the response."""
        if server_name not in self.server_processes:
            return {"status": "error", "error": {"message": f"Server '{server_name}' not running or configured."}}

        server_info = self.server_processes[server_name]
        process = server_info["process"]
        config = server_info["config"]
        lock = server_info["lock"]
        timeout = config.get("timeout", 60)

        request_payload = {
            "type": "tool_request",
            "tool_name": tool_name,
            "arguments": arguments
        }

        async with lock: # Ensure only one request/response cycle at a time per server
            try:
                self.logger.debug(f"Sending to '{server_name}': {request_payload}")
                process.stdin.write(json.dumps(request_payload).encode() + b'\n')
                await process.stdin.drain()

                # Read response with timeout
                response_line = await asyncio.wait_for(process.stdout.readline(), timeout=timeout)

                if not response_line:
                    self.logger.error(f"Server '{server_name}' closed stdout unexpectedly.")
                    # Attempt to restart or mark as failed? For now, return error.
                    return {"status": "error", "error": {"message": f"Server '{server_name}' connection closed."}}

                response_payload = json.loads(response_line.decode())
                self.logger.debug(f"Received from '{server_name}': {response_payload}")
                return response_payload

            except asyncio.TimeoutError:
                self.logger.error(f"Timeout waiting for response from server '{server_name}' after {timeout}s.")
                # Consider attempting to kill/restart the process here
                return {"status": "error", "error": {"message": f"Timeout waiting for '{server_name}'."}}
            except json.JSONDecodeError:
                self.logger.error(f"Failed to decode JSON response from server '{server_name}'. Line: {response_line.decode()}")
                return {"status": "error", "error": {"message": f"Invalid JSON response from '{server_name}'."}}
            except BrokenPipeError:
                 self.logger.error(f"Broken pipe writing to server '{server_name}'. Process likely crashed.")
                 # Mark server as dead?
                 return {"status": "error", "error": {"message": f"Connection lost to server '{server_name}'."}}
            except Exception as e:
                self.logger.error(f"Error communicating with server '{server_name}': {e}")
                return {"status": "error", "error": {"message": f"Communication error with '{server_name}': {e}"}}

    async def access_resource(self, server_name: str, uri: str) -> Dict[str, Any]:
        """Sends a resource request to the specified server and returns the response."""
        # Similar implementation to use_tool, but with a different request payload
        if server_name not in self.server_processes:
            return {"status": "error", "error": {"message": f"Server '{server_name}' not running or configured."}}

        server_info = self.server_processes[server_name]
        process = server_info["process"]
        config = server_info["config"]
        lock = server_info["lock"]
        timeout = config.get("timeout", 60)

        request_payload = {
            "type": "resource_request",
            "uri": uri
        }

        async with lock:
             try:
                 self.logger.debug(f"Sending resource request to '{server_name}': {request_payload}")
                 process.stdin.write(json.dumps(request_payload).encode() + b'\n')
                 await process.stdin.drain()

                 response_line = await asyncio.wait_for(process.stdout.readline(), timeout=timeout)
                 if not response_line:
                     return {"status": "error", "error": {"message": f"Server '{server_name}' connection closed."}}

                 response_payload = json.loads(response_line.decode())
                 self.logger.debug(f"Received resource response from '{server_name}': {response_payload}")
                 return response_payload
             except asyncio.TimeoutError:
                 return {"status": "error", "error": {"message": f"Timeout waiting for '{server_name}'."}}
             except json.JSONDecodeError:
                 return {"status": "error", "error": {"message": f"Invalid JSON response from '{server_name}'."}}
             except BrokenPipeError:
                  return {"status": "error", "error": {"message": f"Connection lost to server '{server_name}'."}}
             except Exception as e:
                 return {"status": "error", "error": {"message": f"Communication error with '{server_name}': {e}"}}

# --- End Real MCPClient Implementation ---


async def main():
    """
    Main asynchronous entry point for the application.
    Sets up the agents, initializes the real MCP client, starts servers, and runs the interaction loop.
    """
    print("\n======================================================")
    print("   AI Project Management System - Multi-Agent Edition   ")
    print("======================================================\n")

    # Load environment variables from .env file
    load_dotenv(dotenv_path=os.path.join(project_root, 'src', '.env')) # Specify path to .env

    # Get Ollama config from environment variables
    model_name = os.getenv("OLLAMA_MODEL", "mistral")
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")

    print(f"Using Ollama model: {model_name}")
    print(f"Ollama API URL: {base_url}")
    
    # Test Ollama connection before proceeding
    print("Testing connection to Ollama...")
    try:
        import requests
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        if response.status_code == 200:
            print(f"✓ Successfully connected to Ollama at {base_url}")
            models = response.json().get("models", [])
            if models:
                available_models = [model.get("name") for model in models]
                print(f"Available models: {', '.join(available_models)}")
                if model_name not in available_models:
                    print(f"⚠️ Warning: Requested model '{model_name}' not found in available models.")
                    print(f"Will attempt to use it anyway, Ollama may download it on first use.")
        else:
            print(f"⚠️ Ollama server returned status code: {response.status_code}")
            print("Will attempt to continue, but expect possible errors.")
    except Exception as e:
        print(f"⚠️ Could not connect to Ollama: {e}")
        print("Make sure the Ollama service is running at the specified URL.")
        print("Continuing anyway, but expect errors if Ollama isn't available.")
        
    print("\nInitializing MCP Client...")

    # Initialize the real MCP Client
    mcp_client = MCPClient(config_path="mcp.json") # Assumes mcp.json is in project root relative to src/main.py

    # Start MCP server subprocesses
    await mcp_client.start_servers()

    print("Initializing agents...")

    try:
        # Initialize Ollama LLM with improved settings and longer timeouts
        print("Initializing Ollama LLM...")
        llm = OllamaLLM(
            model=model_name,
            callbacks=[StreamingStdOutCallbackHandler()],
            base_url=base_url,
            temperature=0.7,
            request_timeout=120.0,  # Increased from 30 to 120 seconds
            num_retries=3,          # Add retries for resilience
            retry_min_seconds=1,    # Minimum backoff time between retries
            retry_max_seconds=10,   # Maximum backoff time between retries
        )
        logger.info(f"OllamaLLM initialized with model={model_name}, base_url={base_url}")

        # Initialize all specialized agents, passing the llm and the real mcp_client
        print("Creating specialized agents...")
        project_manager = ProjectManagerAgent(llm=llm, mcp_client=mcp_client)
        research_specialist = ResearchSpecialistAgent(llm=llm, mcp_client=mcp_client)
        business_analyst = BusinessAnalystAgent(llm=llm, mcp_client=mcp_client)
        code_developer = CodeDeveloperAgent(llm=llm, mcp_client=mcp_client)
        code_reviewer = CodeReviewerAgent(llm=llm, mcp_client=mcp_client)
        report_drafter = ReportDrafterAgent(llm=llm, mcp_client=mcp_client)
        report_reviewer = ReportReviewerAgent(llm=llm, mcp_client=mcp_client)
        report_publisher = ReportPublisherAgent(llm=llm, mcp_client=mcp_client)

        # Initialize the chat coordinator, passing llm and the real mcp_client
        print("Creating chat coordinator...")
        chat_coordinator = ChatCoordinatorAgent(llm=llm, mcp_client=mcp_client)

        # Add specialized agents to the coordinator
        print("Registering specialized agents with coordinator...")
        chat_coordinator.add_agent("project_manager", project_manager)
        chat_coordinator.add_agent("research_specialist", research_specialist)
        chat_coordinator.add_agent("business_analyst", business_analyst)
        chat_coordinator.add_agent("code_developer", code_developer)
        chat_coordinator.add_agent("code_reviewer", code_reviewer)
        chat_coordinator.add_agent("report_drafter", report_drafter)
        chat_coordinator.add_agent("report_reviewer", report_reviewer)
        chat_coordinator.add_agent("report_publisher", report_publisher)

        print("\nAll agents initialized successfully!")
        print("\n------------------------------------------------------")
        print("Welcome to the AI Project Management System!")
        print("You can ask for help with project management, research,")
        print("requirements analysis, coding, and documentation.")
        print("Type 'exit' to quit the application.")
        print("------------------------------------------------------\n")

        # Test Ollama is working correctly before starting the chat loop
        print("Testing LLM with a simple request...")
        try:
            test_prompt = "Say hello in one word."
            test_response = await asyncio.wait_for(
                llm.ainvoke(test_prompt),
                timeout=10.0
            )
            print(f"✓ LLM test successful: {test_response.strip()}")
        except Exception as e:
            print(f"⚠️ LLM test failed: {e}")
            print("Continuing despite the test failure, but expect issues with agent responses.")

        # Start interaction loop
        conversation_history = []
        while True:
            # Get user input asynchronously to avoid blocking
            try:
                user_input = await asyncio.to_thread(input, "\nYou: ")
            except RuntimeError as e:
                # Fallback for environments where asyncio.to_thread might not work well with input
                print("Async input failed, using synchronous input. Note: This might block.")
                user_input = input("\nYou: ")

            if user_input.lower() in ['exit', 'quit', 'bye']:
                print("\nThank you for using the AI Project Management System. Goodbye!")
                break

            # Add user input to conversation history
            conversation_history.append({"role": "user", "content": user_input})

            print("\nProcessing...")

            # Process the request using the chat coordinator asynchronously
            print("\nSending request to Chat Coordinator...")
            try:
                # First try direct communication with LLM to check if it's responding
                print("Testing direct LLM communication...")
                test_result = await asyncio.wait_for(
                    llm.ainvoke("Briefly acknowledge you received this test message."),
                    timeout=10.0
                )
                print(f"✓ LLM direct communication working: {test_result.strip()}")
                
                # Now process the actual request with a longer timeout
                response = await asyncio.wait_for(
                    chat_coordinator.process({"text": user_input}),
                    timeout=60  # Add a 60-second timeout
                )
                print("Response received from Chat Coordinator")
            except asyncio.TimeoutError:
                print("\n⚠️ Request processing timed out. This could be due to:")
                print("1. Ollama service is overloaded or not responding")
                print("2. The model is taking too long to generate a response")
                print("3. There might be an issue with the agent's processing logic")
                print("\nTry a simpler request or restart the application.")
                response = {"response": "Request timed out. The LLM service (Ollama) is taking too long to respond."}
            except Exception as e:
                print(f"\n❌ Error processing request: {e}")
                print(f"Error details: {traceback.format_exc()}")
                response = {"response": f"Error processing request: {e}"}

            # Extract the response text
            if isinstance(response, dict) and "response" in response:
                response_text = response["response"]

                # Handle clarification questions
                if response.get("status") == "clarification_needed" and "clarification_questions" in response:
                    response_text += "\n\nI need some clarification:"
                    for i, question in enumerate(response["clarification_questions"]):
                        response_text += f"\n{i+1}. {question}"

                # Add metadata about which agent processed the request
                if "processed_by" in response:
                    agent_name = response["processed_by"].replace("_", " ").title()
                    print(f"\n[{agent_name}]: {response_text}")
                else:
                    print(f"\nSystem: {response_text}")

                # Add response to conversation history
                conversation_history.append({"role": "assistant", "content": response_text})
            else:
                # Fallback if response is not in expected format
                print(f"\nSystem: {response}")
                conversation_history.append({"role": "assistant", "content": str(response)})

    except Exception as e:
        logger.exception(f"Critical error in main application loop: {e}") # Use logger.exception for stack trace
        print(f"\nCritical error: {e}")
        print("Attempting to shut down gracefully...")
    finally:
        # Ensure servers are stopped even if an error occurs
        if 'mcp_client' in locals() and isinstance(mcp_client, MCPClient):
            await mcp_client.stop_servers()


if __name__ == "__main__":
    loop = asyncio.get_event_loop()
    try:
        loop.run_until_complete(main())
    except KeyboardInterrupt:
        print("\nCtrl+C received. Shutting down...")
        # Handle shutdown tasks if needed, MCPClient.stop_servers() is called in finally block
    finally:
        # Additional cleanup if necessary
        print("Exiting application.")
        # Ensure all tasks are cancelled before closing loop (important for graceful shutdown)
        tasks = [t for t in asyncio.all_tasks() if t is not asyncio.current_task()]
        for task in tasks:
            task.cancel()
        # Allow tasks to finish cancelling
        loop.run_until_complete(asyncio.gather(*tasks, return_exceptions=True))
        loop.close()
