import json
import os
import shutil
import uuid
from pathlib import Path

import pandas as pd
import pytest
from typer.testing import CliRunner

from hronir_encyclopedia import cli as hronir_cli
from hronir_encyclopedia import models, ratings, storage, transaction_manager
from hronir_encyclopedia.models import Path as PathModel


runner = CliRunner()

TEST_ROOT = Path("temp_test_data")
LIBRARY_DIR_abs = (Path.cwd() / TEST_ROOT / "the_library").resolve()
FORKING_PATH_DIR_abs = (Path.cwd() / TEST_ROOT / "forking_path").resolve()
RATINGS_DIR_abs = (Path.cwd() / TEST_ROOT / "ratings").resolve()
DATA_DIR_abs = (Path.cwd() / TEST_ROOT / "data").resolve()
SESSIONS_DIR_fixture_abs = (DATA_DIR_abs / "sessions").resolve()
TRANSACTIONS_DIR_fixture_abs = (DATA_DIR_abs / "transactions").resolve()
CANONICAL_PATH_FILE_fixture_abs = (DATA_DIR_abs / "canonical_path.json").resolve()

FORKING_PATH_DIR_runtime = Path("forking_path")
RATINGS_DIR_runtime = Path("ratings")
DATA_DIR_runtime = Path("data")
SESSIONS_DIR_runtime = DATA_DIR_runtime / "sessions"
TRANSACTIONS_DIR_runtime = DATA_DIR_runtime / "transactions"
CANONICAL_PATH_FILE_runtime = DATA_DIR_runtime / "canonical_path.json"


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
        assert hr_uuid_str == content_derived_uuid, \
            f"Provided hr_uuid {hr_uuid_str} does not match content-derived {content_derived_uuid}."
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
        position,
        prev_hr_uuid_str if prev_hr_uuid_str else "",
        current_hr_uuid_str
    )

    model_prev_uuid = uuid.UUID(prev_hr_uuid_str) if prev_hr_uuid_str and prev_hr_uuid_str != "" else None
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
    return str(storage.compute_narrative_path_uuid(position, prev_hr_uuid if prev_hr_uuid else "", current_hr_uuid))


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


def _get_session_file_data(session_id: str) -> dict | None:
    session_file = SESSIONS_DIR_runtime / f"{session_id}.json"
    if not session_file.exists():
        return None
    return json.loads(session_file.read_text())


