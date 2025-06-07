import json
import uuid
import subprocess
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


def test_clean_functions(tmp_path):
    base = tmp_path / "hronirs"
    uid1 = storage.store_chapter_text("good", base=base)
    uid2 = storage.store_chapter_text("better", base=base)

    fake = storage.store_chapter_text("fake", base=base)
    fake_dir = storage.uuid_to_path(fake, base)
    (fake_dir / "index.md").write_text("tampered")

    assert storage.chapter_exists(fake, base)
    removed = storage.purge_fake_hronirs(base=base)
    assert removed == 1
    assert storage.chapter_exists(uid1, base)
    assert not storage.chapter_exists(fake, base)

    fork_csv = tmp_path / "fork.csv"
    valid_row = {
        "position": 1,
        "prev_uuid": uid1,
        "uuid": uid2,
        "fork_uuid": storage.compute_forking_uuid(1, uid1, uid2),
    }
    invalid_row = {
        "position": 1,
        "prev_uuid": uid1,
        "uuid": fake,
        "fork_uuid": "bad",
    }
    pd.DataFrame([valid_row, invalid_row]).to_csv(fork_csv, index=False)
    removed = storage.purge_fake_forking_csv(fork_csv, base=base)
    assert removed == 1
    df = pd.read_csv(fork_csv)
    assert len(df) == 1

    rating_csv = tmp_path / "rating.csv"
    rows = [
        {
            "uuid": str(uuid.uuid4()),
            "voter": "fork1",
            "winner": uid1,
            "loser": uid2,
        },
        {
            "uuid": str(uuid.uuid4()),
            "voter": "fork1",
            "winner": uid1,
            "loser": uid2,
        },
        {
            "uuid": str(uuid.uuid4()),
            "voter": "fork2",
            "winner": uid1,
            "loser": fake,
        },
    ]
    pd.DataFrame(rows).to_csv(rating_csv, index=False)
    removed = storage.purge_fake_votes_csv(rating_csv, base=base)
    assert removed == 2
    df = pd.read_csv(rating_csv)
    assert len(df) == 1


def test_clean_git_prunes_from_branch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], check=True)

    base = Path("hronirs")
    uid = storage.store_chapter_text("data", base=base)
    bad = storage.store_chapter_text("bad", base=base)
    bad_dir = storage.uuid_to_path(bad, base)
    (bad_dir / "index.md").write_text("tampered")

    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-m", "init"], check=True)

    from hronir_encyclopedia import cli
    cli.main(["clean", "--git"])

    ls_files = subprocess.check_output(["git", "ls-files"], text=True)
    assert str(bad_dir / "index.md") not in ls_files

