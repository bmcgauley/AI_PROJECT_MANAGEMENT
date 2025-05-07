#!/bin/bash
# Script to start Ollama and the AI Project Management system

# Don't exit immediately on error - we want to handle errors gracefully
set +e

echo "======================================================================"
echo "    Starting AI Project Management System with Ollama Integration      "
echo "======================================================================"

# Detect operating system
WINDOWS=false
if [[ "$OSTYPE" == "msys"* ]] || [[ "$OSTYPE" == "win"* ]] || [[ -n "$WINDIR" ]]; then
    WINDOWS=true
    echo "🔍 Detected Windows environment"
else
    echo "🔍 Detected Unix/Linux environment"
fi

# Function to check if a port is in use (cross-platform)
check_port() {
    local port=$1
    if $WINDOWS; then
        # PowerShell command for Windows
        powershell -command "if ((Test-NetConnection -ComputerName localhost -Port $port -WarningAction SilentlyContinue -ErrorAction SilentlyContinue).TcpTestSucceeded) {exit 0} else {exit 1}" > /dev/null 2>&1
    else
        # nc command for Linux/macOS
        nc -z localhost $port > /dev/null 2>&1
    fi
}

# Function to wait for port availability
wait_for_port() {
    local port=$1
    local service=$2
    local max_attempts=60  # Increase timeout to 60 seconds
    local attempt=1
    
    echo "Waiting for $service on port $port..."
    while ! check_port $port; do
        if [ $attempt -ge $max_attempts ]; then
            echo "❌ Timeout waiting for $service to start on port $port"
            return 1
        fi
        echo -n "."
        sleep 1
        attempt=$((attempt + 1))
    done
    echo ""
    echo "✅ $service is ready on port $port"
    return 0
}

# Function to verify model availability
verify_model() {
    local model=$1
    curl -s "http://localhost:11434/api/tags" | grep -q "\"name\":\"$model:\|\"name\":\"$model\","
    return $?
}

# Function to verify model can be loaded without crashing
test_model() {
    local model=$1
    echo "🔍 Testing model $model..."
    
    # Try a simple completion to see if the model works
    TEST_RESULT=$(curl -s --max-time 30 http://localhost:11434/api/generate -d "{
      \"model\": \"$model\",
      \"prompt\": \"Say hello\",
      \"stream\": false
    }")
    
    # Check if we got an error response
    if echo "$TEST_RESULT" | grep -q "error"; then
        echo "⚠️ Model $model failed the test: $(echo "$TEST_RESULT" | grep -o '"error":[^}]*' | cut -d':' -f2-)"
        return 1
    fi
    
    echo "✅ Model $model passed the test"
    return 0
}

# Function to download a model with validation
download_model() {
    local model=$1
    echo "⚠️ Downloading $model model (this may take a while)..."
    ollama pull $model
    
    # Wait a moment for the model to be registered
    sleep 3
    
    # Verify model was correctly downloaded
    if verify_model "$model"; then
        echo "✅ Successfully pulled $model model"
        
        # Test if the model can be used without crashing
        if test_model "$model"; then
            return 0
        else
            echo "⚠️ Model $model was downloaded but failed the functionality test"
            return 1
        fi
    else
        echo "❌ Failed to verify $model model after download"
        return 1
    fi
}

# Function to clean up system resources
cleanup_system() {
    echo "🧹 Cleaning up system resources..."
    
    # Kill any existing system processes (cross-platform)
    if $WINDOWS; then
        taskkill /F /IM python.exe /FI "WINDOWTITLE eq src/main.py" > /dev/null 2>&1 || true
        taskkill /F /IM python.exe /FI "WINDOWTITLE eq src/modern_main.py" > /dev/null 2>&1 || true
    else
        # Unix/Linux process killing
        pkill -f "python.*src/main.py" > /dev/null 2>&1 || true
        pkill -f "python.*src/modern_main.py" > /dev/null 2>&1 || true
    fi
    
    # Clean up Docker containers if they exist
    if command -v docker &> /dev/null; then
        echo "Cleaning up Docker containers..."
        docker rm -f mcp-filesystem-aipm mcp-context7-aipm mcp-atlassian-aipm 2>/dev/null || true
    fi
}

# Initial cleanup
cleanup_system

# Make sure Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama not found. Please install Ollama first."
    exit 1
fi

# Check available memory in a cross-platform way
if $WINDOWS; then
    # PowerShell command to get available memory in GB (rounded to 1 decimal place)
    AVAILABLE_MEM_GB=$(powershell -command "[math]::Round((Get-CimInstance Win32_OperatingSystem).FreePhysicalMemory/1MB, 1)")
else
    # Linux command using grep and bc
    if command -v bc &> /dev/null; then
        AVAILABLE_MEM_KB=$(grep MemAvailable /proc/meminfo | awk '{print $2}')
        AVAILABLE_MEM_GB=$(echo "scale=1; $AVAILABLE_MEM_KB/1024/1024" | bc)
    else
        # Fallback if bc is not available
        AVAILABLE_MEM_GB="unknown"
    fi
fi
echo "💻 Available memory: ${AVAILABLE_MEM_GB}GB"

