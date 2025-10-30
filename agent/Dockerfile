# AgentCore Runtime Container for LINE Agent Secretary
# ARM64 architecture for AWS compatibility

FROM --platform=linux/arm64 python:3.12-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    && rm -rf /var/lib/apt/lists/*

# Copy requirements first for better caching
COPY requirements.txt /app/

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy all agent files
COPY . /app/agent/

# Expose port 8080 (required by AgentCore Runtime)
EXPOSE 8080

# Health check using the /ping endpoint
HEALTHCHECK --interval=30s --timeout=3s --start-period=5s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8080/ping')"

# Run the AgentCore Runtime server
CMD ["python", "-m", "agent.server"]
