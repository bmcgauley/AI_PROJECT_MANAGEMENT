# AI Project Management System

A comprehensive AI Project Management System using the Agent Protocol framework with multiple specialized agents working together to manage projects. The system utilizes Ollama with the Mistral model as the local LLM for all agent operations.

## Architecture Overview

This system implements a multi-agent architecture that:

1. Provides a central Chat Coordinator as the main interface
2. Deploys specialized agents for different aspects of project management
3. Enables agents to communicate and collaborate on complex tasks
4. Integrates with Jira for project/task management
5. Produces high-quality code and documentation through review cycles

### Agent Structure

The system consists of 9 specialized agents:

- **Chat Coordinator**: Main interface that handles user interactions and orchestrates communication
- **Project Manager**: PMBOK/PMP certified agent for project planning, task management, and Jira integration
- **Research Specialist**: Gathers information and best practices for project requirements
- **Business Analyst**: Analyzes requirements and creates specifications
- **Code Developer**: Writes code based on specifications
- **Code Reviewer**: Reviews and suggests improvements to code
- **Report Drafter**: Creates project documentation and reports
- **Report Reviewer**: Reviews and refines reports
- **Report Publisher**: Formats and finalizes reports for delivery

## Requirements

- Python 3.8+
- Ollama installed locally
- Mistral model pulled via Ollama
- Git for version control
- Optional: Docker for containerized deployment

## Setup

### 1. Clone the Repository

```bash
git clone <repository-url>
cd ai-project-management-system
```

### 2. Install Ollama

Visit [https://ollama.ai/](https://ollama.ai/) and follow the installation instructions for your platform.

### 3. Pull the Mistral Model

```bash
ollama pull mistral
```

### 4. Set Up Python Environment

```bash
# Create a virtual environment
python -m venv .venv

# Activate the virtual environment
# Windows
.venv\Scripts\activate
# macOS/Linux
source .venv/bin/activate

# Install dependencies
pip install -r requirements.txt
```

### 5. Configure Environment Variables

Create a `.env` file based on `.env.example`:

```bash
cp .env.example .env
```

Edit the `.env` file to include your specific configuration:
- Ollama API endpoint
- Jira credentials (if using Jira integration)
- Other system-specific settings

### 6. Initialize the System

```bash
python -m src.setup
```

This will check if Ollama and the Mistral model are properly installed and configure the system.

## Usage

### Running the System

```bash
python -m src.main
```

This will start the Chat Coordinator agent, which will handle all user interactions and coordinate with other agents.

### Docker Deployment (Optional)

If you want to use Docker for containerized deployment:

```bash
# Build the Docker image
docker build -t ai-pm-system .

# Run the container
docker run -p 8000:8000 -v $(pwd)/data:/app/data ai-pm-system
```

## Testing

The project includes a comprehensive test suite using pytest. To run tests:

```bash
# Run all tests using the test runner script
python run_tests.py

# Run tests with coverage report
pytest --cov=src tests/
```

For more detailed testing information, see [TESTING.md](TESTING.md).

## System Workflows

The system supports the following workflows:

1. **Project Planning**: Create and manage project plans with tasks, timelines, and resources
2. **Code Development**: Develop code based on specifications with review and improvement cycles
3. **Documentation**: Create and refine project documentation and reports
4. **Jira Integration**: Manage tasks in Jira with automatic updates and synchronization

## Integration Points

- **Jira API**: For project and task management
- **Ollama API**: For accessing the Mistral LLM model
- **Git**: For version control and collaboration

## Development and Extension

See [CONTRIBUTING.md](CONTRIBUTING.md) for guidelines on extending the system with new agents or capabilities.
See [TASK.md](TASK.md) for the current development roadmap and task tracking.

## License

[MIT License](LICENSE) # Test comment
# Test authentication
