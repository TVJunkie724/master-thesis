FROM python:3.11-slim

# Install Node.js (LTS)
RUN apt-get update && apt-get install -y curl \
 && curl -fsSL https://deb.nodesource.com/setup_18.x | bash - \
 && apt-get install -y nodejs \
 && apt-get clean

WORKDIR /app
COPY . /app

RUN pip install \
    requests \
    fastapi \
    uvicorn \
    boto3 \
    colorlog \
    google-auth google-auth-oauthlib google-auth-httplib2 google-api-python-client google-cloud-billing


# RUN npm install @aws-sdk/client-pricing

EXPOSE 8000

CMD ["uvicorn", "rest_api:app", "--host", "0.0.0.0", "--port", "8000"]
