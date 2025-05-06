#!/usr/bin/env python3
"""
Configuration module for the AI Project Management System.
Handles configuration, environment setup, and patches for SQLite and ChromaDB.
"""

import sys
import os
import logging
from typing import Dict, Any, Optional
from unittest.mock import MagicMock
from dotenv import load_dotenv

# Apply SQLite patch immediately to prevent ChromaDB errors
try:
    __import__('pysqlite3')
    sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
except ImportError:
    print("WARNING: pysqlite3-binary not found, ChromaDB may not work correctly.")
    print("Install with: pip install pysqlite3-binary")

# Configure logging
logging.basicConfig(
    level=os.getenv("LOG_LEVEL", "INFO").upper(),
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s'
)
logger = logging.getLogger("ai_pm_system.config")

# Load environment variables
load_dotenv()

# Constants
DEFAULT_OLLAMA_MODEL = "tinyllama"
DEFAULT_OLLAMA_BASE_URL = "http://host.docker.internal:11434"  # Use Docker host address

# Alternative URLs to try if the default doesn't work
ALTERNATE_OLLAMA_URLS = [
    "http://localhost:11434",
    "http://127.0.0.1:11434", 
    "http://0.0.0.0:11434",
    "http://ollama:11434",  # Docker service name if using Docker Compose
    "http://host.docker.internal:11434"  # Special Docker address to access host
]

PROJECT_NAME = "AI Project Management System"
VERSION = "0.2.0"  # Crew.ai version

def configure_sqlite_patches():
    """
    Configure SQLite patches for compatibility with ChromaDB.
    ChromaDB requires SQLite 3.35.0+, but many systems have older versions.
    This function patches the sqlite3 module using pysqlite3-binary.
    """
    try:
        # Check if patch has already been applied
        if 'pysqlite3' not in sys.modules:
            __import__('pysqlite3')
            sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
            logger.info("Patched sqlite3 with pysqlite3 for compatibility")
        else:
            logger.info("SQLite patch already applied")
    except ImportError:
        logger.warning("pysqlite3 not found, using system sqlite3. ChromaDB may not work correctly.")

def create_chromadb_mock():
    """
    Create a mock for ChromaDB to handle compatibility issues.
    Returns a ChromaDBMock object that can be used as a module replacement.
    
    Returns:
        MagicMock: A mock object for ChromaDB
    """
    class ChromaDBMock:
        def __init__(self):
            self.api = MagicMock()
            self.api.types = MagicMock()
            self.api.types.Documents = MagicMock()
            self.api.types.EmbeddingFunction = MagicMock()
            self.api.types.Embeddings = MagicMock()
            self.api.types.validate_embedding_function = MagicMock(return_value=True)
            
            self.config = MagicMock()
            self.config.Settings = MagicMock()
            
            self.errors = MagicMock()
            self.errors.ChromaError = type('ChromaError', (Exception,), {})
            self.errors.NoDatapointsError = type('NoDatapointsError', (self.errors.ChromaError,), {})
            self.errors.InvalidDimensionException = type('InvalidDimensionException', (self.errors.ChromaError,), {})
            
            # Add any other attributes that might be accessed
            self.Client = MagicMock()
            self.PersistentClient = MagicMock()
            self.Collection = MagicMock()
            self.Documents = self.api.types.Documents
            self.EmbeddingFunction = self.api.types.EmbeddingFunction
            self.Embeddings = self.api.types.Embeddings

    return ChromaDBMock()

def install_chromadb_mock():
    """
    Install the ChromaDB mock as a module replacement.
    This is used when ChromaDB compatibility cannot be guaranteed.
    """
    chromadb_mock = create_chromadb_mock()
    
    # Install the mock
    sys.modules['chromadb'] = chromadb_mock
    sys.modules['chromadb.api'] = chromadb_mock.api
    sys.modules['chromadb.api.types'] = chromadb_mock.api.types
    sys.modules['chromadb.config'] = chromadb_mock.config
    sys.modules['chromadb.errors'] = chromadb_mock.errors
    
    logger.info("Installed ChromaDB mock for compatibility")

def get_ollama_config() -> Dict[str, str]:
    """
    Get the configuration for Ollama.
    
    Returns:
        Dict[str, str]: Dictionary containing Ollama configuration
    """
    model_name = os.getenv("OLLAMA_MODEL", DEFAULT_OLLAMA_MODEL)
    base_url = os.getenv("OLLAMA_BASE_URL", DEFAULT_OLLAMA_BASE_URL)
    
    # System message for Ollama
    system_message = os.getenv(
        "OLLAMA_SYSTEM_MESSAGE", 
        "You are a helpful AI assistant skilled in project management and software development."
    )
    
    # Add the ollama/ prefix to the model name for LiteLLM compatibility
    prefixed_model_name = f"ollama/{model_name}" if not model_name.startswith("ollama/") else model_name
    
    return {
        "model_name": prefixed_model_name,
        "base_url": base_url,
        "system_message": system_message
    }

