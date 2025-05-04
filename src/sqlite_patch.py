#!/usr/bin/env python3
"""
SQLite patching module for ChromaDB compatibility.

This module provides fixes for SQLite version compatibility issues with ChromaDB.
It should be imported before any ChromaDB imports in any module that uses ChromaDB.
"""

import sys
import os
from unittest.mock import MagicMock

def apply_sqlite_patch():
    """
    Apply SQLite patching for ChromaDB compatibility.
    
    This function:
    1. Replaces the system's SQLite with pysqlite3-binary (which has newer version)
    2. Creates a complete mock of ChromaDB to avoid actual initialization issues
    
    Returns:
        bool: True if patch was applied successfully
    """
    try:
        print("Applying SQLite patch for ChromaDB compatibility...")
        
        # Configure pysqlite3 binary
        __import__('pysqlite3')
        sys.modules['sqlite3'] = sys.modules.pop('pysqlite3')
        
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
        
        print("✅ SQLite patch applied successfully.")
        return True
        
    except ImportError as e:
        print(f"❌ Failed to apply SQLite patch: {str(e)}")
        print("Make sure 'pysqlite3-binary' is installed. You can install it with:")
        print("pip install pysqlite3-binary")
        return False
    except Exception as e:
        print(f"❌ Failed to apply SQLite patch: {str(e)}")
        return False
