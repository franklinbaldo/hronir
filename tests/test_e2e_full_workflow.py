import json
import os
import shutil
import uuid
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hronir_encyclopedia import cli as hronir_cli
from hronir_encyclopedia import ratings, storage, transaction_manager, session_manager
from hronir_encyclopedia.models import Path as PathModel

runner = CliRunner()

# Define a unique test root directory for this test file
TEST_ROOT_E2E = Path("temp_test_e2e_data")

# Helper functions (adapted from other tests for clarity and direct use)
def _compute_uuid_from_content(content: str) -> str:
    return str(uuid.uuid5(storage.UUID_NAMESPACE, content))

def _create_hronir_and_store(content: str) -> str:
    """Creates a dummy hrönir content and stores it via the CLI."""
    # Use a temporary file to pass content to the CLI store command
    temp_file_path = TEST_ROOT_E2E / f"temp_hronir_{uuid.uuid4()}.md"
    temp_file_path.write_text(content)

    result, output = _run_cli_command(["store", str(temp_file_path)])
    assert result.exit_code == 0, f"CLI store failed: {output}"
    # The store command prints the UUID of the stored chapter
    stored_uuid = output.strip()
    temp_file_path.unlink() # Clean up temp file
    return stored_uuid

def _create_path_entry(position: int, prev_hr_uuid_str: str | None, current_hr_uuid_str: str) -> str:
    """Creates a path entry via the CLI and returns its path_uuid."""
    args = [
        "path",
        "--position", str(position),
        "--target", current_hr_uuid_str,
    ]
    if prev_hr_uuid_str:
        args.extend(["--source", prev_hr_uuid_str])

    result, output = _run_cli_command(args)
    assert result.exit_code == 0, f"CLI path failed: {output}"
    # The path command prints the path_uuid
    path_uuid = output.split("Created path: ")[1].split(" ")[0].strip()
    return path_uuid

def _run_cli_command(args: list[str]):
    result = runner.invoke(hronir_cli.app, args, catch_exceptions=False)
    output = result.stdout
    if result.exit_code != 0:
        print("CLI Error Output for command " + ' '.join(args) + ":\n" + output)
        if result.stderr:
            print("CLI Stderr:\n" + result.stderr)
    return result, output

def _qualify_path(path_to_qualify_uuid_str: str, hr_to_qualify_uuid_str: str, position: int, predecessor_hr_uuid_str: str | None):
    """
    Simulates votes to qualify a given path.
    This directly calls transaction_manager.record_transaction.
    """
    # Create a dummy opponent hrönir and path for duels
    dummy_opponent_content = f"Dummy Opponent for {hr_to_qualify_uuid_str[:8]} {uuid.uuid4()}"
    dummy_opponent_hr_uuid_str = _create_hronir_and_store(dummy_opponent_content)
    _create_path_entry(position, predecessor_hr_uuid_str, dummy_opponent_hr_uuid_str)

    # Simulate enough wins for qualification (e.g., 4 wins)
    num_wins_for_qualification = 4
    for i in range(num_wins_for_qualification):
        single_vote_verdict = [
            {
                "position": position,
                "winner_hrönir_uuid": hr_to_qualify_uuid_str,
                "loser_hrönir_uuid": dummy_opponent_hr_uuid_str,
                "predecessor_hrönir_uuid": predecessor_hr_uuid_str,
            }
        ]
        # Generate a dummy initiating path_uuid for the transaction
        dummy_initiator_path_uuid = str(uuid.uuid4()) # Use v4 for simplicity here

        tx_result = transaction_manager.record_transaction(
            session_id=str(uuid.uuid4()),
            initiating_path_uuid=dummy_initiator_path_uuid,
            session_verdicts=single_vote_verdict,
        )
        assert tx_result is not None, f"Transaction {i+1} for qualification failed."

    # Verify the path is qualified
    qualified_path_data = storage.data_manager.get_path_by_uuid(path_to_qualify_uuid_str)
    assert qualified_path_data is not None
    assert qualified_path_data.status == "QUALIFIED", f"Path {path_to_qualify_uuid_str} did not qualify. Current status: {qualified_path_data.status}"
    assert qualified_path_data.mandate_id is not None, "Qualified path should have a mandate_id."


