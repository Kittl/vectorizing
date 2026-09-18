# Use an official Python runtime as a parent image
FROM python:3.11-slim

# Install system dependencies shared with the development container.
COPY scripts/install_system_dependencies.sh /tmp/install_system_dependencies.sh
RUN bash /tmp/install_system_dependencies.sh && \
    rm /tmp/install_system_dependencies.sh && \
    rm -rf /var/lib/apt/lists/*

# Create a non-root user and group with specific IDs for consistency
RUN addgroup --gid 1001 appuser && \
    adduser --uid 1001 --gid 1001 --disabled-password --gecos "" appuser

# Set the working directory
WORKDIR /app

# Copy only requirements to leverage Docker cache. The test Compose service
# overrides this with the development requirements.
ARG REQUIREMENTS_FILE=prod.txt
COPY requirements/${REQUIREMENTS_FILE} /app/requirements.txt

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
