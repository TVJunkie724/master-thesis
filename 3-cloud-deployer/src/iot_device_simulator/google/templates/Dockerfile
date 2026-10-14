FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
# Device configuration, payloads and certificates are mounted read-only at runtime.

# Set Python path
ENV PYTHONPATH=/app

CMD ["python", "-m", "src.main", "--config", "/app/config.json"]
