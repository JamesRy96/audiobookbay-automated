# Use an official Python runtime as a parent image
FROM python:3.10-slim

# Set the working directory in the container
WORKDIR /app

# Copy the app directory contents into the container
COPY /app /app

# Install any necessary dependencies
RUN pip install --no-cache-dir -r /app/requirements.txt
RUN apt-get update && apt-get install -y curl && rm -rf /var/lib/apt/lists/*

# Healthcheck
HEALTHCHECK CMD curl -sf http://127.0.0.1:5078 || exit 1

# Expose the port the app runs on
EXPOSE 5078

# Define the command to run the application
CMD ["python", "app.py"]
