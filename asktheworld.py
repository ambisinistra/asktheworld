import os
import atexit
import sys

from pyngrok import ngrok, conf

from asktheworld_without_ngrok import app, _state

PORT = int(os.environ.get("PORT", 5000))


def start_ngrok_tunnel():
    auth_token = os.environ.get("NGROK_AUTH")
    if not auth_token:
        print(
            "ERROR: NGROK_AUTH not set. Add it to .env or export it before running.",
            file=sys.stderr,
        )
        sys.exit(1)

    conf.get_default().auth_token = auth_token
    tunnel = ngrok.connect(PORT, "http")

    print()
    print("=" * 60)
    print(f"  Public URL:    {tunnel.public_url}")
    print(f"  Forwarding to: http://localhost:{PORT}")
    print("=" * 60)
    print()

    atexit.register(ngrok.kill)
    return tunnel


if __name__ == "__main__":
    if _state["error"]:
        print(f"Startup error: {_state['error']}", file=sys.stderr)
        sys.exit(1)

    start_ngrok_tunnel()
    app.run(host="0.0.0.0", port=PORT, use_reloader=False)
