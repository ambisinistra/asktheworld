# AskTheWorld

Community-aligned AI: an LLM whose stances on topics are determined by on-chain community votes from [davinci.vote](https://davinci.vote) (Vocdoni protocol). The community votes; the AI follows.

ETHPrague hackathon proof-of-concept.

## How it works

1. Fetches all closed polls from the Vocdoni sequencer (`https://sequencer4.davinci.vote`).
2. For each usable poll (≥1 voter, results final), extracts the winning option.
3. Builds a single system prompt that tells the LLM the community's chosen stance on each topic.
4. Sends that system prompt + a user question to a local LLM via Ollama.

The current script (`asktheworld_v0_2.py`) uses a hardcoded test question:
> *"Should I use Zero-Knowledge proofs for my new privacy app?"*

Edit `main()` in the script to change it.

## Quick start (Docker, recommended)

**Requirements:** Docker. Optionally NVIDIA driver + `nvidia-container-toolkit` for GPU acceleration.

```bash
# Build the image (~2-5 min the first time)
docker build -t asktheworld .

# Run with GPU
docker run --rm --gpus all -v ollama-models:/root/.ollama asktheworld

# Run without GPU (CPU fallback — much slower)
docker run --rm -v ollama-models:/root/.ollama asktheworld
```

The first container start downloads the 7.4 GB model into the named volume `ollama-models`. Later runs reuse it (seconds, not minutes).

## Quick start (without Docker)

**Requirements:** Python 3.10+, [`uv`](https://docs.astral.sh/uv/), Ollama daemon running locally.

```bash
# One-time setup
ollama pull jaahas/qwen3.5-uncensored:9b
uv sync

# Run
uv run python asktheworld_v0_2.py
```

## Configuration

| Env var | Default | Effect |
|---|---|---|
| `OLLAMA_MODEL` | `jaahas/qwen3.5-uncensored:9b` | Which Ollama model tag to use |
| `OLLAMA_HOST` | unset (`http://localhost:11434`) | Point at a remote Ollama daemon |

Override at runtime:

```bash
docker run --rm -v ollama-models:/root/.ollama \
  -e OLLAMA_MODEL=llama3.1:8b asktheworld
```

## Files in this repo

| File | Purpose |
|---|---|
| `asktheworld_v0_2.py` | **Main script** — Ollama version |
| `asktheworld_v0_1.py` | Older OpenAI GPT-4 Turbo version (needs `OPENAI_API_KEY` in `.env`) |
| `asktheworld_v0_0.py` | Original Colab notebook, read-only reference |
| `Dockerfile` + `docker-entrypoint.sh` | Container packaging (pull-on-start pattern) |
| `.dockerignore` | Excludes `.venv`, secrets, old script versions from build context |
| `pyproject.toml` + `uv.lock` | Python dependencies, pinned versions |
| `CLAUDE.md` | Detailed project state, design decisions, and session history |
| `SUMMARY.md` | Original English project summary |

## Notes

- The Docker image base is `ollama/ollama:latest`, which already includes CUDA libs. The same image runs on CPU and GPU — only the `docker run` command differs (`--gpus all`).
- Ollama auto-detects available hardware. No code changes needed when switching between CPU and GPU.
- macOS users: Apple Silicon GPU **cannot** be passed into Docker containers. Mac Docker runs are always CPU.
- The script is a one-shot CLI: each `docker run` starts the daemon, ensures the model is available, runs the script once, and exits.
