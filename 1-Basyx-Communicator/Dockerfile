# Use official Python image
FROM python:3.12-slim

# Set working directory inside container
WORKDIR /app

# Copy Python script into container
COPY . .

# Install dependencies
RUN pip install --no-cache-dir \
    requests \
    basyx-python-sdk

# Run script when container starts
# CMD ["python", "get_aas_data.py"]
