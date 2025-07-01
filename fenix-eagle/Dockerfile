FROM python:3.11-slim

# Set working directory
WORKDIR /app

# Install system dependencies
RUN apt-get update && apt-get install -y \
    gcc \
    g++ \
    make \
    libpq-dev \
    curl \
    wget \
    gnupg \
    && rm -rf /var/lib/apt/lists/*

# Install Node.js for Playwright
RUN curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
    && apt-get install -y nodejs

# Copy requirements and install Python dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Playwright installation disabled for simplified build
# RUN playwright install chromium
# RUN playwright install-deps chromium

# Copy application code
COPY src/ ./src/
COPY . .

# Create non-root user for security
RUN adduser --disabled-password --gecos '' --uid 1000 fenix && \
    chown -R fenix:fenix /app
USER fenix

# Expose port
EXPOSE 8001

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=5s --retries=3 \
    CMD curl -f http://localhost:8001/health || exit 1

# Start command
CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "8001", "--reload"]