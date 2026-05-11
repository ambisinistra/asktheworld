import os
import ollama
from flask import Flask, request, render_template_string
from dotenv import load_dotenv

from asktheworld_v0_2 import (
    fetch_all_process_ids,
    fetch_process,
    is_usable,
    parse_poll,
    build_system_prompt,
    ask,
    DEFAULT_MODEL,
)

load_dotenv()

app = Flask(__name__)

_state = {
    "client": None,
    "model": None,
    "polls": [],
    "system_prompt": "",
    "error": None,
}


def initialize():
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
    host = os.environ.get("OLLAMA_HOST")
    client = ollama.Client(host=host) if host else ollama.Client()

    try:
        available = [m["model"] for m in client.list()["models"]]
    except Exception as e:
        _state["error"] = (
            f"Cannot reach Ollama daemon: {e}. "
            "Make sure `ollama serve` is running, or set OLLAMA_HOST."
        )
        return

    if model not in available:
        _state["error"] = (
            f"Model '{model}' is not pulled locally. "
            f"Available: {available}. Pull with: ollama pull {model}"
        )
        return

    process_ids = fetch_all_process_ids()
    polls = []
    for pid in process_ids:
        process = fetch_process(pid)
        if is_usable(process):
            polls.append(parse_poll(process))

    if not polls:
        _state["error"] = "No usable polls found on the sequencer."
        return

    _state["client"] = client
    _state["model"] = model
    _state["polls"] = polls
    _state["system_prompt"] = build_system_prompt(polls)


PAGE = """
<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <title>AskTheWorld</title>
  <style>
    body { font-family: -apple-system, BlinkMacSystemFont, sans-serif;
           max-width: 720px; margin: 2em auto; padding: 0 1em; color: #222; }
    h1 { margin-bottom: 0.1em; }
    .sub { color: #666; margin-top: 0; }
    form { margin: 1.5em 0; display: flex; gap: 0.5em; }
    input[type=text] { flex: 1; padding: 0.6em; font-size: 1em;
                       border: 1px solid #ccc; border-radius: 4px; }
    button { padding: 0.6em 1.2em; font-size: 1em; cursor: pointer;
             background: #4a90e2; color: white; border: none; border-radius: 4px; }
    button:hover { background: #357ab8; }
    .qa { margin: 1.5em 0; }
    .question { font-weight: 600; margin-bottom: 0.5em; }
    .answer { background: #f4f4f4; padding: 1em; border-left: 3px solid #4a90e2;
              white-space: pre-wrap; border-radius: 0 4px 4px 0; }
    details { margin-top: 2em; color: #555; }
    summary { cursor: pointer; padding: 0.4em 0; }
    pre { white-space: pre-wrap; background: #fafafa; padding: 1em;
          border: 1px solid #eee; border-radius: 4px; font-size: 0.9em; }
    .error { color: #900; padding: 1em; border: 1px solid #c66;
             background: #fee; border-radius: 4px; }
  </style>
</head>
<body>
  <h1>AskTheWorld</h1>
  <p class="sub">An AI whose stances are decided by on-chain community votes (davinci.vote)</p>

  {% if error %}
    <div class="error">{{ error }}</div>
  {% else %}
    <form method="post">
      <input type="text" name="question" placeholder="Ask anything..."
             value="{{ question or '' }}" autofocus required>
      <button type="submit">Ask</button>
    </form>

    {% if answer %}
      <div class="qa">
        <div class="question">You asked: {{ question }}</div>
        <div class="answer">{{ answer }}</div>
      </div>
    {% endif %}

    <details>
      <summary>Community stances used ({{ polls|length }} polls — model: {{ model }})</summary>
      <pre>{{ system_prompt }}</pre>
    </details>
  {% endif %}
</body>
</html>
"""


@app.route("/", methods=["GET", "POST"])
def index():
    if _state["error"]:
        return render_template_string(PAGE, error=_state["error"])

    question = None
    answer = None
    if request.method == "POST":
        question = request.form.get("question", "").strip()
        if question:
            answer = ask(
                _state["client"],
                _state["model"],
                _state["system_prompt"],
                question,
            )

    return render_template_string(
        PAGE,
        error=None,
        question=question,
        answer=answer,
        polls=_state["polls"],
        system_prompt=_state["system_prompt"],
        model=_state["model"],
    )


initialize()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
