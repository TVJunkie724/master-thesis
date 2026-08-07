# syntax=docker/dockerfile:1.7

FROM python:3.11-slim@sha256:baf89808ec37adeaab83cec287adb4a2afa4a11c1d51e961c7ec737877e61af6

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1

WORKDIR /app
COPY requirements.txt constraints.txt storage_mover.py /app/
RUN pip install --no-cache-dir -r /app/requirements.txt -c /app/constraints.txt \
 && groupadd --gid 10001 runtime \
 && useradd --uid 10001 --gid 10001 --home-dir /app --no-create-home --shell /usr/sbin/nologin runtime \
 && chown -R runtime:runtime /app

USER runtime
CMD ["python", "/app/storage_mover.py"]
