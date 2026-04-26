FROM python:3.12-slim

WORKDIR /docs

RUN pip install --no-cache-dir mkdocs==1.6.1

EXPOSE 8000

CMD ["mkdocs", "serve", "--dev-addr=0.0.0.0:8000"]
