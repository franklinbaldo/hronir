import json
import os
import shutil
import uuid
from pathlib import Path

import pytest
from typer.testing import CliRunner

from hronir_encyclopedia import cli as hronir_cli
from hronir_encyclopedia import ratings, storage, transaction_manager
from hronir_encyclopedia.models import Path as PathModel

runner = CliRunner()

TEST_ROOT = Path("temp_test_data_sessions") # Unique name for this test file's temp data
# Absolute paths for reference if needed, but tests will chdir
LIBRARY_DIR_abs = (Path.cwd() / TEST_ROOT / "the_library").resolve()
DATA_DIR_abs = (Path.cwd() / TEST_ROOT / "data").resolve() # Base for DB and JSON files
DB_FILE_abs = (DATA_DIR_abs / "test_hronir_sessions.duckdb").resolve() # Test-specific DB
SESSIONS_DIR_abs = (DATA_DIR_abs / "sessions").resolve()
TRANSACTIONS_DIR_abs = (DATA_DIR_abs / "transactions").resolve()
CANONICAL_PATH_FILE_abs = (DATA_DIR_abs / "canonical_path.json").resolve()

# Runtime paths, relative to TEST_ROOT after chdir
# FORKING_PATH_DIR_runtime and RATINGS_DIR_runtime are removed (data in DuckDB)
DATA_DIR_runtime = Path("data") # This will be data dir inside TEST_ROOT
SESSIONS_DIR_runtime = DATA_DIR_runtime / "sessions"
TRANSACTIONS_DIR_runtime = DATA_DIR_runtime / "transactions"
CANONICAL_PATH_FILE_runtime = DATA_DIR_runtime / "canonical_path.json"
# DB_FILE_runtime will be DATA_DIR_runtime / "test_hronir_sessions.duckdb"


def compute_uuid_from_content_helper(content: str) -> uuid.UUID:
    return uuid.uuid5(storage.UUID_NAMESPACE, content)


def _run_cli_command(args: list[str]):
    result = runner.invoke(hronir_cli.app, args, catch_exceptions=False)
    output = result.stdout
    if result.exit_code != 0:
        print(f"CLI Error Output for command {' '.join(args)}:\n{output}")
        if result.stderr:
            print(f"CLI Stderr:\n{result.stderr}")
    return result, output


def _create_hronir(hr_uuid_str: str, text_content: str) -> str:
    content_derived_uuid = str(compute_uuid_from_content_helper(text_content))

    try:
        uuid.UUID(hr_uuid_str)
        assert hr_uuid_str == content_derived_uuid, (
            f"Provided hr_uuid {hr_uuid_str} does not match content-derived {content_derived_uuid}."
        )
    except ValueError:
        hr_uuid_str = content_derived_uuid

    stored_uuid = storage.store_chapter_text(text_content, base=Path("the_library"))
    assert stored_uuid == hr_uuid_str
    return hr_uuid_str


def hr_uuid_filename_safe(hr_uuid: str) -> str:
    return hr_uuid.replace("-", "")


def _create_fork_entry(
    position: int,
    prev_hr_uuid_str: str | None,
    current_hr_uuid_str: str,
):
    path_uuid_obj = storage.compute_narrative_path_uuid(
        position, prev_hr_uuid_str if prev_hr_uuid_str else "", current_hr_uuid_str
    )

    model_prev_uuid = (
        uuid.UUID(prev_hr_uuid_str) if prev_hr_uuid_str and prev_hr_uuid_str != "" else None
    )
    model_current_uuid = uuid.UUID(current_hr_uuid_str)

    path_data = {
        "path_uuid": path_uuid_obj,
        "position": position,
        "prev_uuid": model_prev_uuid,
        "uuid": model_current_uuid,
        "status": "PENDING",
    }
    path_model = PathModel(**path_data)
    storage.data_manager.add_path(path_model)
    return str(path_uuid_obj)


def _get_fork_uuid(position: int, prev_hr_uuid: str, current_hr_uuid: str) -> str:
    return str(
        storage.compute_narrative_path_uuid(
            position, prev_hr_uuid if prev_hr_uuid else "", current_hr_uuid
        )
    )


def _create_vote_entry(
    position: int, voter_path_uuid: str, winner_hr_uuid: str, loser_hr_uuid: str
):
    ratings.record_vote(position, voter_path_uuid, winner_hr_uuid, loser_hr_uuid)