@pytest.fixture(autouse=True)
def setup_e2e_test_environment(monkeypatch):
    """Sets up a clean environment for each E2E test."""
    # Ensure a clean test root directory
    if TEST_ROOT_E2E.exists():
        shutil.rmtree(TEST_ROOT_E2E)
    TEST_ROOT_E2E.mkdir(parents=True)

    # Monkeypatch environment variables and DataManager paths to use the test root
    monkeypatch.setenv("HRONIR_LIBRARY_DIR", str(TEST_ROOT_E2E / "the_library"))
    monkeypatch.setenv("HRONIR_NARRATIVE_PATHS_DIR", str(TEST_ROOT_E2E / "narrative_paths"))
    monkeypatch.setenv("HRONIR_RATINGS_DIR", str(TEST_ROOT_E2E / "ratings"))
    monkeypatch.setenv("HRONIR_DUCKDB_PATH", str(TEST_ROOT_E2E / "data" / "encyclopedia.duckdb"))

    # Ensure DataManager is re-initialized for a clean state, pointing to the test DB
    storage.DataManager._instance = None
    storage.data_manager = storage.DataManager()
    storage.data_manager.initialize_and_load(clear_existing_data=True)

    # Ensure transaction_manager and session_manager also point to the test data directories
    transaction_manager.TRANSACTIONS_DIR = TEST_ROOT_E2E / "data" / "transactions"
    transaction_manager.HEAD_FILE = transaction_manager.TRANSACTIONS_DIR / "HEAD"
    session_manager.SESSIONS_DIR = TEST_ROOT_E2E / "data" / "sessions"
    session_manager.CONSUMED_PATHS_FILE = session_manager.SESSIONS_DIR / "consumed_path_uuids.json"

    # Create necessary subdirectories within the test root
    (TEST_ROOT_E2E / "the_library").mkdir(parents=True, exist_ok=True)
    (TEST_ROOT_E2E / "narrative_paths").mkdir(parents=True, exist_ok=True)
    (TEST_ROOT_E2E / "ratings").mkdir(parents=True, exist_ok=True)
    (TEST_ROOT_E2E / "data").mkdir(parents=True, exist_ok=True)
    (TEST_ROOT_E2E / "data" / "sessions").mkdir(parents=True, exist_ok=True)
    (TEST_ROOT_E2E / "data" / "transactions").mkdir(parents=True, exist_ok=True)

    # Ensure HEAD file exists and is empty for a clean start
    if transaction_manager.HEAD_FILE.exists():
        transaction_manager.HEAD_FILE.unlink()
    transaction_manager.HEAD_FILE.write_text("")

    # Yield control to the test function
    yield

    # Teardown: Clean up the test root directory
    if TEST_ROOT_E2E.exists():
        shutil.rmtree(TEST_ROOT_E2E)

    # Reset DataManager instance to avoid interference with other tests
    storage.DataManager._instance = None


