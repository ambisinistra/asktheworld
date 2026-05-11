# AskTheWorld

Community-aligned AI: an LLM whose stances on topics are determined by on-chain community votes from [davinci.vote](https://davinci.vote) (Vocdoni protocol). The community votes; the AI follows.

ETHPrague hackathon proof-of-concept.

## How it works

1. Fetches all closed polls from the Vocdoni sequencer (`https://sequencer4.davinci.vote`).
2. For each usable poll (≥1 voter, results final), extracts the winning option.
3. Builds a single system prompt that tells the LLM the community's chosen stance on each topic.
4. Sends that system prompt + a user question to a local LLM via Ollama.
5. The default entrypoint is a Flask web UI (`asktheworld_v0_4.py`) that also opens a public **ngrok** tunnel — the page is reachable both locally and from any browser on the internet via the printed `https://*.ngrok-free.app` URL. A pure-Flask variant without ngrok (`asktheworld_v0_3.py`) and a CLI variant (`asktheworld_v0_2.py`) are still around.

## Quick start (Docker, recommended)

**Requirements:** Docker, an [ngrok account](https://dashboard.ngrok.com/signup) (free), the auth token saved in `.env` as `NGROK_AUTH=...`. Optionally NVIDIA driver + `nvidia-container-toolkit` for GPU acceleration.

```bash
# Build the image (~2-5 min the first time)
docker build -t asktheworld .

# Run with GPU
docker run --rm --gpus all --env-file .env -p 5000:5000 -v ollama-models:/root/.ollama asktheworld

# Run without GPU (CPU fallback — much slower)
docker run --rm           --env-file .env -p 5000:5000 -v ollama-models:/root/.ollama asktheworld
```

Watch the container logs — once initialization finishes, you'll see:

```
============================================================
  Public URL:    https://abcd-1234.ngrok-free.app
  Forwarding to: http://localhost:5000
============================================================
```

That public URL works from any browser on any device. **http://localhost:5000** also works on the host machine (thanks to `-p 5000:5000`).

The first container start downloads the 7.4 GB model into the named volume `ollama-models`. Later runs reuse it (seconds, not minutes). The ngrok agent binary (~30 MB) is also downloaded on first run by `pyngrok`.

### Notes on the two ways the page is reachable

- **Public via ngrok**: traffic comes in from `*.ngrok-free.app` → ngrok cloud → ngrok agent inside the container → Flask. Works from anywhere, no port-forwarding needed.
- **Local via `-p 5000:5000`**: Docker publishes container port 5000 to host port 5000, so `localhost:5000` on the host hits Flask directly. Useful for fast local iteration and not depending on ngrok.

If port 5000 is busy on the host (common on macOS — AirPlay Receiver holds it), use `-p 8080:5000` instead. The ngrok URL is unaffected by host port choice.

### Without ngrok

If you don't want a public URL, drop `--env-file .env` and use `asktheworld_v0_3.py` instead — it's the same web UI without the tunnel. Easiest way: change the last line of `docker-entrypoint.sh` to launch `asktheworld_v0_3.py` (and remove the `NGROK_AUTH` check) and rebuild.

## Quick start (without Docker)

**Requirements:** Python 3.10+, [`uv`](https://docs.astral.sh/uv/), Ollama daemon running locally.

```bash
# One-time setup
ollama pull jaahas/qwen3.5-uncensored:9b
uv sync

# Run the web UI + public ngrok tunnel (needs NGROK_AUTH in .env)
uv run python asktheworld.py     # → http://localhost:5000 + https://*.ngrok-free.app

# Same web UI without ngrok
uv run python asktheworld_without_ngrok.py     # → http://localhost:5000

## Configuration

| Env var | Default | Effect |
|---|---|---|
| `OLLAMA_MODEL` | `jaahas/qwen3.5-uncensored:9b` | Which Ollama model tag to use |
| `OLLAMA_HOST` | unset (`http://localhost:11434`) | Point at a remote Ollama daemon |
| `NGROK_AUTH` | *(required for v0_4)* | ngrok agent auth token, from https://dashboard.ngrok.com/get-started/your-authtoken |
| `PORT` | `5000` | Local port Flask binds to (and ngrok forwards) |

Override at runtime:

```bash
docker run --rm -v ollama-models:/root/.ollama \
  -e OLLAMA_MODEL=llama3.1:8b asktheworld
```

## Files in this repo

| File | Purpose |
|---|---|
| `asktheworld.py` | **Main entrypoint** — v0_3 + automatic ngrok tunnel (needs `NGROK_AUTH`) |
| `asktheworld_without_ngrok.py` | Flask web UI on top of v0_2, no ngrok — used by v0_4 |
| `Dockerfile` + `docker-entrypoint.sh` | Container packaging (pull-on-start pattern) |
| `.dockerignore` | Excludes `.venv`, secrets, old script versions from build context |
| `pyproject.toml` + `uv.lock` | Python dependencies, pinned versions |
| `CLAUDE.md` | Detailed project state, design decisions, and session history |
| `SUMMARY.md` | Original English project summary |

## Notes

- The Docker image base is `ollama/ollama:latest`, which already includes CUDA libs. The same image runs on CPU and GPU — only the `docker run` command differs (`--gpus all`).
- Ollama auto-detects available hardware. No code changes needed when switching between CPU and GPU.
- macOS users: Apple Silicon GPU **cannot** be passed into Docker containers. Mac Docker runs are always CPU.
- The container is a long-running web service: each `docker run` starts the Ollama daemon, ensures the model is available, opens the ngrok tunnel, and serves the Flask UI on port 5000 until stopped (Ctrl+C or `docker stop`).
- Polls and the system prompt are fetched **once at startup** and cached in memory. To pick up new poll results, restart the container.
- **The ngrok URL is public.** Anyone with that URL can hit the LLM and consume your GPU/CPU time. Don't paste it in public channels for longer than you need.
- **The ngrok URL changes on every restart** on the free plan. Reserved domains require a paid ngrok plan.
- `gunicorn` is no longer used in Docker (v0_4 uses Flask's built-in server because the ngrok tunnel runs inside the same Python process). The dev-server warning in the logs is expected and harmless for a demo.
