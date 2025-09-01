# ----------- Base Stage -----------
FROM python:3.11-slim AS base

WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1

RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates curl && \
    rm -rf /var/lib/apt/lists/*

ARG AWS_REGION=us-east-2
RUN mkdir -p /app/certs && \
    curl -fsSL "https://truststore.pki.rds.amazonaws.com/${AWS_REGION}/${AWS_REGION}-bundle.pem" \
        -o /app/certs/rds-ca.pem && \
    chmod 0644 /app/certs/rds-ca.pem

RUN cp /app/certs/rds-ca.pem /usr/local/share/ca-certificates/rds-ca.crt && update-ca-certificates

ENV RDS_CA_BUNDLE=/app/certs/rds-ca.pem

COPY requirements.txt ./
RUN pip install --upgrade pip && \
    pip install --no-cache-dir -r requirements.txt

# ----------- Development Stage -----------
FROM base AS dev
COPY . /app/api
RUN pip install --no-cache-dir debugpy
EXPOSE 8000
ENV ENV=development
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000", "--reload"]

# ----------- Production Stage -----------
FROM base AS prod
COPY . /app/api
EXPOSE 8000
ENV ENV=production
CMD ["uvicorn", "api.main:app", "--host", "0.0.0.0", "--port", "8000"]