def test_full_e2e_workflow():
    """
    Tests the full end-to-end workflow: create hrönirs/paths, qualify, session start/commit, cascade.
    """
    # --- 1. Create Hrönirs and Paths ---
    # Hrönir for Position 0 (initial canonical)
    h0_content_A = "The first hrönir, setting the stage."
    h0_uuid_A = _create_hronir_and_store(h0_content_A)
    p0_path_uuid_A = _create_path_entry(0, None, h0_uuid_A)

    # Hrönir for Position 0 (alternative, will become canonical)
    h0_content_B = "An alternative beginning, a divergent path."
    h0_uuid_B = _create_hronir_and_store(h0_content_B)
    p0_path_uuid_B = _create_path_entry(0, None, h0_uuid_B)

    # Hrönir for Position 1 (child of A, initial canonical)
    h1_content_X = "The narrative continues from A."
    h1_uuid_X = _create_hronir_and_store(h1_content_X)
    p1_path_uuid_X = _create_path_entry(1, h0_uuid_A, h1_uuid_X)

    # Hrönir for Position 1 (child of B, will become canonical)
    h1_content_Y = "The narrative continues from B."
    h1_uuid_Y = _create_hronir_and_store(h1_content_Y)
    p1_path_uuid_Y = _create_path_entry(1, h0_uuid_B, h1_uuid_Y)

    # Initialize canonical path (A is canonical for pos 0, X for pos 1)
    initial_canonical_data = {
        "title": "Initial Canonical Path for E2E Test",
        "path": {
            "0": {"path_uuid": p0_path_uuid_A, "hrönir_uuid": h0_uuid_A},
            "1": {"path_uuid": p1_path_uuid_X, "hrönir_uuid": h1_uuid_X},
        },
    }
    canonical_path_file = TEST_ROOT_E2E / "data" / "canonical_path.json"
    canonical_path_file.write_text(json.dumps(initial_canonical_data, indent=2))

    # --- 2. Qualify a Path ---
    # We need to qualify a path that will initiate a session.
    # Let's qualify p1_path_uuid_X (path at pos 1, from h0_uuid_A)
    _qualify_path(p1_path_uuid_X, h1_uuid_X, 1, h0_uuid_A)

    # Verify qualification status
    qualified_path_data = storage.data_manager.get_path_by_uuid(p1_path_uuid_X)
    assert qualified_path_data.status == "QUALIFIED"
    assert qualified_path_data.mandate_id is not None

    # --- 3. Start a Judgment Session ---
    result_start, output_start = _run_cli_command([
        "session",
        "start",
        "--path-uuid", p1_path_uuid_X,
        "--canonical-path-file", str(canonical_path_file),
    ])
    assert result_start.exit_code == 0, f"Session start failed: {output_start}"

    start_output_data = json.loads(output_start)
    session_id = start_output_data["session_id"]
    assert session_id is not None
    assert start_output_data["initiating_path_uuid"] == p1_path_uuid_X
    assert start_output_data["status"] == "active"

    # The dossier should contain duels for positions 0 up to position_n - 1 (which is 0 in this case)
    # The dossier is based on the current canonical path.
    dossier_duels = start_output_data["dossier"]["duels"]
    assert "0" in dossier_duels, "Dossier should contain a duel for position 0."
    duel_pos0 = dossier_duels["0"]
    # The duel should be between the current canonical (p0_path_uuid_A) and its strongest competitor (p0_path_uuid_B)
    assert {duel_pos0["path_A"], duel_pos0["path_B"]} == {p0_path_uuid_A, p0_path_uuid_B}

    # --- 4. Commit Verdicts ---
    # We will submit a verdict that makes p0_path_uuid_B canonical for position 0.
    verdicts_to_commit = {
        "0": p0_path_uuid_B # Make B canonical for position 0
    }
    verdicts_json_str = json.dumps(verdicts_to_commit)

    result_commit, output_commit = _run_cli_command([
        "session",
        "commit",
        "--session-id", session_id,
        "--verdicts", verdicts_json_str,
        "--canonical-path-file", str(canonical_path_file),
    ])
    assert result_commit.exit_code == 0, f"Session commit failed: {output_commit}"

    # --- 5. Verify Temporal Cascade ---
    # Read the updated canonical path file
    updated_canonical_data = json.loads(canonical_path_file.read_text())

    # Assert that position 0 is now p0_path_uuid_B
    assert "0" in updated_canonical_data["path"]
    assert updated_canonical_data["path"]["0"]["path_uuid"] == p0_path_uuid_B
    assert updated_canonical_data["path"]["0"]["hrönir_uuid"] == h0_uuid_B

    # Assert that position 1 has been re-evaluated based on the new canonical predecessor (h0_uuid_B)
    # It should now be p1_path_uuid_Y, as it's the only child of h0_uuid_B
    assert "1" in updated_canonical_data["path"]
    assert updated_canonical_data["path"]["1"]["path_uuid"] == p1_path_uuid_Y
    assert updated_canonical_data["path"]["1"]["hrönir_uuid"] == h1_uuid_Y

    # Verify the initiating path's status is SPENT
    spent_path_data = storage.data_manager.get_path_by_uuid(p1_path_uuid_X)
    assert spent_path_data.status == "SPENT"

    # Verify the session status is committed
    session_file_data = session_manager.get_session(session_id)
    assert session_file_data.status == "committed"

    print("Full E2E workflow test passed successfully!")
