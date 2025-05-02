#!/bin/bash
# Script to start Ollama and the AI Project Management system

set -e # Exit immediately if a command exits with a non-zero status

echo "======================================================================"
echo "    Starting AI Project Management System with Ollama Integration      "
echo "======================================================================"

# Function to check if a port is in use
check_port() {
    nc -z localhost $1 >/dev/null 2>&1
}

# Function to clean up system resources
cleanup_system() {
    echo "🧹 Cleaning up system resources..."
    
    # Kill any existing Ollama processes
    if pgrep -x "ollama" > /dev/null; then
        echo "Found existing Ollama process, stopping it..."
        pkill ollama || true
        sleep 2
    fi
}

# Function to verify model availability
verify_model() {
    local model=$1
    curl -s "http://localhost:11434/api/tags" | grep -q "\"$model\""
    return $?
}

# Function to wait for port availability
wait_for_port() {
    local port=$1
    local service=$2
    local max_attempts=30
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
    echo "✅ $service is ready on port $port"
    return 0
}

# Initial cleanup
cleanup_system

# Start Ollama if not running
if ! check_port 11434; then
    echo "🚀 Starting Ollama service..."
    nohup ollama serve > ollama.log 2>&1 &
    
    if ! wait_for_port 11434 "Ollama"; then
        echo "❌ Failed to start Ollama"
        exit 1
    fi
fi

# Set default model name and verify it's available
MODEL_NAME="tinyllama"
echo "🔍 Checking for $MODEL_NAME model..."
if ! verify_model "$MODEL_NAME"; then
    echo "⚠️ Model $MODEL_NAME not found, pulling it now..."
    ollama pull $MODEL_NAME
    
    if ! verify_model "$MODEL_NAME"; then
        echo "❌ Failed to pull $MODEL_NAME model"
        exit 1
    fi
fi

# Setup environment variables
export PYTHONUNBUFFERED=1
export OLLAMA_MODEL="tinyllama"
export OLLAMA_BASE_URL="http://localhost:11434"
export LOG_LEVEL="INFO"

# Start the AI Project Management System
echo "🚀 Starting AI Project Management System..."
cd "$(dirname "$0")"

# Run setup_and_run.py in a new terminal
if command -v gnome-terminal &> /dev/null; then
    gnome-terminal -- python3 setup_and_run.py
elif command -v xterm &> /dev/null; then
    xterm -e "python3 setup_and_run.py" &
else
    # Fallback to running in current terminal
    python3 setup_and_run.py
fi

# Wait for the web interface to be available
if ! wait_for_port 8000 "Web Interface"; then
    echo "❌ Failed to start web interface"
    exit 1
fi

echo ""
echo "======================================================================"
echo "✅ AI Project Management System is ready!"
echo "   Web interface: http://localhost:8000"
echo "   Ollama API: http://localhost:11434"
echo ""
echo "Press Ctrl+C to stop all services"
echo "======================================================================"

# Keep the script running to maintain the startup terminal
wait