def _get_consumed_forks_data() -> dict:
    consumed_file = SESSIONS_DIR_runtime / "consumed_fork_uuids.json"
    if not consumed_file.exists():
        return {}
    return json.loads(consumed_file.read_text())


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
                "predecessor_hrönir_uuid": predecessor_hr_uuid_str
            }
        ]
        # Use a valid UUIDv5 for initiating_fork_uuid
        # This should be a path_uuid of a QUALIFIED path that is "spending" its mandate
        # For testing, we can generate a deterministic one or a random v4 if the model allows.
        # The TransactionContent model expects initiating_path_uuid to be UUIDv5.
        # Let's create a dummy path_uuid for the initiator.
        dummy_initiator_content_1 = f"initiator_content_1_{i}_{path_to_qualify_uuid_str}"
        dummy_initiator_content_2 = f"initiator_content_2_{i}_{path_to_qualify_uuid_str}"

        # Create a hrönir UUID (can be v4 or v5, PathModel's uuid is UUID5 but accepts v4 if it's a valid UUID string)
        # For simplicity, let's use v4 for these dummy hrönirs
        dummy_initiator_hr_prev_uuid = str(uuid.uuid4())
        dummy_initiator_hr_curr_uuid = str(uuid.uuid4())


        initiating_path_uuid = str(storage.compute_narrative_path_uuid(
            position -1 if position > 0 else 0, # A path at pos N judges pos N-1 and N-2
            dummy_initiator_hr_prev_uuid,
            dummy_initiator_hr_curr_uuid
        ))


        tx_result = transaction_manager.record_transaction(
            session_id=str(uuid.uuid4()),
            initiating_fork_uuid=initiating_path_uuid,
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
    ranking_for_elo_check = ratings.get_ranking(
        position, predecessor_hr_uuid_str
    )
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
    resolved_test_root = Path.cwd() / TEST_ROOT

    if resolved_test_root.exists():
        shutil.rmtree(resolved_test_root)

    resolved_test_root.mkdir(parents=True)
    (resolved_test_root / "the_library").mkdir(parents=True, exist_ok=True)
    (resolved_test_root / "forking_path").mkdir(parents=True, exist_ok=True)
    (resolved_test_root / "ratings").mkdir(parents=True, exist_ok=True)
    (resolved_test_root / "data").mkdir(parents=True, exist_ok=True)
    (resolved_test_root / "data" / "sessions").mkdir(parents=True, exist_ok=True)
    (resolved_test_root / "data" / "transactions").mkdir(parents=True, exist_ok=True)

    original_cwd = Path.cwd()
    os.chdir(resolved_test_root)

    original_fork_dir = storage.data_manager.fork_csv_dir
    original_ratings_dir = storage.data_manager.ratings_csv_dir
    original_tx_dir = storage.data_manager.transactions_json_dir
    original_initialized = storage.data_manager._initialized

    storage.data_manager.fork_csv_dir = Path("forking_path")
    storage.data_manager.ratings_csv_dir = Path("ratings")
    storage.data_manager.transactions_json_dir = Path("data") / "transactions"

    storage.data_manager._initialized = False
    storage.data_manager.initialize_and_load(
        clear_existing_data=True
    )

    yield

    os.chdir(original_cwd)

    storage.data_manager.fork_csv_dir = original_fork_dir
    storage.data_manager.ratings_csv_dir = original_ratings_dir
    storage.data_manager.transactions_json_dir = original_tx_dir
    storage.data_manager._initialized = original_initialized

    if storage.data_manager._initialized:
        storage.data_manager.clear_in_memory_data()

    shutil.rmtree(resolved_test_root)


class TestSessionWorkflow:
    def test_scenario_1_dossier_and_limited_verdict(self):
        h0a_content = "Hrönir 0A"
        h0a_uuid = str(compute_uuid_from_content_helper(h0a_content))
        _create_hronir(h0a_uuid, h0a_content)
        f0a_path_uuid = _create_fork_entry(0, None, h0a_uuid)

        h0b_content = "Hrönir 0B"
        h0b_uuid = str(compute_uuid_from_content_helper(h0b_content))
        _create_hronir(h0b_uuid, h0b_content)
        f0b_path_uuid = _create_fork_entry(0, None, h0b_uuid)

        _init_canonical_path({"0": {"path_uuid": f0a_path_uuid, "hrönir_uuid": h0a_uuid}})

        h1a_content = "Hrönir 1A from 0A"
        h1a_uuid = str(compute_uuid_from_content_helper(h1a_content))
        _create_hronir(h1a_uuid, h1a_content)
        f1a_path_uuid = _create_fork_entry(1, h0a_uuid, h1a_uuid)

        _init_canonical_path(
            {
                "0": {"path_uuid": f0a_path_uuid, "hrönir_uuid": h0a_uuid},
                "1": {"path_uuid": f1a_path_uuid, "hrönir_uuid": h1a_uuid},
            }
        )

        h2_judge_content = "Hrönir 2 Judge from 1A"
        h2_judge_uuid = str(compute_uuid_from_content_helper(h2_judge_content))
        _create_hronir(h2_judge_uuid, h2_judge_content)
        f2_judge_path_uuid = _create_fork_entry(2, h1a_uuid, h2_judge_uuid)

        _qualify_fork(f2_judge_path_uuid, h2_judge_uuid, 2, h1a_uuid)

        cmd_args_start = [
            "session", "start", "--fork-uuid", f2_judge_path_uuid,
        ]

        result_start, output_start = _run_cli_command(cmd_args_start)
        assert result_start.exit_code == 0, f"session start failed: {output_start}"

        start_output_data = json.loads(output_start)
        session_id = start_output_data["session_id"]

        assert session_id is not None

        assert SESSIONS_DIR_runtime.joinpath(
            f"{session_id}.json"
        ).exists()
        consumed_forks = _get_consumed_forks_data()
        assert consumed_forks.get(f2_judge_path_uuid) == session_id

        verdicts_json_str = json.dumps({"0": f0b_path_uuid})
        cmd_args_commit = [
            "session", "commit", "--session-id", session_id,
            "--verdicts", verdicts_json_str,
        ]
        result_commit, output_commit = _run_cli_command(cmd_args_commit)
        assert result_commit.exit_code == 0, f"session commit failed: {output_commit}"

        tx_head_uuid = _get_head_transaction_uuid()
        assert tx_head_uuid is not None
        tx_data = _get_transaction_data(tx_head_uuid)
        assert tx_data is not None
        assert tx_data["session_id"] == session_id
        assert tx_data["initiating_fork_uuid"] == f2_judge_path_uuid

        session_file_data = _get_session_file_data(session_id)
        assert session_file_data["status"] == "committed"

    def test_scenario_2_full_temporal_cascade(self):
        pass

    def test_scenario_3_dormant_vote_reactivation(self):
        pass
