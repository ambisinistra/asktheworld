import os
import requests
import ollama
from dotenv import load_dotenv

load_dotenv()

SEQUENCER_URL = "https://sequencer4.davinci.vote"
MIN_VOTERS = 1
DEFAULT_MODEL = "jaahas/qwen3.5-uncensored:9b"


def fetch_all_process_ids():
    response = requests.get(f"{SEQUENCER_URL}/processes")
    response.raise_for_status()
    return response.json()["processes"]


def fetch_process(process_id):
    response = requests.get(f"{SEQUENCER_URL}/processes/{process_id}")
    response.raise_for_status()
    return response.json()


def fetch_metadata(metadata_uri):
    response = requests.get(metadata_uri)
    response.raise_for_status()
    return response.json()


def is_usable(process):
    voters = int(process.get("votersCount", 0))
    result = process.get("result")
    accepting = process.get("isAcceptingVotes", True)
    return voters >= MIN_VOTERS and result is not None and not accepting


def parse_poll(process):
    metadata = fetch_metadata(process["metadataURI"])
    question = metadata["title"]["default"]
    choices = [c["title"]["default"] for c in metadata["questions"][0]["choices"]]

    result = [int(x) for x in process["result"]]
    total_votes = int(process["votersCount"])

    winning_index = result.index(max(result))
    winning_choice = choices[winning_index]
    winning_votes = result[winning_index]
    agreement_rate = winning_votes / total_votes if total_votes > 0 else 0

    return {
        "question": question,
        "chosen": winning_choice,
        "total_votes": total_votes,
        "agreement_rate": agreement_rate,
        "process_id": process["id"],
    }


def build_system_prompt(polls):
    stances = []
    for poll in polls:
        agreement_pct = poll["agreement_rate"] * 100
        voters = poll["total_votes"]
        stances.append(
            f'- "{poll["question"]}": the community chose "{poll["chosen"]}" '
            f"({agreement_pct:.0f}% agreement, {voters} voter{'s' if voters != 1 else ''})"
        )

    stances_text = "\n".join(stances)

    return (
        "You are a community-aligned AI. Your stances on the following topics are determined "
        "by on-chain democratic consensus — real people voted on these questions using a "
        "decentralized voting protocol, and you must reflect their collective will.\n\n"
        "Community stances:\n"
        f"{stances_text}\n\n"
        "When any of these topics comes up, align your response with the community's chosen position. "
        "If a topic is not covered above, respond based on your own judgment."
    )


def ask(client, model, system_prompt, user_question):
    response = client.chat(
        model=model,
        messages=[
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": user_question},
        ],
        options={"temperature": 0.7},
    )
    return response["message"]["content"]


def print_section(title):
    print(f"\n{'=' * 60}")
    print(f"  {title}")
    print('=' * 60)


def main():
    model = os.environ.get("OLLAMA_MODEL", DEFAULT_MODEL)
    host = os.environ.get("OLLAMA_HOST")
    client = ollama.Client(host=host) if host else ollama.Client()

    try:
        available = [m["model"] for m in client.list()["models"]]
    except Exception as e:
        print(f"Error: cannot reach Ollama daemon ({e}).")
        print("Make sure `ollama serve` is running, or set OLLAMA_HOST.")
        return

    if model not in available:
        print(f"Error: model '{model}' is not pulled locally.")
        print(f"Available models: {available}")
        print(f"Pull with: ollama pull {model}")
        return
    print(f"Using Ollama model: {model}")

    print_section("FETCHING POLLS")
    process_ids = fetch_all_process_ids()
    print(f"Found {len(process_ids)} processes total.\n")

    polls = []
    skipped = []
    for pid in process_ids:
        process = fetch_process(pid)
        if not is_usable(process):
            skipped.append(pid)
            print(f"  [ skip ] ...{pid[-8:]} — no votes or still open")
            continue
        poll = parse_poll(process)
        polls.append(poll)
        print(f"  [  ok  ] ...{pid[-8:]} — \"{poll['question']}\"")

    print_section("POLL DATA USED")
    if not polls:
        print("No usable polls found. Exiting.")
        return

    for i, poll in enumerate(polls, 1):
        print(f"\n  [{i}] {poll['question']}")
        print(f"       Chosen:     {poll['chosen']}")
        print(f"       Agreement:  {poll['agreement_rate'] * 100:.0f}%")
        print(f"       Voters:     {poll['total_votes']}")
        print(f"       Process ID: {poll['process_id']}")

    print_section("GENERATED SYSTEM PROMPT")
    system_prompt = build_system_prompt(polls)
    print(system_prompt)

    print_section("AI RESPONSE")
    user_question = "Should I use Zero-Knowledge proofs for my new privacy app?"
    print(f"User: {user_question}\n")
    print(ask(client, model, system_prompt, user_question))


if __name__ == "__main__":
    main()
