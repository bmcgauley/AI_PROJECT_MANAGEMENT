"""
Unit tests for the ProjectManagerAgent class.
"""

import pytest
from unittest.mock import MagicMock, patch
from src.agents.project_manager import ProjectManagerAgent


class TestProjectManagerAgent:
    """Tests for the ProjectManagerAgent class."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.llm = MagicMock()
        self.pm_agent = ProjectManagerAgent(self.llm)

    @patch('src.agents.project_manager.LLMChain')
    def test_process_with_string_request_expected(self, mock_llm_chain):
        """
        Test processing a request passed as a string.
        
        Expected use case.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.return_value = "Project management response"
        mock_llm_chain.return_value = mock_chain_instance
        
        # Act
        response = self.pm_agent.process("Create a project plan")
        
        # Assert
        assert response == "Project management response"
        mock_chain_instance.run.assert_called_once()
        
        # Verify memory was updated
        assert len(self.pm_agent.memory) == 1
        assert self.pm_agent.memory[0]["request"] == "Create a project plan"
        assert self.pm_agent.memory[0]["response"] == "Project management response"

    @patch('src.agents.project_manager.LLMChain')
    def test_process_with_dict_request_expected(self, mock_llm_chain):
        """
        Test processing a request passed as a dictionary.
        
        Expected use case.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.return_value = "Project management response"
        mock_llm_chain.return_value = mock_chain_instance
        
        request = {
            "original_text": "Create a project plan",
            "parsed_request": {
                "category": "Project Planning",
                "details": "User wants a project plan"
            },
            "context": "Previous discussion about project requirements"
        }
        
        # Act
        response = self.pm_agent.process(request)
        
        # Assert
        assert response == "Project management response"
        mock_chain_instance.run.assert_called_once_with(
            request="Create a project plan",
            context="Previous discussion about project requirements",
            category="Project Planning",
            details="User wants a project plan"
        )

    @patch('src.agents.project_manager.LLMChain')
    def test_process_with_original_request_key_expected(self, mock_llm_chain):
        """
        Test processing a request with 'original_request' key instead of 'original_text'.
        
        Edge case for backward compatibility.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.return_value = "Project management response"
        mock_llm_chain.return_value = mock_chain_instance
        
        request = {
            "original_request": "Create a project plan",
            "parsed_request": {
                "category": "Project Planning",
                "details": "User wants a project plan"
            }
        }
        
        # Act
        response = self.pm_agent.process(request)
        
        # Assert
        assert response == "Project management response"
        # Check it used the correct key
        mock_chain_instance.run.assert_called_once()
        call_args = mock_chain_instance.run.call_args[1]
        assert call_args["request"] == "Create a project plan"

    @patch('src.agents.project_manager.LLMChain')
    def test_process_with_jira_request_edge_case(self, mock_llm_chain):
        """
        Test processing a Jira-related request.
        
        Edge case for Jira integration.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.return_value = "Project management response"
        mock_llm_chain.return_value = mock_chain_instance
        
        # Manually set jira_enabled to True for testing
        self.pm_agent.jira_enabled = True
        
        request = {
            "original_text": "Create a Jira ticket for this feature",
            "parsed_request": {
                "category": "Task Management",
                "details": "User wants to create a Jira ticket"
            }
        }
        
        # Act
        with patch.object(self.pm_agent, 'logger') as mock_logger:
            response = self.pm_agent.process(request)
        
        # Assert
        assert "Jira" in response
        mock_logger.info.assert_called_with("Processing Jira-specific request")
        mock_chain_instance.run.assert_not_called()  # Should not call PM chain for Jira requests

    @patch('src.agents.project_manager.LLMChain')
    def test_process_with_missing_parsed_request_edge_case(self, mock_llm_chain):
        """
        Test processing a request without parsed_request information.
        
        Edge case.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.return_value = "Project management response"
        mock_llm_chain.return_value = mock_chain_instance
        
        request = {
            "original_text": "Create a project plan"
            # No parsed_request
        }
        
        # Act
        response = self.pm_agent.process(request)
        
        # Assert
        assert response == "Project management response"
        mock_chain_instance.run.assert_called_once()
        call_args = mock_chain_instance.run.call_args[1]
        assert call_args["category"] == "General Project Inquiry"  # Default category
        assert call_args["details"] == "No specific details provided"  # Default details

    @patch('src.agents.project_manager.LLMChain')
    def test_process_exception_handling_failure(self, mock_llm_chain):
        """
        Test exception handling during processing.
        
        Failure case.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.side_effect = Exception("Test error")
        mock_llm_chain.return_value = mock_chain_instance
        
        # Act
        with patch.object(self.pm_agent, 'logger') as mock_logger:
            response = self.pm_agent.process("Create a project plan")
        
        # Assert
        assert "I apologize" in response
        assert "Test error" in response
        mock_logger.error.assert_called_once()

    def test_initialization_expected(self):
        """
        Test that the ProjectManagerAgent initializes correctly.
        
        Expected use case.
        """
        # Assert
        assert self.pm_agent.name == "Project Manager"
        assert "PMBOK/PMP certified" in self.pm_agent.description
        assert self.pm_agent.llm == self.llm
        assert not self.pm_agent.jira_enabled  # Default is False 