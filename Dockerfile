FROM python:3.9-slim

# Set working directory
WORKDIR /app

# Set environment variables
ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app

# Install system dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    curl \
    git \
    wget \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Install Ollama CLI
RUN wget https://ollama.com/downloads/ollama-windows-amd64.exe -O /usr/local/bin/ollama.exe && \
    chmod +x /usr/local/bin/ollama.exe

# Copy requirements file
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy project files
COPY . .

# Create data directory
RUN mkdir -p /app/data

# Create a script to check for Ollama and run the application
RUN echo '#!/bin/bash \n\
# Wait for Ollama to be available \n\
echo "Checking connection to Ollama..." \n\
until $(curl --output /dev/null --silent --head --fail $OLLAMA_BASE_URL/api/tags); do \n\
    printf "." \n\
    sleep 5 \n\
done \n\
echo "Connection to Ollama established!" \n\n\
# Run setup \n\
python -m src.setup \n\n\
# Start the application \n\
exec python -m src.main \n\
' > /app/entrypoint.sh && chmod +x /app/entrypoint.sh

# Set the entrypoint
ENTRYPOINT ["/app/entrypoint.sh"]

# Note: This Dockerfile assumes Ollama is running externally.
# For a complete solution, you would need to either:
# 1. Run Ollama in a separate container and use Docker Compose to connect them
# 2. Include Ollama installation in this container (more complex and not recommended)
