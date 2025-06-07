import os
import requests
from pathlib import Path
import pandas as pd
from . import storage, ratings

API_URL = "https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent"


def _gemini_request(prompt: str) -> str:
    key = os.getenv("GEMINI_API_KEY")
    if not key:
        raise RuntimeError("GEMINI_API_KEY not set")
    url = f"{API_URL}?key={key}"
    payload = {"contents": [{"parts": [{"text": prompt}]}]}
    r = requests.post(url, json=payload)
    r.raise_for_status()
    data = r.json()
    return data["candidates"][0]["content"]["parts"][0]["text"]


def generate_chapter(prompt: str, prev_uuid: str | None = None) -> str:
    """Generate a chapter with Gemini and store it."""
    text = _gemini_request(prompt)
    return storage.store_chapter_text(text, previous_uuid=prev_uuid)


def append_fork(csv_file: Path, position: int, prev_uuid: str, uuid: str) -> str:
    csv_file.parent.mkdir(parents=True, exist_ok=True)
    fork_uuid = storage.compute_forking_uuid(position, prev_uuid, uuid)
    if csv_file.exists():
        df = pd.read_csv(csv_file)
    else:
        df = pd.DataFrame(columns=["position", "prev_uuid", "uuid", "fork_uuid"])
    df = pd.concat([
        df,
        pd.DataFrame([{"position": position, "prev_uuid": prev_uuid, "uuid": uuid, "fork_uuid": fork_uuid}])
    ], ignore_index=True)
    df.to_csv(csv_file, index=False)
    return fork_uuid


def auto_vote(position: int, prev_uuid: str, voter: str) -> str:
    """Generate winner and loser chapters and record a vote."""
    winner_uuid = generate_chapter(f"Winner for position {position}", prev_uuid)
    loser_uuid = generate_chapter(f"Loser for position {position}", prev_uuid)
    fork_csv = Path("forking_path/auto.csv")
    append_fork(fork_csv, position, prev_uuid, winner_uuid)
    append_fork(fork_csv, position, prev_uuid, loser_uuid)
    ratings.record_vote(position, voter, winner_uuid, loser_uuid)
    return winner_uuid
