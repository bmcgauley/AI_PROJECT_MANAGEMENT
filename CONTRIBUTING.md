# Contributing to the AI Project Management System

Thank you for your interest in contributing to the AI Project Management System! This document provides guidelines and instructions for developers who want to extend or modify the system.

## Getting Started

1. **Fork and Clone the Repository**
   ```bash
   git clone https://github.com/yourusername/ai-project-management-system.git
   cd ai-project-management-system
   ```

2. **Set Up Development Environment**
   ```bash
   # Create and activate a virtual environment
   python -m venv .venv
   source .venv/bin/activate  # On Windows: .venv\Scripts\activate
   
   # Install dependencies
   pip install -r requirements.txt
   
   # Install development dependencies
   pip install pytest black mypy
   ```

3. **Ensure Ollama is Installed and Running**
   ```bash
   # Run the setup script to verify your environment
   python -m src.setup
   ```

## Code Structure

The project is organized as follows:

- **src/**: Main source code directory
  - **agents/**: Individual agent implementations
    - **base_agent.py**: Abstract base class for all agents
    - **chat_coordinator.py**: Main interface that orchestrates other agents
    - Other specialized agent implementations
  - **main.py**: Application entry point
  - **setup.py**: Environment setup and validation

## Adding a New Agent

To add a new specialized agent to the system:

1. **Create a new agent file** in the `src/agents/` directory, inheriting from `BaseAgent`:
   ```python
   from src.agents.base_agent import BaseAgent
   
   class MyNewAgent(BaseAgent):
       def __init__(self, llm):
           super().__init__(
               llm=llm,
               name="My New Agent",
               description="Description of what this agent does"
           )
           # Initialize your agent-specific properties here
       
       def process(self, request):
           # Implement your agent's processing logic here
           return "Agent response"
   ```

2. **Update the imports** in `src/agents/__init__.py` to include your new agent.

3. **Register your agent** in `src/main.py`:
   ```python
   # Initialize the new agent
   my_new_agent = MyNewAgent(llm)
   
   # Add it to the chat coordinator
   chat_coordinator.add_agent("my_new_agent", my_new_agent)
   ```

## Modifying an Existing Agent

To modify an existing agent's behavior:

1. **Update the agent's prompt template** to adjust how it responds to requests.
2. **Enhance the processing logic** in the `process()` method to add new capabilities.
3. **Add new methods** for specialized functionality that your agent needs.

## Testing Your Changes

Run the test suite to ensure your changes don't break existing functionality:

```bash
# Run all tests
pytest

# Run tests for a specific agent
pytest tests/agents/test_my_agent.py
```

## Code Style Guidelines

This project follows these style guidelines:

1. **PEP 8** for general Python code style
2. **Type hints** for all function parameters and return values
3. **Google-style docstrings** for all classes and methods
4. **Black** for code formatting:
   ```bash
   black src/
   ```
5. **MyPy** for type checking:
   ```bash
   mypy src/
   ```

## Submitting Changes

1. **Create a feature branch** for your changes:
   ```bash
   git checkout -b feature/my-new-feature
   ```

2. **Commit your changes** with clear, descriptive commit messages:
   ```bash
   git commit -m "Add new agent for handling X functionality"
   ```

3. **Push your branch** to your fork:
   ```bash
   git push origin feature/my-new-feature
   ```

4. **Create a Pull Request** against the main repository.

## Agent Communication Protocol

When adding or modifying agents, maintain the established communication protocol:

1. **Input Format**: Each agent's `process()` method accepts a dictionary containing:
   - `original_text`: The original user request
   - `parsed_request`: Parsed information about the request
   - `context`: Previous conversation context
   - Other request-specific parameters

2. **Output Format**: Each agent should return either:
   - A string containing the response
   - A dictionary with at least a `response` key and optional metadata

## Adding New Dependencies

If your agent requires new dependencies:

1. **Add them to requirements.txt** with version constraints
2. **Document the dependency** in this contributing guide if it requires special handling

## Questions or Problems?

If you have any questions about contributing, please open an issue on the repository. 