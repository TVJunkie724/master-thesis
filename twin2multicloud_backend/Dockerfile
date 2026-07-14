FROM python:3.11-slim@sha256:baf89808ec37adeaab83cec287adb4a2afa4a11c1d51e961c7ec737877e61af6 AS base

WORKDIR /app

COPY requirements.txt requirements.lock ./
RUN pip install --no-cache-dir \
    -r requirements.txt \
    -c requirements.lock


FROM base AS production

COPY . .

EXPOSE 5005

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5005"]


FROM production AS development

COPY requirements-dev.txt ./
RUN pip install --no-cache-dir \
    -r requirements-dev.txt \
    -c requirements.lock

CMD ["uvicorn", "src.main:app", "--host", "0.0.0.0", "--port", "5005", "--reload"]
