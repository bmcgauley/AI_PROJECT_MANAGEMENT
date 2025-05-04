#!/usr/bin/env python3
"""
Tests for the WebSocketManager class with the ChatCoordinatorAgent.
"""

import os
import sys
import pytest
import json
from unittest.mock import MagicMock, AsyncMock, patch

# Patch SQLite before importing any module that might use ChromaDB
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))
from src.sqlite_patch import apply_sqlite_patch
apply_sqlite_patch()

# Now it's safe to import modules that might use ChromaDB
from src.web.ws_handlers import WebSocketManager
from src.request_processor import RequestProcessor
from src.agents.chat_coordinator import ChatCoordinatorAgent


class MockWebSocket:
    """Mock WebSocket for testing."""
    
    def __init__(self):
        """Initialize the mock WebSocket."""
        self.sent_messages = []
        self.closed = False
        self.accept = AsyncMock()
        self.send_text = AsyncMock(side_effect=self._store_message)
        self.receive_text = AsyncMock()
        self.close = AsyncMock(side_effect=self._set_closed)
        
    def _store_message(self, message):
        """Store a sent message."""
        self.sent_messages.append(message)
        
    def _set_closed(self):
        """Mark the WebSocket as closed."""
        self.closed = True
        
    def get_json_messages(self):
        """Get all sent messages as parsed JSON."""
        return [json.loads(msg) for msg in self.sent_messages]


class TestWebSocketManager:
    """Tests for the WebSocketManager class."""
    
    def setup_method(self):
        """Set up test fixtures before each test method."""
        # Create mock request processor
        self.mock_request_processor = MagicMock(spec=RequestProcessor)
        self.mock_request_processor.initialize = AsyncMock()
        self.mock_request_processor.process_request = AsyncMock()
        self.mock_request_processor.agent_states = {
            "Project Manager": "idle",
            "Code Developer": "idle"
        }
        
        # Create mock coordinator
        self.mock_coordinator = MagicMock(spec=ChatCoordinatorAgent)
        self.mock_coordinator.get_available_agents = MagicMock(
            return_value="Project Manager: Manages projects\nCode Developer: Writes code"
        )
        self.mock_request_processor.coordinator = self.mock_coordinator
        
        # Create WebSocketManager instance with mocks
        self.manager = WebSocketManager(self.mock_request_processor)
        
        # Create mock WebSocket
        self.mock_websocket = MockWebSocket()
    
    @pytest.mark.asyncio
    async def test_initialize_expected(self):
        """
        Test initializing the WebSocketManager.
        
        Expected use case.
        """
        # Act
        await self.manager.initialize()
        
        # Assert
        self.mock_request_processor.initialize.assert_called_once()
        assert self.manager.initialized == True
    
    @pytest.mark.asyncio
    async def test_handle_agent_event_expected(self):
        """
        Test handling an agent event from ChatCoordinatorAgent.
        
        Expected use case.
        """
        # Arrange
        client_id = await self.manager.connect(self.mock_websocket)
        
        # Register custom event handler
        mock_handler = AsyncMock()
        self.manager.register_event_handler("test_event", mock_handler)
        
        # Act
        await self.manager.handle_agent_event("test_event", message="Test message")
        
        # Assert
        mock_handler.assert_called_once()
        msgs = self.mock_websocket.get_json_messages()
        assert len(msgs) >= 1
        event_msgs = [msg for msg in msgs if msg["type"] == "test_event"]
        assert len(event_msgs) == 1
        assert event_msgs[0]["message"] == "Test message"
    
    @pytest.mark.asyncio
    async def test_process_request_expected(self):
        """
        Test processing a user request through the ChatCoordinatorAgent.
        
        Expected use case.
        """
        # Arrange
        client_id = await self.manager.connect(self.mock_websocket)
        self.mock_request_processor.process_request.return_value = {
            "status": "success",
            "processed_by": "Project Manager",
            "response": "Task completed successfully",
            "supporting_agents": ["Code Developer"],
            "request_id": "test-123"
        }
        
        # Act
        await self.manager.process_request(client_id, "Create a project timeline", "test-123")
        
        # Assert
        self.mock_request_processor.process_request.assert_called_once_with(
            user_request="Create a project timeline",
            request_id="test-123"
        )
        
        msgs = self.mock_websocket.get_json_messages()
        response_msgs = [msg for msg in msgs if msg["type"] == "response"]
        assert len(response_msgs) == 1
        assert response_msgs[0]["status"] == "success"
        assert response_msgs[0]["processed_by"] == "Project Manager"
        assert response_msgs[0]["response"] == "Task completed successfully"


if __name__ == '__main__':
    pytest.main()
