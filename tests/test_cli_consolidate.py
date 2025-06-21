import json
import shutil
from pathlib import Path
import pytest # Added for pytest.raises

import pandas as pd

from hronir_encyclopedia import cli, storage


# Helper to create dummy chapter files in the_library
def _create_dummy_chapter(library_dir: Path, uuid_str: str, content: str):
    chapter_path = storage.uuid_to_path(uuid_str, library_dir)
    chapter_path.mkdir(parents=True, exist_ok=True)
    (chapter_path / "index.md").write_text(content)
    meta = {"uuid": uuid_str}  # Minimal metadata
    (chapter_path / "metadata.json").write_text(json.dumps(meta))


# Helper to create dummy rating CSVs (raw votes for get_ranking)
def _create_dummy_raw_votes_csv(ratings_dir: Path, position: int, votes_data: list[dict]):
    df = pd.DataFrame(votes_data)
    # Ensure essential columns for get_ranking if not provided in votes_data
    if not votes_data:  # Handle empty votes list
        df = pd.DataFrame(columns=["uuid", "voter", "winner", "loser"])
    else:
        if "uuid" not in df.columns:  # vote uuid
            df["uuid"] = [f"vote{i+1}" for i in range(len(df))]
        if "voter" not in df.columns:
            df["voter"] = [f"voter{i+1}" for i in range(len(df))]

    ratings_file = ratings_dir / f"position_{position:03d}.csv"
    df.to_csv(ratings_file, index=False)


