#!/bin/bash
set -euo pipefail

MODEL="${OLLAMA_MODEL:-jaahas/qwen3.5-uncensored:9b}"

echo "==> Starting Ollama daemon..."
ollama serve > /tmp/ollama.log 2>&1 &

echo "==> Waiting for Ollama daemon to become ready..."
for i in {1..60}; do
    if ollama list >/dev/null 2>&1; then
        echo "==> Daemon ready."
        break
    fi
    sleep 1
done

if ! ollama list >/dev/null 2>&1; then
    echo "ERROR: Ollama daemon did not start within 60s. See /tmp/ollama.log:"
    cat /tmp/ollama.log
    exit 1
fi

echo "==> Ensuring model '$MODEL' is available (pull is a no-op if already cached)..."
ollama pull "$MODEL"

echo "==> Starting Flask web UI (asktheworld.py)..."
cd /app
exec uv run python asktheworld.py
