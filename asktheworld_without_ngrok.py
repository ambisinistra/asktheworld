import json
import os
import ollama
from flask import Flask, Response, request, render_template_string, stream_with_context
from dotenv import load_dotenv

from asktheworld_cli import (
    fetch_all_process_ids,
    fetch_process,
    is_usable,
    parse_poll,
    build_system_prompt,
    ask_stream,
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
    button[disabled] { background: #aaa; cursor: not-allowed; }
    .qa { margin: 1.5em 0; }
    .question { font-weight: 600; margin-bottom: 0.5em; }
    .thinking { background: #fafaf2; padding: 1em; border-left: 3px solid #c9a227;
                white-space: pre-wrap; border-radius: 0 4px 4px 0;
                color: #6b5d1f; font-style: italic; font-size: 0.92em;
                margin-bottom: 0.75em; }
    .thinking-label { display: block; font-weight: 600; font-style: normal;
                      color: #8a7a2c; margin-bottom: 0.4em; font-size: 0.85em;
                      letter-spacing: 0.05em; text-transform: uppercase; }
    .answer { background: #f4f4f4; padding: 1em; border-left: 3px solid #4a90e2;
              white-space: pre-wrap; border-radius: 0 4px 4px 0; }
    .answer-label { display: block; font-weight: 600; color: #2a6fc4;
                    margin-bottom: 0.4em; font-size: 0.85em;
                    letter-spacing: 0.05em; text-transform: uppercase; }
    details { margin-top: 2em; color: #555; }
    summary { cursor: pointer; padding: 0.4em 0; }
    pre { white-space: pre-wrap; background: #fafafa; padding: 1em;
          border: 1px solid #eee; border-radius: 4px; font-size: 0.9em; }
    .error { color: #900; padding: 1em; border: 1px solid #c66;
             background: #fee; border-radius: 4px; }
    .cursor::after { content: "▍"; animation: blink 1s steps(2) infinite;
                     color: #888; margin-left: 1px; }
    @keyframes blink { 50% { opacity: 0; } }
  </style>
</head>
<body>
  <h1>AskTheWorld</h1>
  <p class="sub">An AI whose stances are decided by on-chain community votes (davinci.vote)</p>

  {% if error %}
    <div class="error">{{ error }}</div>
  {% else %}
    <form id="ask-form">
      <input id="question" type="text" name="question" placeholder="Ask anything..."
             autofocus required autocomplete="off">
      <button id="submit-btn" type="submit">Ask</button>
    </form>

    <div id="qa" class="qa" style="display: none;">
      <div id="question-display" class="question"></div>
      <div id="thinking-block" style="display: none;">
        <span class="thinking-label">Thinking…</span>
        <div id="thinking" class="thinking"></div>
      </div>
      <div id="answer-block" style="display: none;">
        <span class="answer-label">Answer</span>
        <div id="answer" class="answer"></div>
      </div>
    </div>

    <details>
      <summary>Community stances used ({{ polls|length }} polls — model: {{ model }})</summary>
      <pre>{{ system_prompt }}</pre>
    </details>

    <script>
      const form = document.getElementById('ask-form');
      const input = document.getElementById('question');
      const btn = document.getElementById('submit-btn');
      const qa = document.getElementById('qa');
      const questionDisplay = document.getElementById('question-display');
      const thinkingBlock = document.getElementById('thinking-block');
      const thinkingEl = document.getElementById('thinking');
      const answerBlock = document.getElementById('answer-block');
      const answerEl = document.getElementById('answer');

      form.addEventListener('submit', async (e) => {
        e.preventDefault();
        const question = input.value.trim();
        if (!question) return;

        btn.disabled = true;
        qa.style.display = 'block';
        questionDisplay.textContent = 'You asked: ' + question;
        thinkingBlock.style.display = 'none';
        thinkingEl.textContent = '';
        thinkingEl.classList.remove('cursor');
        answerBlock.style.display = 'none';
        answerEl.textContent = '';
        answerEl.classList.remove('cursor');

        try {
          const resp = await fetch('/ask', {
            method: 'POST',
            headers: { 'Content-Type': 'application/json' },
            body: JSON.stringify({ question }),
          });
          if (!resp.ok || !resp.body) {
            answerBlock.style.display = 'block';
            answerEl.textContent = 'Request failed: ' + resp.status;
            return;
          }

          const reader = resp.body.getReader();
          const decoder = new TextDecoder();
          let buf = '';
          let activeEl = null;

          while (true) {
            const { value, done } = await reader.read();
            if (done) break;
            buf += decoder.decode(value, { stream: true });

            let sep;
            while ((sep = buf.indexOf('\\n\\n')) !== -1) {
              const event = buf.slice(0, sep);
              buf = buf.slice(sep + 2);

              const dataLines = event.split('\\n')
                .filter(l => l.startsWith('data: '))
                .map(l => l.slice(6));
              if (!dataLines.length) continue;

              let payload;
              try { payload = JSON.parse(dataLines.join('\\n')); }
              catch { continue; }

              if (payload.kind === 'thinking') {
                if (thinkingBlock.style.display === 'none') {
                  thinkingBlock.style.display = 'block';
                  thinkingEl.classList.add('cursor');
                }
                if (activeEl && activeEl !== thinkingEl) activeEl.classList.remove('cursor');
                activeEl = thinkingEl;
                thinkingEl.textContent += payload.text;
              } else if (payload.kind === 'content') {
                if (answerBlock.style.display === 'none') {
                  answerBlock.style.display = 'block';
                  answerEl.classList.add('cursor');
                }
                if (activeEl && activeEl !== answerEl) activeEl.classList.remove('cursor');
                activeEl = answerEl;
                answerEl.textContent += payload.text;
              } else if (payload.kind === 'error') {
                answerBlock.style.display = 'block';
                answerEl.textContent = 'Error: ' + payload.text;
              } else if (payload.kind === 'done') {
                if (activeEl) activeEl.classList.remove('cursor');
              }
            }
          }
          if (activeEl) activeEl.classList.remove('cursor');
        } catch (err) {
          answerBlock.style.display = 'block';
          answerEl.textContent = 'Error: ' + err.message;
        } finally {
          btn.disabled = false;
        }
      });
    </script>
  {% endif %}
</body>
</html>
"""


@app.route("/", methods=["GET"])
def index():
    if _state["error"]:
        return render_template_string(PAGE, error=_state["error"])
    return render_template_string(
        PAGE,
        error=None,
        polls=_state["polls"],
        system_prompt=_state["system_prompt"],
        model=_state["model"],
    )


@app.route("/ask", methods=["POST"])
def ask_endpoint():
    if _state["error"]:
        return Response(
            f'data: {json.dumps({"kind": "error", "text": _state["error"]})}\n\n',
            mimetype="text/event-stream",
        )

    payload = request.get_json(silent=True) or {}
    question = (payload.get("question") or "").strip()
    if not question:
        return Response(
            f'data: {json.dumps({"kind": "error", "text": "empty question"})}\n\n',
            mimetype="text/event-stream",
        )

    def generate():
        try:
            for kind, text in ask_stream(
                _state["client"],
                _state["model"],
                _state["system_prompt"],
                question,
            ):
                yield f"data: {json.dumps({'kind': kind, 'text': text})}\n\n"
            yield f"data: {json.dumps({'kind': 'done'})}\n\n"
        except Exception as e:
            yield f"data: {json.dumps({'kind': 'error', 'text': str(e)})}\n\n"

    return Response(
        stream_with_context(generate()),
        mimetype="text/event-stream",
        headers={"Cache-Control": "no-cache", "X-Accel-Buffering": "no"},
    )


initialize()


if __name__ == "__main__":
    app.run(host="0.0.0.0", port=5000)
