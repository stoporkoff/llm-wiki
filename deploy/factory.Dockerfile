FROM python:3.12-slim

ENV PYTHONDONTWRITEBYTECODE=1 \
    PYTHONUNBUFFERED=1 \
    PIP_DISABLE_PIP_VERSION_CHECK=1 \
    PIP_NO_CACHE_DIR=1

WORKDIR /app
COPY pyproject.toml README.md LICENSE ./
COPY src ./src
COPY agent_specs ./agent_specs
COPY wiki ./wiki
RUN python -m pip install ".[factory]"

EXPOSE 8000
CMD ["llm-wiki-factory"]
