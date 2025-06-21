import json
import subprocess
import uuid
from pathlib import Path

import pandas as pd
import pytest # Added for pytest.raises

from hronir_encyclopedia import database, gemini_util, ratings, storage


def test_store_chapter_text(tmp_path):
    base = tmp_path / "the_library"
    text = "hello world"
    uid = storage.store_chapter_text(text, base=base)
    chapter_dir = storage.uuid_to_path(uid, base)
    assert (chapter_dir / "index.md").read_text() == text
    meta = json.loads((chapter_dir / "metadata.json").read_text())
    assert meta["uuid"] == uid


def test_record_vote_multiple_entries(tmp_path):
    base = tmp_path / "ratings"
    fork_dir = tmp_path / "forking_path"
    with database.open_database(ratings_dir=base, fork_dir=fork_dir) as conn:
        for i in range(10):
            ratings.record_vote(1, f"voter{i}", f"winner{i}", f"loser{i}", conn=conn)
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

    with database.open_database() as conn:
        for _ in range(10):
            gemini_util.auto_vote(
                position=1,
                prev_uuid="00000000-0000-0000-0000-000000000000",
                voter=str(uuid.uuid4()),
                conn=conn,
            )

    df = pd.read_csv(Path("ratings/position_001.csv"))
    assert len(df) == 10


def test_clean_functions(tmp_path):
    base = tmp_path / "the_library"
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

    fork_uuid_valid = "fork1"
    fork_dir = tmp_path / "forking_path"
    fork_dir.mkdir()
    fork_csv2 = fork_dir / "paths.csv"
    pd.DataFrame(
        [
            {
                "position": 1,
                "prev_uuid": uid1,
                "uuid": uid2,
                "fork_uuid": fork_uuid_valid,
            }
        ]
    ).to_csv(fork_csv2, index=False)

    rating_csv = tmp_path / "rating.csv"
    rows = [
        {
            "uuid": str(uuid.uuid4()),
            "voter": fork_uuid_valid,
            "winner": uid1,
            "loser": uid2,
        },
        {
            "uuid": str(uuid.uuid4()),
            "voter": fork_uuid_valid,
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
    removed = storage.purge_fake_votes_csv(rating_csv, base=base, fork_dir=fork_dir)
    assert removed == 2
    df = pd.read_csv(rating_csv)
    assert len(df) == 1


def test_clean_git_prunes_from_branch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    subprocess.run(["git", "init"], check=True)

    base = Path("the_library")
    storage.store_chapter_text("data", base=base)  # uid variable was unused
    bad = storage.store_chapter_text("bad", base=base)
    bad_dir = storage.uuid_to_path(bad, base)
    (bad_dir / "index.md").write_text("tampered")

    subprocess.run(["git", "add", "-A"], check=True)
    subprocess.run(["git", "commit", "-m", "init"], check=True)

    from hronir_encyclopedia import cli

    with pytest.raises(SystemExit) as e:
        cli.main(["clean", "--git"])
    assert e.type == SystemExit
    assert e.value.code == 0

    # After 'clean --git', the 'git rm' should have run.
    # 'git ls-files' will no longer show the file.
    ls_files_after_rm = subprocess.check_output(["git", "ls-files"], text=True)
    assert str(bad_dir / "index.md") not in ls_files_after_rm
    assert str(bad_dir / "metadata.json") not in ls_files_after_rm

    # Also check git status --porcelain to see the 'D' (deleted) status
    # This confirms they are staged for deletion.
    status_result = subprocess.run(
        ["git", "status", "--porcelain"], capture_output=True, text=True, check=True
    )
    # bad_dir is already relative to tmp_path (e.g. "the_library/c/8/0/...")
    # So, no need for .relative_to(tmp_path)
    deleted_file_path_str = str(bad_dir / "index.md")
    deleted_metadata_path_str = str(bad_dir / "metadata.json")

    expected_deleted_lines = {
        f"D  {deleted_file_path_str}",
        f"D  {deleted_metadata_path_str}"
    }
    actual_lines = {line.strip() for line in status_result.stdout.strip().split('\n') if line.strip().startswith("D ")}

    # Check that only the two "bad" files are staged for deletion
    # and no other files are unexpectedly staged.
    assert actual_lines == expected_deleted_lines

    # Verify that the "good" chapter is still tracked by git
    good_uuid = storage.compute_uuid("data")
    good_dir = storage.uuid_to_path(good_uuid, base)
    assert str(good_dir / "index.md") in ls_files_after_rm
