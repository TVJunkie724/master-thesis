# syntax=docker/dockerfile:1.7

FROM python:3.11-slim@sha256:baf89808ec37adeaab83cec287adb4a2afa4a11c1d51e961c7ec737877e61af6 AS platform

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PORT=8080

WORKDIR /app
COPY platform/requirements.txt /app/requirements.txt
COPY platform/constraints.txt /app/constraints.txt
RUN pip install --no-cache-dir -r /app/requirements.txt -c /app/constraints.txt
COPY platform /app
COPY bridge_core.py /app/bridge_core.py

RUN groupadd --gid 10001 runtime \
 && useradd --uid 10001 --gid 10001 --home-dir /app --no-create-home --shell /usr/sbin/nologin runtime \
 && chown -R runtime:runtime /app

USER runtime
EXPOSE 8080
CMD ["gunicorn", "--bind", ":8080", "--workers", "1", "--threads", "8", "--timeout", "60", "app:app"]
