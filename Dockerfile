# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install necessary packages
RUN apt-get update -y && apt-get install -y \
    wget \
    build-essential \
    python3-dev \
    libagg-dev \
    libpotrace-dev \
    pkg-config \
    libgl1 \
    --no-install-recommends && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user and group with specific IDs for consistency
RUN addgroup --gid 1001 appuser && \
    adduser --uid 1001 --gid 1001 --disabled-password --gecos "" appuser

# Set the working directory
WORKDIR /app

# Copy only requirements to leverage Docker cache
COPY requirements/dev.txt /app/requirements.txt

# Install Python dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt

# Copy the rest of the application code
COPY . /app

# Change ownership of the application files
RUN chown -R appuser:appuser /app

# Switch to the non-root user
USER appuser

# Set environment variables
ENV PORT=5000

# Expose the port
EXPOSE $PORT

# Define the command to run the application
CMD ["gunicorn", "-w", "4", "vectorizing:create_app()", "--timeout", "0", "-b", "0.0.0.0:5000"]
