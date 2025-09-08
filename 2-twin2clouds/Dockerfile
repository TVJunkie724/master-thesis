FROM python:3.11-slim

# Install Node.js (LTS)
RUN apt-get update && apt-get install -y curl \
 && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
 && apt-get install -y nodejs \
 && apt-get clean

WORKDIR /app
COPY . /app

RUN pip install fastapi uvicorn

EXPOSE 8000

CMD ["uvicorn", "api:app", "--host", "0.0.0.0", "--port", "8000"]
