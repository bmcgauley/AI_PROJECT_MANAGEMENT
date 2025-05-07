#!/usr/bin/env python3
"""Check and fix langchain compatibility issues."""
import sys
import subprocess

def check_and_fix_langchain():
    """Check langchain versions and fix if necessary."""
    print("🔍 Checking LangChain dependencies...")
    
    try:
        # Try importing the required modules
        import langchain_core.messages
        
        # Check if 'is_data_content_block' is missing
        if not hasattr(langchain_core.messages, 'is_data_content_block'):
            print("⚠️ Detected outdated langchain_core. Upgrading...")
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "--upgrade",
                "langchain-core>=0.3.34",
                "langchain>=0.3.24",
                "langchain-community>=0.3.22",
                "langchain-ollama>=0.3.2"
            ])
            print("✅ LangChain dependencies upgraded.")
        else:
            print("✅ LangChain dependencies are up to date.")
        
        return True
    except ImportError as e:
        print(f"⚠️ ImportError: {e}")
        print("Attempting to reinstall LangChain dependencies...")
        
        try:
            subprocess.check_call([
                sys.executable, "-m", "pip", "install", "--upgrade",
                "langchain-core>=0.3.34",
                "langchain>=0.3.24",
                "langchain-community>=0.3.22",
                "langchain-ollama>=0.3.2"
            ])
            print("✅ LangChain dependencies reinstalled.")
            return True
        except subprocess.CalledProcessError as e:
            print(f"❌ Failed to reinstall LangChain dependencies: {e}")
            return False

if __name__ == "__main__":
    success = check_and_fix_langchain()
    sys.exit(0 if success else 1)
