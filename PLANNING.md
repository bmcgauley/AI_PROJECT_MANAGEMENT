# AI Project Management System - Planning Document

## Project Overview
The AI Project Management System is a multi-agent system designed to handle project management tasks using AI agents. The system is being transitioned from a LangChain-based implementation to a Crew.ai-based implementation to improve reliability and agent communication.

## Architecture

### Core Components
1. **Agent System**
   - Using Crew.ai for agent orchestration
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
- Crew.ai (for agent orchestration)
- FastAPI (web framework)
- Ollama (local LLM)
- Docker (for MCP servers)

### Key Libraries
- crewai>=0.28.0
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
1. Implement parallel system using Crew.ai
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