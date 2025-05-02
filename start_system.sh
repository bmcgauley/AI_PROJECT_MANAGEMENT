#!/bin/bash
# Script to start Ollama and the AI Project Management system

set -e # Exit immediately if a command exits with a non-zero status

echo "======================================================================"
echo "    Starting AI Project Management System with Ollama Integration      "
echo "======================================================================"

# Function to check if Ollama is running
check_ollama() {
  curl -s http://localhost:11434/api/tags > /dev/null 2>&1
  return $?
}

# Function to start Ollama
start_ollama() {
  echo "🚀 Starting Ollama service..."
  
  # Kill any existing Ollama process
  if pgrep -x "ollama" > /dev/null; then
    echo "Found existing Ollama process, killing it..."
    pkill ollama || true
    sleep 2
  fi
  
  # Start Ollama server in the background
  ollama serve > ollama.log 2>&1 &
  
  # Store the PID of Ollama
  OLLAMA_PID=$!
  echo "Ollama started with PID: $OLLAMA_PID"
  
  # Wait for Ollama to initialize
  echo "⏳ Waiting for Ollama to initialize..."
  MAX_ATTEMPTS=30
  ATTEMPT=1
  
  while [ $ATTEMPT -le $MAX_ATTEMPTS ]; do
    echo "Attempt $ATTEMPT/$MAX_ATTEMPTS..."
    
    if check_ollama; then
      echo "✅ Ollama is now ready!"
      break
    fi
    
    if ! ps -p $OLLAMA_PID > /dev/null; then
      echo "❌ Error: Ollama process died. Check ollama.log for details."
      cat ollama.log
      exit 1
    fi
    
    echo "Still waiting for Ollama to start..."
    ATTEMPT=$((ATTEMPT + 1))
    sleep 2
  done
  
  if [ $ATTEMPT -gt $MAX_ATTEMPTS ]; then
    echo "❌ Error: Ollama failed to start after $MAX_ATTEMPTS attempts."
    echo "Check ollama.log for details:"
    cat ollama.log
    exit 1
  fi
  
  # Check if the mistral model is available
  echo "📊 Checking available models..."
  MODELS=$(curl -s http://localhost:11434/api/tags)
  echo "$MODELS" | grep -q '"name":"mistral"' || echo "⚠️ Warning: 'mistral' model may not be available. It will be downloaded on first use."
  
  echo "🔍 Available models:"
  echo "$MODELS" | grep '"name"' | sed 's/.*"name":"\([^"]*\)".*/- \1/' || echo "No models found"
}

# Check if Ollama is running
echo "🔍 Checking if Ollama is already running..."
if ! check_ollama; then
  echo "Ollama is not running."
  start_ollama
else
  echo "✅ Ollama is already running."
  
  # Display available models
  echo "🔍 Available models:"
  curl -s http://localhost:11434/api/tags | grep '"name"' | sed 's/.*"name":"\([^"]*\)".*/- \1/' || echo "No models found"
fi

# Pull the mistral model if not already available
if ! curl -s http://localhost:11434/api/tags | grep -q '"name":"mistral"'; then
  echo "⏳ Downloading mistral model (this may take several minutes)..."
  ollama pull mistral
fi

# Start the AI Project Management System
echo ""
echo "======================================================================"
echo "    Starting AI Project Management System...                           "
echo "======================================================================"
echo ""

cd "$(dirname "$0")" # Change to the script's directory
PYTHONUNBUFFERED=1 OLLAMA_MODEL=mistral OLLAMA_BASE_URL=http://localhost:11434 LOG_LEVEL=INFO python3 ./src/main.py

# The script will exit here when the Python program ends
echo "AI Project Management System has exited."
