FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y \
        ca-certificates \
        coreutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app
COPY ./3-cloud-deployer/requirements.txt /app/requirements.txt

RUN pip install --no-cache-dir -r requirements.txt

EXPOSE 8000

ENV PYTHONPATH=/app:/app/src

CMD ["uvicorn", "rest_api:app", "--host", "0.0.0.0", "--port", "8000"]