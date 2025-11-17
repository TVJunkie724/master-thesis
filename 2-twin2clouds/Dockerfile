# STAGE 1 — Node builder (Clarity Core)
FROM node:18 AS clarity-builder

WORKDIR /build

RUN npm init -y
RUN npm install @clr/ui @cds/core --save


# STAGE 2 — Python runtime
FROM python:3.11-slim

RUN apt-get update \
    && apt-get install -y ca-certificates \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /app

COPY . /app

RUN mkdir -p /app/docs/cds
COPY --from=clarity-builder /build/node_modules/@cds/core /app/docs/cds

RUN pip install \
    requests \
    fastapi \
    uvicorn \
    colorlog \
    boto3 \
    azure-mgmt-consumption \
    azure-mgmt-resource \
    azure-identity \
    google-auth \
    google-auth-oauthlib \
    google-auth-httplib2 \
    google-api-python-client \
    google-cloud-billing

EXPOSE 8000

CMD ["uvicorn", "rest_api:app", "--host", "0.0.0.0", "--port", "8000"]
