FROM python:3.11-slim

# Install Node.js (LTS) and system dependencies
RUN apt-get update && apt-get install -y curl unzip \
 && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
 && apt-get install -y nodejs \
 && apt-get clean

# Install Terraform (direct download)
RUN curl -fsSL https://releases.hashicorp.com/terraform/1.7.5/terraform_1.7.5_linux_amd64.zip -o /tmp/terraform.zip \
 && unzip /tmp/terraform.zip -d /usr/local/bin/ \
 && rm /tmp/terraform.zip \
 && chmod +x /usr/local/bin/terraform

WORKDIR /app
COPY ./3-cloud-deployer/requirements.txt /app/requirements.txt
COPY ./3-cloud-deployer /app

RUN pip install -r requirements.txt

EXPOSE 8000

ENV PYTHONPATH=/app:/app/src

CMD ["uvicorn", "rest_api:app", "--host", "0.0.0.0", "--port", "8000"]