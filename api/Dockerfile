# ----------- Base Stage -----------
FROM python:3.11-slim AS base
WORKDIR /app
ENV PYTHONDONTWRITEBYTECODE=1
ENV PYTHONUNBUFFERED=1
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
