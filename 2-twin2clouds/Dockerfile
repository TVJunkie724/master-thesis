FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y \
        ca-certificates \
        coreutils \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY ./requirements.txt /app/requirements.txt
COPY ./requirements.lock /app/requirements.lock

RUN pip install --no-cache-dir -r /app/requirements.txt -c /app/requirements.lock

COPY . /app

EXPOSE 8000

CMD ["uvicorn", "rest_api:app", "--host", "0.0.0.0", "--port", "8000"]