def check_ollama_connectivity(base_url=None) -> tuple:
    """
    Check if Ollama is available at the given or configured base URL.
    Tries multiple potential URLs if the provided one fails.
    
    Args:
        base_url: Optional URL to check first
        
    Returns:
        tuple: (success (bool), url (str), error_message (str))
    """
    import requests
    from requests.exceptions import RequestException
    
    urls_to_try = []
    
    # Add the provided URL first if given
    if base_url:
        urls_to_try.append(base_url)
    
    # Add default and alternate URLs
    urls_to_try.extend([url for url in [DEFAULT_OLLAMA_BASE_URL] + ALTERNATE_OLLAMA_URLS if url not in urls_to_try])
    
    for url in urls_to_try:
        try:
            response = requests.get(f"{url}/api/tags", timeout=5)
            response.raise_for_status()
            logger.info(f"✓ Successfully connected to Ollama at {url}")
            return True, url, None
        except RequestException as e:
            error = f"Connection failed to {url}: {str(e)}"
            logger.warning(error)
    
    return False, None, f"Failed to connect to Ollama at any of the tried URLs: {', '.join(urls_to_try)}"

def get_mcp_config_path() -> str:
    """
    Get the path to the MCP configuration file.
    
    Returns:
        str: Path to the MCP configuration file
    """
    return os.getenv("MCP_CONFIG_PATH", "mcp.json")

def setup_environment() -> None:
    """
    Set up the environment for the AI Project Management System.
    This includes SQLite patches, ChromaDB mocks, and other configurations.
    """
    # Configure SQLite patches if needed
    if os.getenv("USE_PYSQLITE3", "true").lower() in ["true", "1", "yes"]:
        configure_sqlite_patches()
    
    # Install ChromaDB mock if needed
    if os.getenv("USE_CHROMADB_MOCK", "true").lower() in ["true", "1", "yes"]:
        install_chromadb_mock()
    
    # Force stdout to be unbuffered for immediate display of output
    sys.stdout.reconfigure(write_through=True)  # Python 3.7+
    
    logger.info("Environment setup completed")

def get_agent_config(agent_type: str) -> Dict[str, Any]:
    """
    Get configuration for a specific agent type.
    
    Args:
        agent_type: The type of agent to get configuration for
        
    Returns:
        Dict[str, Any]: Configuration for the agent
    """
    # Base configuration for all agents
    base_config = {
        "verbose": True,
        "allow_delegation": False,
    }
    
    # Specific configurations for different agent types
    agent_configs = {
        "project_manager": {
            "role": "Project Manager",
            "goal": "Manage projects efficiently and coordinate team efforts",
            "backstory": """You are an experienced project manager with PMBOK/PMP certification, 
            proficient in project planning, task management, and requirements analysis. 
            You coordinate team efforts and create project documentation and reports.""",
            "allow_delegation": True,
        },
        "research_specialist": {
            "role": "Research Specialist",
            "goal": "Find and analyze information from various sources and respond creatively to different types of requests",
            "backstory": """You are a versatile research expert and creative content generator who can find and 
            analyze information from various sources, including the web. For research requests, you provide comprehensive 
            reports and can analyze trends, competitors, and industry developments. For creative requests like 
            'tell me a story', you respond with engaging original content that directly addresses what was asked for.
            You're skilled at both analytical research and creative writing, adapting your approach to match what's needed.""",
        },
        "business_analyst": {
            "role": "Business Analyst",
            "goal": "Analyze requirements and create specifications based on project needs",
            "backstory": """You are a skilled business analyst who excels at gathering and 
            analyzing requirements, creating specifications, and helping translate business needs 
            into technical solutions.""",
        },
        "code_developer": {
            "role": "Code Developer",
            "goal": "Write efficient, clean code based on specifications",
            "backstory": """You are a software developer with expertise in multiple programming languages 
            and frameworks. You write clean, efficient code following best practices and can implement 
            features based on specifications.""",
        },
        "code_reviewer": {
            "role": "Code Reviewer",
            "goal": "Review code for quality, security, and best practices",
            "backstory": """You are a senior developer specialized in code review. You evaluate code for 
            quality, security issues, and adherence to best practices, providing constructive feedback 
            for improvements.""",
        },
        "report_drafter": {
            "role": "Report Drafter",
            "goal": "Create clear, comprehensive reports and documentation",
            "backstory": """You are skilled at creating various types of reports and documentation for projects.
            You can structure information clearly and create professional documents that effectively 
            communicate project details.""",
        },
        "report_reviewer": {
            "role": "Report Reviewer",
            "goal": "Review reports for accuracy, clarity, and completeness",
            "backstory": """You are a detail-oriented report reviewer with expertise in technical writing and 
            documentation standards. You ensure reports are accurate, clear, and complete before publication.""",
        },
        "report_publisher": {
            "role": "Report Publisher",
            "goal": "Format and distribute reports to stakeholders",
            "backstory": """You are responsible for the final formatting, packaging, and distribution of 
            reports to various stakeholders. You ensure reports meet organizational standards and reach 
            the intended audience.""",
        }
    }
    
    # Get configuration for the specified agent type, or use empty dict if not found
    agent_specific_config = agent_configs.get(agent_type.lower(), {})
    
    # Combine base and agent-specific configurations
    config = {**base_config, **agent_specific_config}
    
    return config

def get_web_config() -> Dict[str, Any]:
    """
    Get configuration for the web interface.
    
    Returns:
        Dict[str, Any]: Configuration for the web interface
    """
    return {
        "host": os.getenv("WEB_HOST", "0.0.0.0"),
        "port": int(os.getenv("WEB_PORT", "8080")),  # Changed from 8000 to 8080 to avoid conflict with Archon
        "log_level": os.getenv("LOG_LEVEL", "info"),
        "static_dir": "src/web/static",
        "templates_dir": "src/web/templates"
    }
