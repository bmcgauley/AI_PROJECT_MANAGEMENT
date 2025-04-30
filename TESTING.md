# Testing Guide

This document outlines how to run tests for the AI Project Management System.

## Setup

1. Make sure you have installed the development dependencies:

```bash
pip install -r requirements.txt
```

2. Ensure your Python path includes the project root directory.

## Running Tests

### Using the Test Runner Script

The simplest way to run all tests is to use the provided test runner script:

```bash
python run_tests.py
```

This will run all tests with verbose output.

### Using pytest Directly

You can also run tests directly using pytest:

```bash
# Run all tests
pytest

# Run with verbose output
pytest -v

# Run tests for a specific agent
pytest tests/agents/test_base_agent.py

# Run a specific test class
pytest tests/agents/test_chat_coordinator.py::TestChatCoordinatorAgent

# Run a specific test function
pytest tests/agents/test_project_manager.py::TestProjectManagerAgent::test_initialization_expected
```

### Code Coverage

To run tests with code coverage reports:

```bash
# Run tests with coverage
pytest --cov=src tests/

# Generate HTML coverage report
pytest --cov=src --cov-report=html tests/
```

The HTML coverage report will be generated in the `htmlcov` directory. Open `htmlcov/index.html` in a web browser to view the report.

## Test Structure

The test suite follows the same structure as the main application:

- `tests/agents/` - Tests for the agent classes
  - `test_base_agent.py` - Tests for the BaseAgent class
  - `test_chat_coordinator.py` - Tests for the ChatCoordinatorAgent class
  - `test_project_manager.py` - Tests for the ProjectManagerAgent class
  - (Additional test files for other agents)

Each test file includes at least:
1. Tests for expected use cases
2. Tests for edge cases
3. Tests for failure cases

## Writing New Tests

When adding new tests, follow these guidelines:

1. Create a test class for each agent class
2. Use descriptive test names that indicate what's being tested
3. Include docstrings that describe the test purpose and which category it belongs to
4. Follow the Arrange-Act-Assert pattern
5. Use mocks for external dependencies like LLM calls

Example test function:

```python
def test_some_functionality_expected(self):
    """
    Test that some functionality works as expected.
    
    Expected use case.
    """
    # Arrange - set up test conditions
    
    # Act - call the code being tested
    
    # Assert - verify the results
```

## Continuous Integration

In the future, these tests will be integrated into a CI/CD pipeline to automatically run on each commit or pull request. 