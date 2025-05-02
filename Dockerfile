FROM python:3.9-slim

WORKDIR /app

# Install required packages
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    python3-pip \
    python3-setuptools \
    && rm -rf /var/lib/apt/lists/*

# Install Python dependencies
RUN pip3 install --no-cache-dir \
    atlassian-python-api \
    fastapi \
    uvicorn

# Set environment variables
ENV JIRA_URL=https://central-authority.atlassian.net/
ENV JIRA_USERNAME=bmcgauley44@gmail.com
ENV JIRA_API_TOKEN=ATATT3xFfGF0rqA2w1IJ2XT0IHgT3VSjxP9c1r-WxYq783R7OMP4ommVeIUvF5otiXukaZH6T5ZHCPlA4aH_7MZkcM1ZgqSQDrGb8GxyCtTuVS968VKHnWyc8kN-3FOkqzhpeCjqHLOVocMXoh-sUX9whaAi6KxS-Kx8AXEV1Ko2YzJi2nPinbM=0BAD9FF4

# Copy MCP server code
COPY . .

# Expose port
EXPOSE 8080

# Start MCP server
CMD ["python3", "-m", "uvicorn", "main:app", "--host", "0.0.0.0", "--port", "8080"]
