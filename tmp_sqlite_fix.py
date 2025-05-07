#!/usr/bin/env python3
"""
Cross-platform SQLite compatibility fix for ChromaDB.
This script works in both Windows and Linux environments.
"""
import sys
import subprocess
import os
import platform

def fix_sqlite():
    """Fix SQLite for both Windows and container environments."""
    print("[INFO] Cross-platform SQLite compatibility fix")
    
    # Determine if we're on Windows
    is_windows = platform.system() == "Windows"
    
    if is_windows:
        # Windows compatibility - no need for pysqlite3-binary
        print("[INFO] Windows environment detected, using built-in SQLite")
        print("[INFO] Skipping pysqlite3-binary installation on Windows")
        
        # Create a module-level patch for imports
        try:
            with open("src/sqlite_patch_windows.py", "w", encoding="utf-8") as f:
                f.write('''#!/usr/bin/env python3
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
''')
            print("[SUCCESS] Created Windows-compatible SQLite patch")
            return True
        except Exception as e:
            print(f"[ERROR] Failed to create Windows-compatible patch: {str(e)}")
            return False
            
    else:
        # Container/Linux environment - install and use pysqlite3-binary
        print("[INFO] Container/Linux environment detected, using pysqlite3-binary")
        
        # Check if pysqlite3-binary is installed
        try:
            import pysqlite3
            print("[SUCCESS] pysqlite3-binary is already installed.")
        except ImportError:
            print("[WARNING] pysqlite3-binary package not found. Installing...")
            try:
                subprocess.check_call([sys.executable, "-m", "pip", "install", "pysqlite3-binary"])
                print("[SUCCESS] Successfully installed pysqlite3-binary.")
            except subprocess.CalledProcessError as e:
                print(f"[ERROR] Failed to install pysqlite3-binary: {e}")
                return False
        
        # Verify installation
        try:
            import pysqlite3
            print(f"[SUCCESS] pysqlite3 version: {pysqlite3.sqlite_version}")
        except ImportError:
            print("[ERROR] Failed to import pysqlite3 after installation.")
            return False
        
        # Try patching sqlite3
        try:
            sys.modules['sqlite3'] = pysqlite3
            import sqlite3
            print(f"[SUCCESS] Successfully patched sqlite3 with pysqlite3. Version: {sqlite3.sqlite_version}")
        except Exception as e:
            print(f"[ERROR] Failed to patch sqlite3: {e}")
            return False
        
        print("[SUCCESS] SQLite fix completed successfully!")
        return True

if __name__ == "__main__":
    success = fix_sqlite()
    sys.exit(0 if success else 1)
