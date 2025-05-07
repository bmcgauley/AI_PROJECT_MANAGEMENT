#!/usr/bin/env python3
"""
Windows-specific SQLite patching module for ChromaDB compatibility.

This module provides a Windows-compatible approach that attempts to use pysqlite3-binary
if available, and falls back to a mock implementation if not.
"""

import sys
import os
import importlib.util
import logging
import subprocess
from unittest.mock import MagicMock

logger = logging.getLogger("ai_pm_system.sqlite_patch_windows")

def apply_sqlite_patch():
    """
    Windows-specific SQLite patch for ChromaDB compatibility.
    
    Attempts three approaches in this order:
    1. Try to use pysqlite3-binary if installed
    2. Try to install pysqlite3-binary if pip is available
    3. Fall back to mocking ChromaDB if all else fails
    
    Returns:
        bool: True if patch was applied successfully
    """
    logger.info("Applying Windows-specific SQLite patch...")
    
    # First attempt: Check if pysqlite3 is already installed
    if importlib.util.find_spec("pysqlite3"):
        try:
            logger.info("Found pysqlite3 module, applying patch...")
            import pysqlite3
            import sqlite3
            
            # Store the original module for potential fallback
            sys.modules["sqlite3_original"] = sqlite3
            
            # Replace with pysqlite3
            sys.modules["sqlite3"] = pysqlite3
            logger.info("[SUCCESS] Applied pysqlite3 patch successfully")
            return True
        except Exception as e:
            logger.error(f"Failed to apply pysqlite3 patch despite module being present: {str(e)}")
    else:
        logger.warning("pysqlite3 module not found")
    
    # Second attempt: Try to install pysqlite3-binary
    try:
        logger.info("Attempting to install pysqlite3-binary...")
        result = subprocess.run(
            [sys.executable, "-m", "pip", "install", "pysqlite3-binary"],
            check=True,
            capture_output=True,
            text=True
        )
        logger.info(f"pysqlite3-binary installation output: {result.stdout}")
        
        # Try importing again after installation
        try:
            import pysqlite3
            import sqlite3
            
            # Store the original module for potential fallback
            sys.modules["sqlite3_original"] = sqlite3
            
            # Replace with pysqlite3
            sys.modules["sqlite3"] = pysqlite3
            logger.info("[SUCCESS] Installed and applied pysqlite3 patch successfully")
            return True
        except ImportError:
            logger.error("Failed to import pysqlite3 after installation")
    except subprocess.CalledProcessError as e:
        logger.error(f"Failed to install pysqlite3-binary: {str(e)}")
        logger.error(f"Error output: {e.stderr}")
    except Exception as e:
        logger.error(f"Unexpected error during pysqlite3-binary installation: {str(e)}")
    
    # Third attempt: Fall back to mocking ChromaDB
    try:
        logger.info("Falling back to ChromaDB mock implementation...")
        
        # Create a complete mock ChromaDB structure
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
                
                # Mock Client functionality for basic operations
                self.Client = MagicMock()
                self.Client.return_value.create_collection.return_value.add.return_value = None
                self.Client.return_value.create_collection.return_value.get.return_value = {
                    "ids": [], "embeddings": [], "documents": [], "metadatas": []
                }
                self.Client.return_value.create_collection.return_value.query.return_value = {
                    "ids": [], "embeddings": [], "documents": [], "metadatas": [], "distances": []
                }
                
                self.PersistentClient = MagicMock()
                self.Collection = MagicMock()
                self.Documents = self.api.types.Documents
                self.EmbeddingFunction = self.api.types.EmbeddingFunction
                self.Embeddings = self.api.types.Embeddings
                
                # Create environmental variable to signal the mock is in use
                os.environ["CHROMADB_MOCK_ACTIVE"] = "true"

        chromadb_mock = ChromaDBMock()

        # Install the mock
        sys.modules['chromadb'] = chromadb_mock
        sys.modules['chromadb.api'] = chromadb_mock.api
        sys.modules['chromadb.api.types'] = chromadb_mock.api.types
        sys.modules['chromadb.config'] = chromadb_mock.config
        sys.modules['chromadb.errors'] = chromadb_mock.errors
        
        logger.info("[SUCCESS] Windows-compatible ChromaDB mock applied successfully")
        
        # Inform user clearly about mock implementation
        print("=" * 80)
        print("⚠️  WARNING: Using mock ChromaDB implementation")
        print("    Vector database functionality will be limited.")
        print("    To enable full functionality, install pysqlite3-binary manually:")
        print("    pip install pysqlite3-binary")
        print("=" * 80)
        
        return True
    except Exception as e:
        logger.error(f"Failed to apply ChromaDB mock: {str(e)}")
        return False
