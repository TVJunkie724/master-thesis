FROM python:3.11-slim

WORKDIR /app

# Copy only code and dependencies, never device credentials.
COPY requirements.txt .
COPY src/ ./src/

# Install dependencies
RUN pip install --no-cache-dir -r requirements.txt

# Run main.py
CMD ["python", "src/main.py", "--config", "/app/config.json"]
