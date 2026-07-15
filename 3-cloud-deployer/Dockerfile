# syntax=docker/dockerfile:1.7

FROM python:3.11-slim@sha256:baf89808ec37adeaab83cec287adb4a2afa4a11c1d51e961c7ec737877e61af6 AS base

ARG TERRAFORM_VERSION=1.7.5
ARG TERRAFORM_SHA256_AMD64=3ff056b5e8259003f67fd0f0ed7229499cfb0b41f3ff55cc184088589994f7a5
ARG TERRAFORM_SHA256_ARM64=08631c385667dd28f03b3a3f77cb980393af4a2fcfc2236c148a678ad9150c8c

RUN set -eu; \
    apt-get update; \
    apt-get install -y --no-install-recommends ca-certificates curl unzip; \
    arch="$(dpkg --print-architecture)"; \
    case "$arch" in \
        amd64) terraform_arch="amd64"; terraform_sha="$TERRAFORM_SHA256_AMD64" ;; \
        arm64) terraform_arch="arm64"; terraform_sha="$TERRAFORM_SHA256_ARM64" ;; \
        *) echo "Unsupported architecture: $arch" >&2; exit 1 ;; \
    esac; \
    archive="terraform_${TERRAFORM_VERSION}_linux_${terraform_arch}.zip"; \
    curl -fsSL "https://releases.hashicorp.com/terraform/${TERRAFORM_VERSION}/${archive}" -o "/tmp/${archive}"; \
    echo "${terraform_sha}  /tmp/${archive}" | sha256sum -c -; \
    unzip "/tmp/${archive}" -d /usr/local/bin; \
    chmod 0755 /usr/local/bin/terraform; \
    rm -f "/tmp/${archive}"; \
    apt-get purge -y --auto-remove curl unzip; \
    rm -rf /var/lib/apt/lists/*

# Disable uamqp (C library) - use pure-Python AMQP for ARM64 compatibility
ENV AZURE_UAMQP_EXTENSION_ENABLED=False

WORKDIR /app
COPY requirements.txt /app/requirements.txt
COPY requirements.lock /app/requirements.lock
COPY constraints.txt /app/constraints.txt

RUN pip install --no-cache-dir \
    -r /app/requirements.txt \
    -c /app/requirements.lock \
    -c /app/constraints.txt


FROM base AS production

COPY . /app

RUN groupadd --gid 10001 deployer \
 && useradd --uid 10001 --gid 10001 --home-dir /app --no-create-home --shell /usr/sbin/nologin deployer \
 && mkdir -p /app/upload /var/lib/twin2multicloud-deployer/runtime-state \
 && chown -R deployer:deployer /app /var/lib/twin2multicloud-deployer \
 && chmod 0700 /var/lib/twin2multicloud-deployer/runtime-state

USER deployer

EXPOSE 8000

ENV PYTHONPATH=/app:/app/src

CMD ["uvicorn", "rest_api:app", "--host", "0.0.0.0", "--port", "8000"]


FROM production AS development

USER root
COPY requirements-dev.txt /app/requirements-dev.txt
RUN pip install --no-cache-dir \
    -r /app/requirements-dev.txt \
    -c /app/requirements.lock \
    -c /app/constraints.txt
USER deployer