def test_consolidate_book_workflow(tmp_path, capsys):
    ratings_dir = tmp_path / "ratings"
    ratings_dir.mkdir()
    library_dir = tmp_path / "the_library"
    library_dir.mkdir()
    book_dir = tmp_path / "book"
    book_dir.mkdir()
    index_file = book_dir / "book_index.json"

    # --- Setup Chapters in Library ---
    chap_A_uuid = storage.compute_uuid("Chapter A: The True Winner for Pos 1")
    chap_B_uuid = storage.compute_uuid("Chapter B: A Contender for Pos 1")
    chap_C_uuid = storage.compute_uuid("Chapter C: Original for Pos 0 (Unchanged)")
    chap_D_uuid = storage.compute_uuid("Chapter D: Candidate for Pos 2 (Not in Library)")
    chap_E_uuid = storage.compute_uuid("Chapter E: Old Winner for Pos 1 (To be replaced)")

    _create_dummy_chapter(library_dir, chap_A_uuid, "Chapter A: The True Winner for Pos 1")
    _create_dummy_chapter(library_dir, chap_B_uuid, "Chapter B: A Contender for Pos 1")
    _create_dummy_chapter(library_dir, chap_C_uuid, "Chapter C: Original for Pos 0 (Unchanged)")
    # chap_D_uuid is intentionally not created in the library
    _create_dummy_chapter(
        library_dir, chap_E_uuid, "Chapter E: Old Winner for Pos 1 (To be replaced)"
    )

    # --- Initial Book State (book_index.json and files in book_dir) ---
    initial_pos0_filename = f"0_{chap_C_uuid[:8]}.md"
    initial_pos1_old_filename = f"1_{chap_E_uuid[:8]}.md"

    initial_book_index_data = {
        "title": "The Great Hrönir Tome",
        "chapters": {"0": initial_pos0_filename, "1": initial_pos1_old_filename},
    }
    index_file.write_text(json.dumps(initial_book_index_data, indent=2))
    (book_dir / initial_pos0_filename).write_text("Chapter C: Original for Pos 0 (Unchanged)")
    (book_dir / initial_pos1_old_filename).write_text(
        "Chapter E: Old Winner for Pos 1 (To be replaced)"
    )

    # --- Setup Ratings Data (Raw Votes) ---
    # Position 1: chap_A wins 2-1 against chap_B. Elo for A should be higher.
    votes_pos1 = [
        {"winner": chap_A_uuid, "loser": chap_B_uuid},
        {"winner": chap_A_uuid, "loser": chap_B_uuid},
        {"winner": chap_B_uuid, "loser": chap_A_uuid},
    ]
    _create_dummy_raw_votes_csv(ratings_dir, 1, votes_pos1)

    # Position 2: chap_D would win, but it's not in the library.
    votes_pos2 = [{"winner": chap_D_uuid, "loser": chap_A_uuid}]
    _create_dummy_raw_votes_csv(ratings_dir, 2, votes_pos2)

    # Position 3: No votes, so ranking will be empty.
    _create_dummy_raw_votes_csv(ratings_dir, 3, [])

    # --- Run 1: Basic Consolidation ---
    with pytest.raises(SystemExit) as e_info:
        cli.main(
            [
                "consolidate-book",
                f"--ratings-dir={ratings_dir}",
                f"--library-dir={library_dir}",
                f"--book-dir={book_dir}",
                f"--index-file={index_file}",
            ]
        )
    assert e_info.type == SystemExit
    assert e_info.value.code == 0
    captured = capsys.readouterr()
    # print(f"Run 1 Output:\n{captured.out}") # For debugging

    # Assertions for Run 1
    updated_index_data = json.loads(index_file.read_text())
    expected_pos1_new_filename = f"1_{chap_A_uuid[:8]}.md"

    assert updated_index_data["chapters"]["0"] == initial_pos0_filename  # Pos 0 unchanged
    assert (book_dir / initial_pos0_filename).exists()

    assert updated_index_data["chapters"]["1"] == expected_pos1_new_filename  # Pos 1 updated to A
    assert (book_dir / expected_pos1_new_filename).exists()
    assert (
        book_dir / expected_pos1_new_filename
    ).read_text() == "Chapter A: The True Winner for Pos 1"
    assert not (book_dir / initial_pos1_old_filename).exists()  # Old file for Pos 1 removed

    assert "2" not in updated_index_data["chapters"]  # Pos 2 not added (winner not in library)
    assert f"Winner chapter {chap_D_uuid} for position 2 not found in library." in captured.err # Check stderr
    assert not list(book_dir.glob("2_*.md"))

    assert "3" not in updated_index_data["chapters"]  # Pos 3 not added (no ranking data)
    assert "No ranking data for position 3." in captured.out # This is a normal info message, so stdout is fine
    assert not list(book_dir.glob("3_*.md"))

    # --- Run 2: Corrupted Index File ---
    index_file.write_text("invalid json content")
    with pytest.raises(SystemExit) as e_info_run2:
        cli.main(
            [
                "consolidate-book", # Use hyphen
                f"--ratings-dir={ratings_dir}",
                f"--library-dir={library_dir}",
                f"--book-dir={book_dir}",
                f"--index-file={index_file}",
            ]
        )
    assert e_info_run2.type == SystemExit
    assert e_info_run2.value.code == 0 # Expect successful exit despite error message
    captured_corrupt = capsys.readouterr()
    # print(f"Run 2 (Corrupt Index) Output:\n{captured_corrupt.out}")
    # print(f"Run 2 (Corrupt Index) Stderr:\n{captured_corrupt.err}")

    assert f"Error reading or parsing book index file: {index_file}" in captured_corrupt.err # Error goes to stderr
    # Should create a new default index and still process available ratings
    index_after_corrupt_run = json.loads(index_file.read_text())
    assert index_after_corrupt_run["title"] == "The Hrönir Encyclopedia"  # Default title
    assert (
        index_after_corrupt_run["chapters"]["1"] == expected_pos1_new_filename
    )  # Pos 1 re-consolidated
    assert (book_dir / expected_pos1_new_filename).exists()
    # Files not part of active consolidation (like original pos 0) should remain if not overwritten
    assert (book_dir / initial_pos0_filename).exists()

    # --- Run 3: Ratings Directory Missing ---
    shutil.rmtree(ratings_dir)
    # Re-create ratings_dir as an empty dir for the test, because the CLI checks for dir existence, not content
    # The test is for when the *directory* is missing. The error message should be about the dir.
    # To test "Ratings directory not found", it must actually not exist.
    # So rmtree is correct. The CLI should then print to stderr and exit(1).

    with pytest.raises(SystemExit) as e_info_run3:
        cli.main(
            [
                "consolidate-book", # Use hyphen
                f"--ratings-dir={ratings_dir}",  # Path still points to it, but it's gone
                f"--library-dir={library_dir}",
                f"--book-dir={book_dir}",
                f"--index-file={index_file}",
            ]
        )
    assert e_info_run3.type == SystemExit
    # The CLI should exit with an error code if the ratings_dir is not found, as it's a prerequisite.
    # Typer/Click typically exits with 2 for bad parameters like a non-existent directory for an `exists=True` option.
    assert e_info_run3.value.code == 2 # Expecting Typer/Click's bad parameter exit code

    captured_no_ratings_dir = capsys.readouterr()
    # print(f"Run 3 (No Ratings Dir) Output:\n{captured_no_ratings_dir.out}")
    # print(f"Run 3 (No Ratings Dir) Stderr:\n{captured_no_ratings_dir.err}")
    # Typer's actual error message for a non-existent directory with exists=True
    expected_error_msg_part = f"Invalid value for '--ratings-dir'.*Directory '{ratings_dir}' does not exist"
    # Use re.search or check for key parts if the exact path formatting is tricky.
    # For simplicity, let's check for the core message parts.
    assert "Invalid value for '--ratings-dir'" in captured_no_ratings_dir.err
    # Check for the components of the message "Directory '<path>' does not exist."
    assert "Directory" in captured_no_ratings_dir.err
    assert str(ratings_dir) in captured_no_ratings_dir.err # Ensure the correct path is mentioned
    assert "does not exist" in captured_no_ratings_dir.err
    # Index file should not have been modified further by this call, as the command should have failed early.
    index_after_no_ratings_dir = json.loads(index_file.read_text()) # This was the state after corrupt run
    assert index_after_no_ratings_dir["chapters"]["1"] == expected_pos1_new_filename


# Note: Removed the trailing ``` that was causing syntax errors.
