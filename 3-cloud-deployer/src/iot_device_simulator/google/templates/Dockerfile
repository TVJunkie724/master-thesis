FROM python:3.11-slim

WORKDIR /app

# Install dependencies
COPY requirements.txt .
RUN pip install --no-cache-dir -r requirements.txt

# Copy source code
COPY src/ ./src/
COPY config.json .
COPY payloads.json .
COPY service_account.json .

# Set Python path
ENV PYTHONPATH=/app

CMD ["python", "-m", "src.main"]