def _init_canonical_path(path_data: dict):
    CANONICAL_PATH_FILE_runtime.parent.mkdir(parents=True, exist_ok=True)
    content = {"title": "The Hrönir Encyclopedia - Canonical Path", "path": path_data}
    CANONICAL_PATH_FILE_runtime.write_text(json.dumps(content, indent=2))


def _get_canonical_path() -> dict:
    if not CANONICAL_PATH_FILE_runtime.exists():
        return {}
    return json.loads(CANONICAL_PATH_FILE_runtime.read_text())["path"]


# def _get_session_file_data(session_id: str) -> dict | None:
#     session_file = SESSIONS_DIR_runtime / f"{session_id}.json"
#     if not session_file.exists():
#         return None
#     return json.loads(session_file.read_text())


# def _get_consumed_paths_data() -> dict: # Renamed function
#     consumed_file = SESSIONS_DIR_runtime / "consumed_path_uuids.json" # Corrected filename
#     if not consumed_file.exists():
#         return {}
#     return json.loads(consumed_file.read_text())


def _get_transaction_data(tx_uuid: str) -> dict | None:
    tx_file = TRANSACTIONS_DIR_runtime / f"{tx_uuid}.json"
    if not tx_file.exists():
        return None
    return json.loads(tx_file.read_text())


def _get_head_transaction_uuid() -> str | None:
    head_file = TRANSACTIONS_DIR_runtime / "HEAD"
    if not head_file.exists():
        return None
    return head_file.read_text().strip()


def _qualify_fork(
    path_to_qualify_uuid_str: str,
    hr_to_qualify_uuid_str: str,
    position: int,
    predecessor_hr_uuid_str: str | None,
):
    dummy_opponent_content = f"Dummy Opponent for {hr_to_qualify_uuid_str[:8]}"
    dummy_opponent_hr_uuid_str = str(compute_uuid_from_content_helper(dummy_opponent_content))
    _create_hronir(dummy_opponent_hr_uuid_str, dummy_opponent_content)

    _create_fork_entry(
        position,
        predecessor_hr_uuid_str,
        dummy_opponent_hr_uuid_str,
    )

    for i in range(4):
        single_vote_verdict = [
            {
                "position": position,
                "winner_hrönir_uuid": hr_to_qualify_uuid_str,
                "loser_hrönir_uuid": dummy_opponent_hr_uuid_str,
                "predecessor_hrönir_uuid": predecessor_hr_uuid_str,
            }
        ]
        # Use a valid UUIDv5 for initiating_path_uuid
        # This should be a path_uuid of a QUALIFIED path that is "spending" its mandate
        # For testing, we can generate a deterministic one or a random v4 if the model allows.
        # The TransactionContent model expects initiating_path_uuid to be UUIDv5.
        # Let's create a dummy path_uuid for the initiator.
        _dummy_initiator_content_1 = f"initiator_content_1_{i}_{path_to_qualify_uuid_str}"
        _dummy_initiator_content_2 = f"initiator_content_2_{i}_{path_to_qualify_uuid_str}"

        # Create a hrönir UUID (can be v4 or v5, PathModel's uuid is UUID5 but accepts v4 if it's a valid UUID string)
        # For simplicity, let's use v4 for these dummy hrönirs
        dummy_initiator_hr_prev_uuid = str(uuid.uuid4())
        dummy_initiator_hr_curr_uuid = str(uuid.uuid4())

        initiating_path_uuid = str(
            storage.compute_narrative_path_uuid(
                position - 1 if position > 0 else 0,  # A path at pos N judges pos N-1 and N-2
                dummy_initiator_hr_prev_uuid,
                dummy_initiator_hr_curr_uuid,
            )
        )

        tx_result = transaction_manager.record_transaction(
            session_id=str(uuid.uuid4()),
            initiating_path_uuid=initiating_path_uuid,
            session_verdicts=single_vote_verdict,
        )
        assert tx_result is not None, (
            f"Transaction {i + 1} for qualification of {path_to_qualify_uuid_str} failed"
        )

    qualified_path_data = storage.data_manager.get_path_by_uuid(path_to_qualify_uuid_str)
    assert qualified_path_data is not None, (
        f"Path {path_to_qualify_uuid_str} not found after qualification attempt."
    )

    elo_rating_msg = "N/A"
    ranking_for_elo_check = ratings.get_ranking(position, predecessor_hr_uuid_str)
    if not ranking_for_elo_check.empty:
        path_in_ranking = ranking_for_elo_check[
            ranking_for_elo_check["path_uuid"] == path_to_qualify_uuid_str
        ]
        if not path_in_ranking.empty:
            elo_rating_msg = str(path_in_ranking.iloc[0]["elo_rating"])

    assert qualified_path_data.status == "QUALIFIED", (
        f"Path {path_to_qualify_uuid_str} did not reach QUALIFIED status. Current status: {qualified_path_data.status}, Elo: {elo_rating_msg}"
    )
    assert qualified_path_data.mandate_id is not None, (
        f"Path {path_to_qualify_uuid_str} is QUALIFIED but has no mandate_id."
    )


