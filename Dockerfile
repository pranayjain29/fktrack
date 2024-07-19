# Use a specific stable tag for the base image
FROM cypress/browsers:latest
FROM python:3.10-slim

# Set the port for the container
ARG PORT=443

# Install necessary system packages and Python packages
RUN apt-get update && \
    apt-get install -y \
    gcc \
    libffi-dev \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Upgrade pip
RUN python -m pip install --upgrade pip

# Copy requirements.txt and install dependencies
COPY requirements.txt .

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set the entry point for the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "443"]

