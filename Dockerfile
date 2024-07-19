# Use the Python 3.10 slim image as the base image
FROM python:3.10-slim

# Set the port for the container
ARG PORT=443

# Install necessary system packages and Google Chrome
RUN apt-get update && \
    apt-get install -y --no-install-recommends \
    curl \
    gnupg \
    ca-certificates \
    unzip \
    && curl -fsSL https://dl-ssl.google.com/linux/linux_signing_key.pub | apt-key add - && \
    sh -c 'echo "deb [arch=amd64] http://dl.google.com/linux/chrome/deb/ stable main" > /etc/apt/sources.list.d/google-chrome.list' && \
    apt-get update && \
    apt-get install -y --no-install-recommends \
    google-chrome-stable \
    && apt-get clean && \
    rm -rf /var/lib/apt/lists/*

# Install WebDriver Manager and necessary Python packages
RUN python -m pip install --upgrade pip && \
    pip install --no-cache-dir webdriver-manager

# Copy requirements.txt and install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set the entry point for the container
CMD ["gunicorn", "app:app", "--workers", "1", "--timeout", "1000", "--max-requests", "2000", "--bind", "0.0.0.0:443"]

# Expose the port
EXPOSE 443