@pytest.fixture(autouse=True)
def test_environment(monkeypatch):
    resolved_test_root = (Path.cwd() / TEST_ROOT).resolve()

    if resolved_test_root.exists():
        shutil.rmtree(resolved_test_root)
    resolved_test_root.mkdir(parents=True)

    # Create necessary subdirectories within the resolved_test_root
    library_runtime_path = resolved_test_root / "the_library"
    data_runtime_path = resolved_test_root / "data"
    db_file_runtime_path = data_runtime_path / "test_hronir_sessions.duckdb" # Test-specific DB file

    sessions_runtime_path = data_runtime_path / "sessions"
    transactions_runtime_path = data_runtime_path / "transactions"

    library_runtime_path.mkdir(parents=True, exist_ok=True)
    data_runtime_path.mkdir(parents=True, exist_ok=True) # For DB and JSON files
    sessions_runtime_path.mkdir(parents=True, exist_ok=True)
    transactions_runtime_path.mkdir(parents=True, exist_ok=True)

    original_cwd = Path.cwd()
    os.chdir(resolved_test_root) # Change CWD to the test root for relative path consistency

    # Store and set environment variables for test-specific paths
    original_env_library_dir = os.getenv("HRONIR_LIBRARY_DIR")
    original_env_duckdb_path = os.getenv("HRONIR_DUCKDB_PATH")

    monkeypatch.setenv("HRONIR_LIBRARY_DIR", str(library_runtime_path))
    monkeypatch.setenv("HRONIR_DUCKDB_PATH", str(db_file_runtime_path))

    # Delete test DB file if it exists from a previous run
    if db_file_runtime_path.exists():
        db_file_runtime_path.unlink()

    # Force re-instantiation and re-initialization of the global DataManager
    if storage.data_manager._instance is not None:
        if hasattr(storage.data_manager.backend, 'conn') and storage.data_manager.backend.conn is not None:
            try:
                storage.data_manager.backend.conn.close()
            except Exception: pass # Ignore errors if already closed
    monkeypatch.setattr(storage, "data_manager", storage.DataManager()) # Create new instance with new env vars

    # Initialize the new global DataManager instance
    storage.data_manager.initialize_and_load(clear_existing_data=True) # Creates tables, clears them

    # Patch module-level paths for transaction_manager (for JSON files)
    # Session manager specific paths are removed.
    monkeypatch.setattr(transaction_manager, "TRANSACTIONS_DIR", Path("data/transactions"))
    monkeypatch.setattr(transaction_manager, "HEAD_FILE", Path("data/transactions/HEAD"))
    # monkeypatch.setattr(session_manager, "SESSIONS_DIR", Path("data/sessions")) # Removed
    # monkeypatch.setattr(session_manager, "CONSUMED_PATHS_FILE", Path("data/sessions/consumed_path_uuids.json")) # Removed

    # Ensure HEAD file exists if transaction_manager relies on it
    if not (Path("data/transactions/HEAD")).exists():
        (Path("data/transactions/HEAD")).write_text("")


    yield # Run the test

    # Teardown
    os.chdir(original_cwd) # Change back to original CWD

    if storage.data_manager._instance is not None and hasattr(storage.data_manager.backend, 'conn') and storage.data_manager.backend.conn is not None:
        try:
            storage.data_manager.backend.conn.close()
        except Exception: pass

    # Restore original environment variables if they were set, otherwise unset
    if original_env_library_dir is None:
        monkeypatch.delenv("HRONIR_LIBRARY_DIR", raising=False)
    else:
        monkeypatch.setenv("HRONIR_LIBRARY_DIR", original_env_library_dir)

    if original_env_duckdb_path is None:
        monkeypatch.delenv("HRONIR_DUCKDB_PATH", raising=False)
    else:
        monkeypatch.setenv("HRONIR_DUCKDB_PATH", original_env_duckdb_path)

    # Force DataManager to re-initialize on next access outside this test env
    if storage.data_manager._instance is not None:
        storage.data_manager._instance = None

    shutil.rmtree(resolved_test_root)


