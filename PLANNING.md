# AI Project Management System - Planning Document

## Project Overview
The AI Project Management System is a multi-agent system designed to handle project management tasks using AI agents. The system uses LangChain for agent orchestration and communication.

## Architecture

### Core Components
1. **Agent System**
   - Using LangChain for agent orchestration
   - Multiple specialized agents for different tasks
   - Real-time agent communication and thought streaming

2. **Web Interface**
   - FastAPI backend
   - WebSocket-based real-time updates
   - "Under the Hood" view for agent thought processes

3. **MCP Integration**
   - Multiple MCP servers for different functionalities
   - Includes filesystem, context7, and Atlassian integration

## Technology Stack

### Core Technologies
- Python 3.12+
- LangChain (for agent orchestration)
- FastAPI (web framework)
- Ollama (local LLM)
- Docker (for MCP servers)

### Key Libraries
- langchain>=0.0.0
- fastapi>=0.103.1
- pydantic>=2.5.0
- websockets>=11.0.3
- langchain_ollama (for LLM integration)
- pysqlite3-binary (for SQLite compatibility)

### Dependency Management

#### SQLite Compatibility
- ChromaDB requires SQLite 3.35.0+
- Systems with older SQLite are handled using pysqlite3-binary package
- Module patching: sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')

#### ChromaDB Integration
- Mocking ChromaDB in case of compatibility issues
- Using environment variables to configure ChromaDB to use alternate databases
- DuckDB option as alternative to SQLite when necessary

## Code Style & Standards

### Python Code Style
- Follow PEP 8 guidelines
- Use type hints
- Format code with black
- Maximum file length: 500 lines
- Docstrings: Google style

### Project Structure
```
src/
├── agents/          # Individual agent implementations
├── mcp_servers/     # MCP server implementations
└── web/            # Web interface components
    ├── static/     # Static assets
    └── templates/  # HTML templates

tests/              # Test files mirroring src structure
```

## Development Workflow
1. Feature branches for new development
2. Unit tests required for all new features
3. Code review required before merging
4. Update documentation with changes

## Migration Plan (LangChain to Crew.ai)
1. Implement parallel system using LangChain
2. Test new implementation thoroughly
3. Gradually transition features
4. Validate improvements in:
   - JSON parsing reliability
   - Agent thought streaming
   - Inter-agent communication

### Migration Challenges
1. **Dependency Compatibility**:
   - SQLite version requirements for ChromaDB
   - LiteLLM configuration for Ollama models
   - Pydantic version compatibility across dependencies

2. **Workarounds Implemented**:
   - SQLite patching with pysqlite3-binary
   - ChromaDB module mocking
   - LLM provider configuration adjustments

## Future Improvements
1. Enhanced agent coordination patterns
2. Improved error recovery
3. Better thought streaming visualization
4. Extended MCP server capabilities
5. Automated dependency compatibility handling

## Performance Goals
1. Reliable JSON parsing
2. Real-time agent thought updates
3. Seamless agent coordination
4. Quick response times

## System Startup Procedure
1. Start Ollama service first (ensures model is loaded)
2. Initialize required MCP servers
3. Start AI Project Management system with proper environment
4. Validate all components are running correctly

## Security Considerations
1. Secure API token handling
2. Proper environment variable usage
3. Docker container security
4. Input validation

## Monitoring & Maintenance
1. Agent state monitoring
2. System health checks
3. Error logging and tracking
4. Performance metrics collection
5. Dependency compatibility monitoring


######### Guide
To build this multi-agent system, we'll design each agent using the pydantic library and langchain or any similar framework for implementing NLP-based functionalities such as conversational bots, task management, and information gathering.

1. Chat Coordinator
Main Interface: Acts as a gateway between different agents and handles user requests.
Orchestrates Communication: Manages the flow of interactions between agents based on their functions (e.g., ProjectManager, Research Specialist, etc.).
2. Project Manager
PMBOK/PMP Certified Agent: Provides project planning, task management (using lark_parser or similar for grammar-driven parsing), and integration with Jira.
Task Management: Manages tasks within projects using a tracking system.
3. Research Specialist
Gathers Information and Best Practices: Invokes external information sources through APIs, such as web scraping and GitHub searches.
4. Business Analyst
Analyzes Requirements and Creates Specifications: Interprets user requests to create detailed project specifications.
Documentation: Generates technical documentation for the project.
5. Code Developer
Writes Code Based on Specifications: Code generation by using templates or other tools like Django or Flask.
Code Reviewer: Provides reviews and suggests improvements to code.
6. Code Reviewer
Reviews and Suggests Improvements to Code: Evaluates the quality of existing code, suggesting changes for better structure or performance.
Collaboration: Facilitates collaboration between code developer and project manager.
7. Report Drafter
Creates Project Documents and Reports: Drafts comprehensive documents using templates from external sources (like Jinja2).
Revision: Refines the generated documentation for clarity and consistency.
8. Report Reviewer
Reviews and Refines Reports: Evaluates the quality of project reports, providing feedback to improve overall content.
Integration: Integrates with other agents for final formatting and distribution.
9. Report Publisher
Formats and Finalizes Reports for Delivery: Presents the finalized project reports in a format suitable for delivery.
Delivery: Outputs the report to a specified location or format (such as PDF or HTML).
Implementation Strategy
Agent Classes:

ChatCoordinator, ProjectManager, Research Specialist, Business Analyst, CodeDeveloper, CodeReviewer, Report Drafter, Report Reviewer, and Report Publisher.
Tools and Frameworks:

Using langchain for NLP functionalities.
Utilizing Pydantic for data validation and structure.
Integrating with external APIs for information gathering and task management.
Agent Initialization:

Establishing a modular architecture where each agent can be initialized separately and linked to the Chat Coordinator.
Communication: Implementing communication channels or interfaces between agents, using message passing systems like MQTT or WebSocket.

Decision Logic: Each agent should have a clear decision logic based on its function, integrating with other relevant agents.

Error Handling:

Implementing error handling mechanisms to catch and respond to exceptions in data fetching, system failures, etc.
Testing:

Testing each agent individually before combining them into a multi-agent system.
Conducting integration tests to ensure that all components work seamlessly together.
Deployment: Deploy the system with proper load balancing and monitoring mechanisms for performance and fault tolerance.

This structured approach ensures that the multi-agent system is modular, scalable, and adaptable, making it suitable for a wide range of project-related tasks.