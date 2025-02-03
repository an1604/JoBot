# Use Python with better package compatibility
FROM python:3.9-slim

# Set working directory
WORKDIR /agents
ENV PYTHONPATH=/agents

RUN apt-get update && apt-get install -y --no-install-recommends \
    wget \
    curl \
    xvfb \
    firefox-esr \
    && rm -rf /var/lib/apt/lists/*

# Download and install Geckodriver manually
RUN GECKO_VERSION=0.33.0 && \
    wget -q "https://github.com/mozilla/geckodriver/releases/download/v$GECKO_VERSION/geckodriver-v$GECKO_VERSION-linux64.tar.gz" -O /tmp/geckodriver.tar.gz && \
    tar -xzf /tmp/geckodriver.tar.gz -C /usr/local/bin && \
    rm /tmp/geckodriver.tar.gz

# Alternative: Manually install Geckodriver if a specific version is required
# RUN wget https://github.com/mozilla/geckodriver/releases/download/v0.33.0/geckodriver-v0.33.0-linux64.tar.gz \
#     && tar -xvzf geckodriver-v0.33.0-linux64.tar.gz -C /usr/local/bin \
#     && rm geckodriver-v0.33.0-linux64.tar.gz

# Copy and install Python dependencies
COPY requirements.txt /agents/
RUN pip install --no-cache-dir -r requirements.txt

# Copy the entire project
COPY . .

# Set Flask environment variables
ENV FLASK_APP=agents/Server/app.py
ENV FLASK_ENV=production

# Expose Flask application port
EXPOSE 5002

# Default command to run the Flask app
CMD ["flask", "run", "--host=0.0.0.0", "--port=5002"]