# class TestSessionWorkflow:
# TODO: Refactor these tests for the new 'cast-votes' command and remove session-specific logic.
# For now, all old session-based tests are commented out.

    # def test_scenario_1_dossier_and_limited_verdict(self):
    #     h0a_content = "Hrönir 0A"
    #     h0a_uuid = str(compute_uuid_from_content_helper(h0a_content))
    #     _create_hronir(h0a_uuid, h0a_content)
    #     f0a_path_uuid = _create_fork_entry(0, None, h0a_uuid)

    #     h0b_content = "Hrönir 0B"
    #     h0b_uuid = str(compute_uuid_from_content_helper(h0b_content))
    #     _create_hronir(h0b_uuid, h0b_content)
    #     f0b_path_uuid = _create_fork_entry(0, None, h0b_uuid)

    #     _init_canonical_path({"0": {"path_uuid": f0a_path_uuid, "hrönir_uuid": h0a_uuid}})

    #     h1a_content = "Hrönir 1A from 0A"
    #     h1a_uuid = str(compute_uuid_from_content_helper(h1a_content))
    #     _create_hronir(h1a_uuid, h1a_content)
    #     f1a_path_uuid = _create_fork_entry(1, h0a_uuid, h1a_uuid)

    #     _init_canonical_path(
    #         {
    #             "0": {"path_uuid": f0a_path_uuid, "hrönir_uuid": h0a_uuid},
    #             "1": {"path_uuid": f1a_path_uuid, "hrönir_uuid": h1a_uuid},
    #         }
    #     )

    #     h2_judge_content = "Hrönir 2 Judge from 1A"
    #     h2_judge_uuid = str(compute_uuid_from_content_helper(h2_judge_content))
    #     _create_hronir(h2_judge_uuid, h2_judge_content)
    #     f2_judge_path_uuid = _create_fork_entry(2, h1a_uuid, h2_judge_uuid)

    #     _qualify_fork(f2_judge_path_uuid, h2_judge_uuid, 2, h1a_uuid)

    #     cmd_args_start = [
    #         "session",
    #         "start",
    #         "--path-uuid",
    #         f2_judge_path_uuid,
    #     ]

    #     result_start, output_start = _run_cli_command(cmd_args_start)
    #     assert result_start.exit_code == 0, f"session start failed: {output_start}"

    #     start_output_data = json.loads(output_start)
    #     session_id = start_output_data["session_id"]

    #     assert session_id is not None

    #     # assert SESSIONS_DIR_runtime.joinpath(f"{session_id}.json").exists() # File check
    #     # consumed_paths_data = _get_consumed_paths_data()
    #     # assert consumed_paths_data.get(f2_judge_path_uuid) == session_id # Consumed check

    #     verdicts_json_str = json.dumps({"0": f0b_path_uuid})
    #     cmd_args_commit = [
    #         "session",
    #         "commit",
    #         "--session-id",
    #         session_id,
    #         "--verdicts",
    #         verdicts_json_str,
    #     ]
    #     result_commit, output_commit = _run_cli_command(cmd_args_commit)
    #     assert result_commit.exit_code == 0, f"session commit failed: {output_commit}"

    #     tx_head_uuid = _get_head_transaction_uuid()
    #     assert tx_head_uuid is not None
    #     tx_data = _get_transaction_data(tx_head_uuid)
    #     assert tx_data is not None
    #     # assert tx_data["content"]["session_id"] == session_id # session_id in transaction content will change
    #     assert tx_data["content"]["initiating_path_uuid"] == f2_judge_path_uuid

    #     # session_file_data = _get_session_file_data(session_id) # Session file check
    #     # assert session_file_data["status"] == "committed" # Status check

    # def test_scenario_2_full_temporal_cascade(self):
    #     pass

    # def test_scenario_3_dormant_vote_reactivation(self):
    #     pass
