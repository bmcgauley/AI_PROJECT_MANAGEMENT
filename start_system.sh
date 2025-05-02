#!/bin/bash
# Script to start Ollama and the AI Project Management system

# Don't exit immediately on error - we want to handle errors gracefully
set +e

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
        return 0
    else
        echo "❌ Failed to verify $model model after download"
        return 1
    fi
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

# Make sure Ollama is installed
if ! command -v ollama &> /dev/null; then
    echo "❌ Ollama not found. Please install Ollama first."
    exit 1
fi

# Check if any Ollama processes are running but not responsive
if pgrep ollama >/dev/null && ! check_port 11434; then
    echo "⚠️ Ollama process found but not responding on port 11434. Restarting Ollama..."
    pkill ollama
    sleep 3
fi

# Forcefully kill any hung Ollama processes - this is important in container environments
pkill -9 ollama >/dev/null 2>&1 || true
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
    
    # Check if process is still running
    if ! kill -0 $OLLAMA_PID 2>/dev/null; then
        echo "❌ Ollama process died during startup"
        echo "Last few lines of Ollama startup log:"
        tail -10 ollama_startup.log
        exit 1
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

# Define list of models to try in order of preference
MODELS_TO_TRY=("mistral" "tinyllama" "llama2" "gemma")

# Check if any of the preferred models are available
MODEL_FOUND=false
for MODEL_NAME in "${MODELS_TO_TRY[@]}"; do
    echo "Checking for $MODEL_NAME model..."
    if verify_model "$MODEL_NAME"; then
        MODEL_FOUND=true
        echo "✅ Found $MODEL_NAME model, will use this one"
        break
    fi
done

# If no model is found, try to download models in order of size (smallest first)
if [ "$MODEL_FOUND" = false ]; then
    echo "⚠️ No suitable models found, will try to download one..."
    
    # Try downloading models in order (smallest first for faster downloads)
    for MODEL_TO_DOWNLOAD in "tinyllama" "mistral"; do
        echo "Attempting to download $MODEL_TO_DOWNLOAD..."
        if download_model "$MODEL_TO_DOWNLOAD"; then
            MODEL_NAME="$MODEL_TO_DOWNLOAD"
            MODEL_FOUND=true
            break
        else
            echo "Failed to download $MODEL_TO_DOWNLOAD, trying next model..."
        fi
    done
    
    # If still no model, give up
    if [ "$MODEL_FOUND" = false ]; then
        echo "❌ Failed to download any model. Please manually run 'ollama pull tinyllama' and try again."
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

# Make sure requirements are installed
echo "Ensuring all dependencies are installed..."
pip install -r requirements.txt >/dev/null

# Start the AI Project Management System
echo "🚀 Starting AI Project Management System..."
python3 src/main.py

# This point is only reached if the Python app exits
echo "❌ AI Project Management System has stopped"
