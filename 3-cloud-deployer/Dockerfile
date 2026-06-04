FROM python:3.11-slim

# Install Node.js (LTS) and system dependencies
ARG NODE_MAJOR=22
RUN apt-get update && apt-get install -y curl unzip \
 && curl -fsSL "https://deb.nodesource.com/setup_${NODE_MAJOR}.x" | bash - \
 && apt-get install -y nodejs \
 && apt-get clean

# Install Terraform (architecture-aware for ARM64/AMD64 compatibility)
RUN ARCH=$(dpkg --print-architecture) && \
    if [ "$ARCH" = "arm64" ]; then TF_ARCH="arm64"; else TF_ARCH="amd64"; fi && \
    curl -fsSL "https://releases.hashicorp.com/terraform/1.7.5/terraform_1.7.5_linux_${TF_ARCH}.zip" -o /tmp/terraform.zip \
 && unzip /tmp/terraform.zip -d /usr/local/bin/ \
 && rm /tmp/terraform.zip \
 && chmod +x /usr/local/bin/terraform

# Disable uamqp (C library) - use pure-Python AMQP for ARM64 compatibility
ENV AZURE_UAMQP_EXTENSION_ENABLED=False

WORKDIR /app
COPY requirements.txt /app/requirements.txt
COPY constraints.txt /app/constraints.txt
COPY . /app

# Install with constraints to block uamqp
RUN pip install -r /app/requirements.txt -c /app/constraints.txt

EXPOSE 8000

ENV PYTHONPATH=/app:/app/src

CMD ["uvicorn", "rest_api:app", "--host", "0.0.0.0", "--port", "8000"]
