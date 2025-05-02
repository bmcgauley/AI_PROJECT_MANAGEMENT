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

# Function to verify model availability
verify_model() {
    local model=$1
    curl -s "http://localhost:11434/api/tags" | grep -q "\"$model\""
    return $?
}

# Function to clean up system resources
cleanup_system() {
    echo "🧹 Cleaning up system resources..."
    
    # Kill any existing system processes
    pkill -f "python.*src/main.py" >/dev/null 2>&1 || true
    
    # Clean up Docker containers if they exist
    if command -v docker &> /dev/null; then
        echo "Cleaning up Docker containers..."
        docker rm -f mcp-filesystem-aipm mcp-context7-aipm mcp-atlassian-aipm 2>/dev/null || true
    fi
}

# Initial cleanup
cleanup_system

# Check if Ollama is already running, and start it if not
if ! check_port 11434; then
    echo "🚀 Starting Ollama service..."
    
    # Kill any existing Ollama processes
    pkill ollama >/dev/null 2>&1 || true
    sleep 2
    
    # Start Ollama with output to log file
    nohup ollama serve > ollama.log 2>&1 &
    OLLAMA_PID=$!
    
    # Wait for Ollama to become available
    if ! wait_for_port 11434 "Ollama"; then
        echo "❌ Failed to start Ollama service"
        exit 1
    fi
else
    echo "✅ Ollama service is already running on port 11434"
fi

# Verify that Ollama is responding properly
echo "Verifying Ollama API..."
if ! curl -s http://localhost:11434/api/tags > /dev/null; then
    echo "❌ Ollama API is not responding properly"
    exit 1
fi
echo "✅ Ollama API is responding properly"

# Check for default model
MODEL_NAME="tinyllama"
if ! verify_model "$MODEL_NAME"; then
    echo "⚠️ Model $MODEL_NAME not found, trying to pull it..."
    ollama pull $MODEL_NAME
    
    if ! verify_model "$MODEL_NAME"; then
        echo "⚠️ Could not pull tinyllama model, checking for mistral instead..."
        MODEL_NAME="mistral"
        
        if ! verify_model "$MODEL_NAME"; then
            echo "❌ No suitable models found. Please run 'ollama pull tinyllama' or 'ollama pull mistral' first."
            exit 1
        fi
    fi
fi

echo "✅ Using model: $MODEL_NAME"

# Setup environment variables for the Python application
export OLLAMA_MODEL=$MODEL_NAME
export OLLAMA_BASE_URL="http://127.0.0.1:11434"
export LOG_LEVEL="INFO"
export PYTHONPATH="$(pwd)"

# Make sure requirements are installed
echo "Ensuring all dependencies are installed..."
pip install -r requirements.txt >/dev/null 2>&1

# Start the AI Project Management System
echo "🚀 Starting AI Project Management System..."
python3 src/main.py

# This point is only reached if the Python app exits
echo "❌ AI Project Management System has stopped"
