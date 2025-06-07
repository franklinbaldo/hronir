import json
import uuid
from pathlib import Path

import pandas as pd

from hronir_encyclopedia import storage, ratings, gemini_util


def test_store_chapter_text(tmp_path):
    base = tmp_path / "hronirs"
    text = "hello world"
    uid = storage.store_chapter_text(text, base=base)
    chapter_dir = storage.uuid_to_path(uid, base)
    assert (chapter_dir / "index.md").read_text() == text
    meta = json.loads((chapter_dir / "metadata.json").read_text())
    assert meta["uuid"] == uid


def test_record_vote_multiple_entries(tmp_path):
    base = tmp_path / "ratings"
    for i in range(10):
        ratings.record_vote(1, f"voter{i}", f"winner{i}", f"loser{i}", base=base)
    df = pd.read_csv(base / "position_001.csv")
    assert len(df) == 10
    assert set(df["voter"]) == {f"voter{i}" for i in range(10)}
    assert df["uuid"].is_unique


def test_auto_vote_records_votes(monkeypatch, tmp_path):
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("GEMINI_API_KEY", "dummy")
    counter = {"i": 0}

    def fake_request(prompt: str) -> str:
        counter["i"] += 1
        return f"chapter {counter['i']}"

    monkeypatch.setattr(gemini_util, "_gemini_request", fake_request)

    for _ in range(10):
        gemini_util.auto_vote(
            position=1,
            prev_uuid="00000000-0000-0000-0000-000000000000",
            voter=str(uuid.uuid4()),
        )

    df = pd.read_csv(Path("ratings/position_001.csv"))
    assert len(df) == 10

