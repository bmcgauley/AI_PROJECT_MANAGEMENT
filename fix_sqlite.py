#!/usr/bin/env python3
"""
This script fixes SQLite compatibility issues for ChromaDB.
It installs the necessary pysqlite3-binary package if not already installed.
"""

import sys
import subprocess
import os

def main():
    """Main function to fix SQLite compatibility issues."""
    print("🔧 Fixing SQLite compatibility issues for ChromaDB...")
    
    # Check if pysqlite3-binary is installed
    try:
        import pysqlite3
        print("✅ pysqlite3-binary is already installed.")
    except ImportError:
        print("⚠️ pysqlite3-binary package not found. Installing...")
        try:
            subprocess.check_call([sys.executable, "-m", "pip", "install", "pysqlite3-binary"])
            print("✅ Successfully installed pysqlite3-binary.")
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to install pysqlite3-binary: {e}")
            return False
    
    # Verify installation
    try:
        import pysqlite3
        print(f"✅ pysqlite3 version: {pysqlite3.sqlite_version}")
    except ImportError:
        print("❌ Failed to import pysqlite3 after installation.")
        return False
    
    # Create a simple test to ensure it can replace sqlite3
    try:
        # Try patching sqlite3
        sys.modules['sqlite3'] = pysqlite3
        import sqlite3
        print(f"✅ Successfully patched sqlite3 with pysqlite3. Version: {sqlite3.sqlite_version}")
    except Exception as e:
        print(f"❌ Failed to patch sqlite3: {e}")
        return False
    
    print("✅ SQLite fix completed successfully!")
    return True

if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
