FROM ollama/ollama:latest

COPY --from=ghcr.io/astral-sh/uv:latest /uv /uvx /bin/

RUN apt-get update && \
    apt-get install -y --no-install-recommends \
        python3 \
        python3-venv \
        curl \
        ca-certificates && \
    rm -rf /var/lib/apt/lists/*

ENV PYTHONUNBUFFERED=1

WORKDIR /app

COPY pyproject.toml uv.lock ./
RUN uv sync --frozen --no-install-project

COPY asktheworld.py asktheworld_without_ngrok.py asktheworld_cli.py ./
COPY docker-entrypoint.sh /usr/local/bin/docker-entrypoint.sh
RUN chmod +x /usr/local/bin/docker-entrypoint.sh

VOLUME ["/root/.ollama"]
EXPOSE 5000

ENTRYPOINT ["/usr/local/bin/docker-entrypoint.sh"]
