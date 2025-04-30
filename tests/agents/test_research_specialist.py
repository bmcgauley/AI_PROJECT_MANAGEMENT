"""
Unit tests for the ResearchSpecialistAgent class.
"""

import pytest
from unittest.mock import MagicMock, patch
from src.agents.research_specialist import ResearchSpecialistAgent


class TestResearchSpecialistAgent:
    """Tests for the ResearchSpecialistAgent class."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        self.llm = MagicMock()
        self.research_agent = ResearchSpecialistAgent(self.llm)

    def test_initialization_expected(self):
        """
        Test that the ResearchSpecialistAgent initializes correctly.
        
        Expected use case.
        """
        # Assert
        assert self.research_agent.name == "Research Specialist"
        assert "Gathers information" in self.research_agent.description
        assert self.research_agent.llm == self.llm
        assert hasattr(self.research_agent, 'research_chain')

    @patch('src.agents.research_specialist.LLMChain')
    def test_process_with_string_request_expected(self, mock_llm_chain):
        """
        Test processing a request passed as a string.
        
        Expected use case.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.return_value = "Research findings and recommendations"
        mock_llm_chain.return_value = mock_chain_instance
        
        # Act
        response = self.research_agent.process("Research best practices for Agile development")
        
        # Assert
        assert response == "Research findings and recommendations"
        mock_chain_instance.run.assert_called_once()
        
        # Verify memory was updated
        assert len(self.research_agent.memory) == 1
        assert self.research_agent.memory[0]["request"] == "Research best practices for Agile development"
        assert self.research_agent.memory[0]["response"] == "Research findings and recommendations"

    @patch('src.agents.research_specialist.LLMChain')
    def test_process_with_dict_request_expected(self, mock_llm_chain):
        """
        Test processing a request passed as a dictionary.
        
        Expected use case.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.return_value = "Research findings and recommendations"
        mock_llm_chain.return_value = mock_chain_instance
        
        request = {
            "original_text": "Research best practices for DevOps",
            "context": "Previous discussion about CI/CD pipelines"
        }
        
        # Act
        response = self.research_agent.process(request)
        
        # Assert
        assert response == "Research findings and recommendations"
        mock_chain_instance.run.assert_called_once_with(
            request="Research best practices for DevOps",
            context="Previous discussion about CI/CD pipelines"
        )

    @patch('src.agents.research_specialist.LLMChain')
    def test_process_with_original_request_key_edge_case(self, mock_llm_chain):
        """
        Test processing a request with 'original_request' key instead of 'original_text'.
        
        Edge case for backward compatibility.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.return_value = "Research findings and recommendations"
        mock_llm_chain.return_value = mock_chain_instance
        
        request = {
            "original_request": "Research best practices for DevOps",
            "context": "Previous discussion about CI/CD pipelines"
        }
        
        # Act
        response = self.research_agent.process(request)
        
        # Assert
        assert response == "Research findings and recommendations"
        # Check it used the correct key
        mock_chain_instance.run.assert_called_once()
        call_args = mock_chain_instance.run.call_args[1]
        assert call_args["request"] == "Research best practices for DevOps"

    @patch('src.agents.research_specialist.LLMChain')
    def test_process_without_context_edge_case(self, mock_llm_chain):
        """
        Test processing a request without context information.
        
        Edge case.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.return_value = "Research findings and recommendations"
        mock_llm_chain.return_value = mock_chain_instance
        
        request = {
            "original_text": "Research best practices for DevOps"
            # No context provided
        }
        
        # Act
        response = self.research_agent.process(request)
        
        # Assert
        assert response == "Research findings and recommendations"
        mock_chain_instance.run.assert_called_once()
        call_args = mock_chain_instance.run.call_args[1]
        assert call_args["context"] == "No previous context available."  # Default context

    @patch('src.agents.research_specialist.LLMChain')
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
        with patch.object(self.research_agent, 'logger') as mock_logger:
            response = self.research_agent.process("Research best practices for Agile development")
        
        # Assert
        assert "I apologize" in response
        assert "Test error" in response
        mock_logger.error.assert_called_once()

    @patch('src.agents.research_specialist.LLMChain')
    def test_process_empty_response_edge_case(self, mock_llm_chain):
        """
        Test processing when the LLM returns an empty response.
        
        Edge case.
        """
        # Arrange
        mock_chain_instance = MagicMock()
        mock_chain_instance.run.return_value = ""  # Empty response
        mock_llm_chain.return_value = mock_chain_instance
        
        # Act
        response = self.research_agent.process("Research best practices for Agile development")
        
        # Assert
        assert response == ""  # Should return empty string as is
        mock_chain_instance.run.assert_called_once() 