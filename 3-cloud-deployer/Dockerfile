FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y \
        ca-certificates \
        coreutils \
        wget \
        unzip \
    && rm -rf /var/lib/apt/lists/*

# Install Terraform CLI
RUN wget -q https://releases.hashicorp.com/terraform/1.6.6/terraform_1.6.6_linux_amd64.zip \
    && unzip terraform_1.6.6_linux_amd64.zip -d /usr/local/bin/ \
    && rm terraform_1.6.6_linux_amd64.zip \
    && chmod +x /usr/local/bin/terraform

WORKDIR /app

COPY . /app
COPY ./3-cloud-deployer/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

ENV PYTHONPATH=/app:/app/src

CMD ["uvicorn", "rest_api:app", "--host", "0.0.0.0", "--port", "8000"]