FROM python:3.11-slim@sha256:baf89808ec37adeaab83cec287adb4a2afa4a11c1d51e961c7ec737877e61af6 AS base

WORKDIR /app

COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir \
    -r requirements.txt \
    -c requirements.lock


FROM base AS production

RUN groupadd --gid 10002 management \
 && useradd --uid 10002 --gid 10002 --home-dir /var/lib/twin2multicloud-management --no-create-home --shell /usr/sbin/nologin management \
 && mkdir -p /var/lib/twin2multicloud-management/data /var/lib/twin2multicloud-management/uploads \
 && chown -R management:management /var/lib/twin2multicloud-management \
 && chmod 0700 /var/lib/twin2multicloud-management/data /var/lib/twin2multicloud-management/uploads

COPY . .

ENV DATABASE_URL=sqlite:////var/lib/twin2multicloud-management/data/app.db \
    UPLOAD_DIR=/var/lib/twin2multicloud-management/uploads \
    HOME=/var/lib/twin2multicloud-management \
    PYTHONDONTWRITEBYTECODE=1

USER management

EXPOSE 5005

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5005"]


FROM production AS development

USER root
COPY requirements-dev.txt ./
RUN pip install --no-cache-dir \
    -r requirements-dev.txt \
    -c requirements.lock
USER management

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5005", "--reload"]
