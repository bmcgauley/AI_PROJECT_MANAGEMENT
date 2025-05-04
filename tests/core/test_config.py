#!/usr/bin/env python3
"""
Tests for the config module.
"""

import os
import sys
import unittest
from unittest.mock import patch, MagicMock

# Add parent directory to path for imports
sys.path.append(os.path.abspath(os.path.join(os.path.dirname(__file__), '../..')))

from src.config import (
    configure_sqlite_patches, 
    create_chromadb_mock, 
    install_chromadb_mock,
    get_ollama_config,
    get_mcp_config_path,
    setup_environment,
    get_agent_config,
    get_web_config
)

class TestConfig(unittest.TestCase):
    """Tests for the config module functions."""
    
    @patch('src.config.__import__')
    @patch('src.config.sys.modules')
    def test_configure_sqlite_patches_success(self, mock_sys_modules, mock_import):
        """Test successful SQLite patching when pysqlite3 is available."""
        # Setup mock to simulate successful import
        mock_sys_modules.__getitem__.return_value = MagicMock()
        mock_sys_modules.pop.return_value = MagicMock()
        
        configure_sqlite_patches()
        
        # Verify the import was attempted
        mock_import.assert_called_with('pysqlite3')
        # Verify the module was popped from sys.modules
        mock_sys_modules.pop.assert_called_with('pysqlite3')

    @patch('src.config.__import__')
    def test_configure_sqlite_patches_not_available(self, mock_import):
        """Test SQLite patching behavior when pysqlite3 is not available."""
        # Setup mock to raise ImportError
        mock_import.side_effect = ImportError("No module named 'pysqlite3'")
        
        # This should not raise an exception
        configure_sqlite_patches()
        
        # Verify the import was attempted
        mock_import.assert_called_with('pysqlite3')

    def test_create_chromadb_mock(self):
        """Test creation of ChromaDB mock object."""
        mock = create_chromadb_mock()
        
        # Verify the mock has the expected attributes
        self.assertTrue(hasattr(mock, 'api'))
        self.assertTrue(hasattr(mock, 'config'))
        self.assertTrue(hasattr(mock, 'errors'))
        self.assertTrue(hasattr(mock, 'Client'))
        self.assertTrue(hasattr(mock, 'Collection'))
        self.assertTrue(hasattr(mock, 'PersistentClient'))
        
        # Verify the error classes are created
        self.assertTrue(issubclass(mock.errors.NoDatapointsError, mock.errors.ChromaError))
        self.assertTrue(issubclass(mock.errors.InvalidDimensionException, mock.errors.ChromaError))

    @patch('src.config.sys.modules')
    def test_install_chromadb_mock(self, mock_sys_modules):
        """Test installation of ChromaDB mock into sys.modules."""
        install_chromadb_mock()
        
        # Verify the modules were installed
        self.assertEqual(len(mock_sys_modules.__setitem__.call_args_list), 5)
        mock_module_names = [args[0][0] for args in mock_sys_modules.__setitem__.call_args_list]
        
        # Check that all expected modules were mocked
        self.assertIn('chromadb', mock_module_names)
        self.assertIn('chromadb.api', mock_module_names)
        self.assertIn('chromadb.api.types', mock_module_names)
        self.assertIn('chromadb.config', mock_module_names)
        self.assertIn('chromadb.errors', mock_module_names)

    @patch.dict(os.environ, {'OLLAMA_MODEL': 'testmodel', 'OLLAMA_BASE_URL': 'http://test:11434'})
    def test_get_ollama_config_with_environment_variables(self):
        """Test getting Ollama config with environment variables set."""
        config = get_ollama_config()
        
        self.assertEqual(config['model_name'], 'testmodel')
        self.assertEqual(config['base_url'], 'http://test:11434')
        self.assertTrue('system_message' in config)

    @patch.dict(os.environ, {}, clear=True)
    def test_get_ollama_config_defaults(self):
        """Test getting Ollama config with default values."""
        config = get_ollama_config()
        
        # Verify defaults are used when environment variables are not set
        self.assertIn('model_name', config)
        self.assertIn('base_url', config)
        self.assertIn('system_message', config)

    @patch.dict(os.environ, {'MCP_CONFIG_PATH': '/custom/path/mcp.json'})
    def test_get_mcp_config_path_custom(self):
        """Test getting custom MCP config path."""
        path = get_mcp_config_path()
        self.assertEqual(path, '/custom/path/mcp.json')

    @patch.dict(os.environ, {}, clear=True)
    def test_get_mcp_config_path_default(self):
        """Test getting default MCP config path."""
        path = get_mcp_config_path()
        self.assertEqual(path, 'mcp.json')

    @patch('src.config.configure_sqlite_patches')
    @patch('src.config.install_chromadb_mock')
    def test_setup_environment(self, mock_install_chromadb, mock_configure_sqlite):
        """Test environment setup function."""
        # Call with default environment
        setup_environment()
        
        # Verify that both patches are applied by default
        mock_configure_sqlite.assert_called_once()
        mock_install_chromadb.assert_called_once()

    def test_get_agent_config_known_agent(self):
        """Test getting configuration for a known agent type."""
        config = get_agent_config("project_manager")
        
        # Verify expected config properties
        self.assertEqual(config["role"], "Project Manager")
        self.assertIn("backstory", config)
        self.assertIn("goal", config)
        self.assertTrue(config["allow_delegation"])  # PM should allow delegation
        self.assertTrue(config["verbose"])

    def test_get_agent_config_unknown_agent(self):
        """Test getting configuration for an unknown agent type."""
        config = get_agent_config("unknown_agent_type")
        
        # Verify it returns a base configuration without specific settings
        self.assertIn("verbose", config)
        self.assertIn("allow_delegation", config)  # Base config should include this
        self.assertFalse(config["allow_delegation"])  # Default to false

    def test_get_web_config_with_defaults(self):
        """Test getting web config with default values."""
        config = get_web_config()
        
        # Check that all expected config keys are present
        self.assertIn("host", config)
        self.assertIn("port", config)
        self.assertIn("log_level", config)
        self.assertIn("static_dir", config)
        self.assertIn("templates_dir", config)
        
        # Verify default port is an integer
        self.assertIsInstance(config["port"], int)
        
        # Verify directories are correctly specified
        self.assertEqual(config["static_dir"], "src/web/static")
        self.assertEqual(config["templates_dir"], "src/web/templates")

if __name__ == '__main__':
    unittest.main()
