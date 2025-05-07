#!/usr/bin/env python3
"""
Windows-specific SQLite patching module for ChromaDB compatibility.

This module provides a Windows-compatible approach that bypasses the need for pysqlite3-binary,
which often has installation issues on Windows platforms.
"""

import sys
from unittest.mock import MagicMock

def apply_sqlite_patch():
    """
    Windows-specific SQLite patch that mocks ChromaDB.
    
    Instead of attempting to use pysqlite3-binary (which often fails on Windows),
    this function creates a complete mock of ChromaDB to allow the system to run
    without actual ChromaDB functionality.
    
    Returns:
        bool: True if patch was applied successfully
    """
    try:
        print("Applying Windows-compatible ChromaDB mock...")
        
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
                
                # Add any other attributes that might be accessed
                self.Client = MagicMock()
                self.PersistentClient = MagicMock()
                self.Collection = MagicMock()
                self.Documents = self.api.types.Documents
                self.EmbeddingFunction = self.api.types.EmbeddingFunction
                self.Embeddings = self.api.types.Embeddings

        chromadb_mock = ChromaDBMock()

        # Install the mock
        sys.modules['chromadb'] = chromadb_mock
        sys.modules['chromadb.api'] = chromadb_mock.api
        sys.modules['chromadb.api.types'] = chromadb_mock.api.types
        sys.modules['chromadb.config'] = chromadb_mock.config
        sys.modules['chromadb.errors'] = chromadb_mock.errors
        
        print("[SUCCESS] Windows-compatible ChromaDB mock applied successfully")
        return True
    except Exception as e:
        print(f"[ERROR] Failed to apply Windows-compatible ChromaDB mock: {str(e)}")
        return False
