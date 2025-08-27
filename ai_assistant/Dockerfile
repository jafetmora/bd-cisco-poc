# ===== Base con Miniconda =====
FROM continuumio/miniconda3:24.5.0-0 AS base
SHELL ["/bin/bash", "-lc"]
WORKDIR /app

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PYTHONPATH=/app \
    ENV_NAME=ai

# (Opcional) si compilas wheels nativos
RUN apt-get update && apt-get install -y --no-install-recommends build-essential \
    && rm -rf /var/lib/apt/lists/*

# Instala el env de conda primero para cachear
COPY requirements.txt /tmp/requirements.txt
RUN conda create -y -n $ENV_NAME python=3.11 && \
    conda run -n $ENV_NAME pip install --no-cache-dir -r /tmp/requirements.txt && \
    conda clean -afy

# ===== Development =====
FROM base AS dev
# Copia TODO el proyecto (ai_engine/, app/, scripts/, etc.)
COPY . /app
EXPOSE 8002
ENV ENV=development
# Para reload fluido, agrega 'watchfiles>=0.21' a requirements.txt
CMD ["conda", "run", "--no-capture-output", "-n", "ai", \
     "uvicorn", "ai_engine.app.run:app", "--host", "0.0.0.0", "--port", "8002", "--reload"]

# ===== Production =====
FROM base AS prod
COPY . /app
EXPOSE 8002
ENV ENV=production
CMD ["conda", "run", "--no-capture-output", "-n", "ai", \
     "uvicorn", "ai_engine.app.run:app", "--host", "0.0.0.0", "--port", "8002"]
