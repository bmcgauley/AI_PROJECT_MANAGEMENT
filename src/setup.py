"""
Setup script for the AI Project Management System.
Checks for and configures the Ollama environment.
"""

import os
import sys
import subprocess
import time
import requests
import platform
import shutil
from dotenv import load_dotenv

def print_header(message):
    """Print a formatted header message."""
    print("\n" + "=" * 60)
    print(f"  {message}")
    print("=" * 60 + "\n")

def check_ollama_installed():
    """Check if Ollama is installed."""
    print("Checking if Ollama is installed...")
    
    if platform.system() == "Windows":
        ollama_path = shutil.which("ollama.exe")
    else:
        ollama_path = shutil.which("ollama")
    
    if ollama_path:
        print("✅ Ollama is installed.")
        return True
    else:
        print("❌ Ollama is not installed.")
        print("\nPlease install Ollama:")
        print("  Visit https://ollama.ai/ to download and install Ollama.")
        return False

def check_ollama_running(base_url="http://localhost:11434"):
    """Check if Ollama service is running."""
    print("Checking if Ollama service is running...")
    
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        if response.status_code == 200:
            print("✅ Ollama service is running.")
            return True
        else:
            print(f"❌ Ollama service is not responding properly. Status code: {response.status_code}")
            return False
    except requests.exceptions.RequestException:
        print("❌ Ollama service is not running or not accessible.")
        
        if platform.system() == "Windows":
            print("\nPlease start Ollama:")
            print("  Check if Ollama is running in the system tray or start it from the Start menu.")
        else:
            print("\nPlease start Ollama with:")
            print("  ollama serve")
        
        return False

def check_mistral_model(base_url="http://localhost:11434"):
    """Check if the Mistral model is available."""
    print("Checking if Mistral model is available...")
    
    try:
        response = requests.get(f"{base_url}/api/tags", timeout=5)
        models = response.json().get("models", [])
        
        # Check if mistral is in the list of models
        mistral_available = any(model.get("name") == "mistral" for model in models)
        
        if mistral_available:
            print("✅ Mistral model is available.")
            return True
        else:
            print("❌ Mistral model is not available.")
            return False
    except (requests.exceptions.RequestException, ValueError):
        print("❌ Could not check for Mistral model. Make sure Ollama is running.")
        return False

def pull_mistral_model(base_url="http://localhost:11434"):
    """Pull the Mistral model from Ollama."""
    print("Pulling Mistral model (this may take a while)...")
    
    try:
        # For simplicity, we'll use subprocess to run the ollama pull command
        # In a production application, you might want to use the Ollama API directly
        result = subprocess.run(
            ["ollama", "pull", "mistral"],
            capture_output=True,
            text=True,
            check=True
        )
        
        if result.returncode == 0:
            print("✅ Successfully pulled Mistral model.")
            return True
        else:
            print(f"❌ Failed to pull Mistral model. Error: {result.stderr}")
            return False
    except subprocess.SubprocessError as e:
        print(f"❌ Failed to pull Mistral model. Error: {str(e)}")
        return False

def create_env_file():
    """Create a .env file if it doesn't exist."""
    if os.path.exists(".env"):
        print("✅ .env file already exists.")
        return
    
    print("Creating .env file...")
    
    env_content = """# Ollama Configuration
OLLAMA_BASE_URL=http://localhost:11434
OLLAMA_MODEL=mistral

# System Configuration
LOG_LEVEL=INFO
DATA_DIR=./data
ENABLE_AGENT_MEMORY=true
"""
    
    try:
        with open(".env", "w") as f:
            f.write(env_content)
        print("✅ Created .env file.")
    except Exception as e:
        print(f"❌ Failed to create .env file. Error: {str(e)}")

def create_data_directory():
    """Create the data directory for storing agent state."""
    data_dir = os.getenv("DATA_DIR", "./data")
    
    if not os.path.exists(data_dir):
        print(f"Creating data directory at {data_dir}...")
        try:
            os.makedirs(data_dir)
            print(f"✅ Created data directory at {data_dir}.")
        except Exception as e:
            print(f"❌ Failed to create data directory. Error: {str(e)}")
    else:
        print(f"✅ Data directory already exists at {data_dir}.")

def main():
    """Main setup function."""
    print_header("AI Project Management System - Setup")
    
    # Load environment variables
    load_dotenv()
    
    # Set base URL
    base_url = os.getenv("OLLAMA_BASE_URL", "http://localhost:11434")
    
    # Check Ollama installation
    if not check_ollama_installed():
        sys.exit(1)
    
    # Check if Ollama is running
    if not check_ollama_running(base_url):
        print("\nPlease start Ollama and run this setup script again.")
        sys.exit(1)
    
    # Check for Mistral model
    has_mistral = check_mistral_model(base_url)
    
    # Pull Mistral model if not available
    if not has_mistral:
        print("\nPulling Mistral model...")
        if not pull_mistral_model(base_url):
            print("\nFailed to pull Mistral model. Please try manually with:")
            print("  ollama pull mistral")
            print("\nThen run this setup script again.")
            sys.exit(1)
    
    # Create .env file if it doesn't exist
    create_env_file()
    
    # Create data directory
    create_data_directory()
    
    print_header("Setup Completed Successfully!")
    print("You can now run the AI Project Management System with:")
    print("  python -m src.main")
    print("\nEnjoy using your AI Project Management System!")

if __name__ == "__main__":
    main() 