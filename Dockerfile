FROM python:3.11-slim

WORKDIR /app

# System deps for asyncpg, lightgbm
RUN apt-get update && apt-get install -y --no-install-recommends \
    gcc libpq-dev && rm -rf /var/lib/apt/lists/*

# Python deps
COPY pyproject.toml ./
RUN pip install --no-cache-dir poetry && \
    poetry config virtualenvs.create false && \
    poetry install --only main

# App code
COPY src ./src
COPY config.yaml ./config.yaml
COPY prompts ./prompts

EXPOSE 8000 8501