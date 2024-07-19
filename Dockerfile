# Use a specific stable tag for the base image
FROM cypress/browsers:latest

# Set the port for the container
ARG PORT=443

# Install Python 3 and pip
RUN apt-get update && apt-get install -y \
    python3 \
    python3-pip \
    && apt-get clean \
    && rm -rf /var/lib/apt/lists/*

# Verify the installation of Python and pip
RUN python3 --version && pip3 --version

# Set the PATH for the installed pip packages
ENV PATH="/root/.local/bin:${PATH}"

# Copy requirements.txt and install dependencies
COPY requirements.txt .

# Install dependencies using pip
RUN python3 -m pip install --upgrade pip
RUN python3 -m pip install --user -r requirements.txt

# Copy the rest of the application code
COPY . .

# Set the entry point for the container
CMD ["uvicorn", "main:app", "--host", "0.0.0.0", "--port", "443"]
