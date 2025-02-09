# Use an official Python runtime as the base image
FROM python:3.12-slim

# Set environment variables for Python
ENV PYTHONUNBUFFERED=1

# Create and switch to the working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y gcc libpq-dev

# Copy the project files to the Docker container
COPY . .

# Install dependencies from requirements.txt
RUN pip install --no-cache-dir -r requirements.txt

# Expose the port the app runs on
EXPOSE 8080

# Start the application using Gunicorn
CMD ["gunicorn", "-w", "4", "-b", "0.0.0.0:8080", "application:app"]
