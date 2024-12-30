# Use an official Python runtime as the base image
FROM python:3.9-slim

# Set the working directory in the container
WORKDIR /agents
ENV PYTHONPATH=/agents
# Install system dependencies for Selenium
RUN apt-get update && apt-get install -y \
    wget \
    curl \
    xvfb \
    firefox-esr \
    && rm -rf /var/lib/apt/lists/*

# Install Geckodriver for Selenium
RUN wget https://github.com/mozilla/geckodriver/releases/download/v0.33.0/geckodriver-v0.33.0-linux64.tar.gz \
    && tar -xvzf geckodriver-v0.33.0-linux64.tar.gz -C /usr/local/bin \
    && rm geckodriver-v0.33.0-linux64.tar.gz

# Copy the Python dependencies file_manager.py
COPY requirements1.txt /agents/

# Install Python dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Set the Flask app environment variables
ENV FLASK_APP=agents/Server/app.py
ENV FLASK_ENV=production

# Expose the Flask application's port
EXPOSE 5002

# Command to run the Flask application
CMD ["flask", "run", "--host=0.0.0.0", "--port=5002"]