# Check if any Ollama processes are running but not responsive
if $WINDOWS; then
    # Windows version using PowerShell to check for process
    OLLAMA_RUNNING=$(powershell -command "Get-Process ollama -ErrorAction SilentlyContinue")
    if [[ -n "$OLLAMA_RUNNING" ]] && ! check_port 11434; then
        echo "⚠️ Ollama process found but not responding on port 11434. Restarting Ollama..."
        taskkill /F /IM ollama.exe > /dev/null 2>&1
        sleep 3
    fi
else
    # Unix/Linux version
    if command -v pgrep &> /dev/null; then
        if pgrep ollama >/dev/null && ! check_port 11434; then
            echo "⚠️ Ollama process found but not responding on port 11434. Restarting Ollama..."
            pkill ollama
            sleep 3
        fi
    fi
fi

# Forcefully kill any hung Ollama processes - cross-platform
if $WINDOWS; then
    taskkill /F /IM ollama.exe > /dev/null 2>&1 || true
else
    pkill -9 ollama > /dev/null 2>&1 || true
fi
sleep 2

# Start Ollama in foreground mode first to ensure initialization
echo "🚀 Starting Ollama service..."
ollama serve > ollama_startup.log 2>&1 &
OLLAMA_PID=$!

# Wait for Ollama to become available with increased timeout
echo "Waiting for Ollama to initialize (this may take a minute)..."
WAIT_TIME=0
MAX_WAIT=60
while ! curl -s --fail http://localhost:11434/api/tags >/dev/null 2>&1; do
    if [ $WAIT_TIME -ge $MAX_WAIT ]; then
        echo "❌ Ollama failed to start within $MAX_WAIT seconds"
        echo "Last few lines of Ollama startup log:"
        tail -10 ollama_startup.log
        exit 1
    fi
    
    # Check if process is still running (cross-platform)
    if $WINDOWS; then
        if ! powershell -command "Get-Process -Id $OLLAMA_PID -ErrorAction SilentlyContinue"; then
            echo "❌ Ollama process died during startup"
            echo "Last few lines of Ollama startup log:"
            tail -10 ollama_startup.log
            exit 1
        fi
    else
        if ! kill -0 $OLLAMA_PID 2>/dev/null; then
            echo "❌ Ollama process died during startup"
            echo "Last few lines of Ollama startup log:"
            tail -10 ollama_startup.log
            exit 1
        fi
    fi
    
    echo -n "."
    sleep 2
    WAIT_TIME=$((WAIT_TIME + 2))
done

echo ""
echo "✅ Ollama is running and responding to API calls"

# Verify that Ollama API is responding with model list
echo "Verifying Ollama API..."
MODELS_JSON=$(curl -s http://localhost:11434/api/tags)
if [ -z "$MODELS_JSON" ]; then
    echo "❌ Ollama API returned empty response"
    exit 1
fi
echo "✅ Ollama API is responding properly"

# Define list of models to try in order of preference - prioritize tinyllamadue to memory constraints
# The tinyllama model (7.2B parameters) requires more RAM, so we prefer tinyllama(1B parameters)
MODELS_TO_TRY=("tinyllama" "tinyllama" "gemma" "llama2")

# Check if any of the preferred models are available
MODEL_FOUND=false
for MODEL_NAME in "${MODELS_TO_TRY[@]}"; do
    echo "Checking for $MODEL_NAME model..."
    if verify_model "$MODEL_NAME"; then
        echo "✅ Found $MODEL_NAME model, testing if it works properly..."
        if test_model "$MODEL_NAME"; then
            MODEL_FOUND=true
            echo "✅ Will use $MODEL_NAME model"
            break
        else
            echo "⚠️ Model $MODEL_NAME failed the test, trying next model..."
        fi
    fi
done

# If no model is found, try to download tinyllama(smallest model)
if [ "$MODEL_FOUND" = false ]; then
    echo "⚠️ No suitable models found or all existing models failed tests, will download tinyllama..."
    if download_model "tinyllama"; then
        MODEL_NAME="tinyllama"
        MODEL_FOUND=true
    else
        echo "❌ Failed to download tinyllamamodel. Please manually run 'ollama pull tinyllama' and try again."
        echo "See https://ollama.ai/library for more models."
        exit 1
    fi
fi

echo "✅ Using model: $MODEL_NAME"

# Setup environment variables for the Python application
export OLLAMA_MODEL=$MODEL_NAME
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export LOG_LEVEL="INFO"
export PYTHONPATH="$(pwd)"

# Cross-platform approach to handling dependencies
echo "Installing requirements..."
python -m pip install --upgrade pip
python -m pip install -r requirements.txt
if [ -f mcp_servers/requirements.txt ]; then
    python -m pip install -r mcp_servers/requirements.txt
fi

# Create a cross-platform compatible Python script for SQLite patching
cat > tmp_sqlite_fix.py << 'EOF'
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
EOF

# Apply the cross-platform SQLite patch
echo "Applying cross-platform SQLite patch..."
python tmp_sqlite_fix.py

# Create a version check script for langchain
cat > tmp_version_fix.py << 'EOF'
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
EOF

# Fix LangChain dependencies
echo "Checking and fixing LangChain dependencies..."
python tmp_version_fix.py

# Check if the user wants to use the legacy system
if [ "$1" = "--legacy" ]; then
    echo "Starting legacy system..."
    python -m src.main
else
    # Start the modern system by default
    echo "Starting modern system with Pydantic and LangGraph..."
    python -m src.modern_main
fi

# Clean up temporary files
rm -f tmp_sqlite_fix.py tmp_version_fix.py

echo "System shutdown complete."
