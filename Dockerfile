# Use the Python 3.10 slim image as the base image
FROM python:3.10-slim

# Set the port for the container
ARG PORT=443

# Install necessary system packages and Python packages
RUN apt-get update && \
    apt-get install -y \
    curl \
    gnupg \
    ca-certificates \
    unzip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Add Google's APT repository
RUN curl -fsSL https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list'

# Install Google Chrome
RUN apt-get update && \
    apt-get install -y google-chrome-stable && \
    apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python -m pip install --upgrade pip

# Copy requirements.txt and install dependencies
COPY requirements.txt .

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

CMD ["gunicorn", "main:app", "--workers", "2", "--timeout", "1000", "--max-requests", "2000", "--bind", "0.0.0.0:8080"]

