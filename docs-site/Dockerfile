FROM python:3.12-slim

WORKDIR /docs

RUN pip install --no-cache-dir \
    mkdocs==1.6.1 \
    mkdocs-material==9.5.49 \
    pymdown-extensions==10.21.3

EXPOSE 8000

CMD ["mkdocs", "serve", "--dev-addr=0.0.0.0:8000"]
