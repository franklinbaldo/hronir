from pathlib import Path

import pandas as pd

from hronir_encyclopedia import (
    ratings,
    storage,
)


def _call_get_ranking_with_setup(position, predecessor_hronir_uuid, forking_dir, ratings_dir):
    original_fork_csv_dir = storage.data_manager.fork_csv_dir
    original_ratings_csv_dir = storage.data_manager.ratings_csv_dir
    original_initialized = storage.data_manager._initialized
    db_cleared_by_this_run = False

    try:
        storage.data_manager.fork_csv_dir = forking_dir
        storage.data_manager.ratings_csv_dir = ratings_dir
        storage.data_manager._initialized = False
        storage.data_manager.clear_in_memory_data()
        db_cleared_by_this_run = True
        storage.data_manager.initialize_and_load(clear_existing_data=False)

        df = ratings.get_ranking(
            position=position,
            predecessor_hronir_uuid=predecessor_hronir_uuid,
            # session argument removed
        )
        return df
    finally:
        storage.data_manager.fork_csv_dir = original_fork_csv_dir
        storage.data_manager.ratings_csv_dir = original_ratings_csv_dir
        storage.data_manager._initialized = original_initialized
        if db_cleared_by_this_run and storage.data_manager._initialized:
            storage.data_manager.clear_in_memory_data()


UUID_A = "hr-a"
UUID_B = "hr-b"
UUID_C = "hr-c"
PREDECESSOR_POS1 = "pred-pos1"


def test_get_ranking(tmp_path: Path):
    ratings_dir_test_var = tmp_path / "ratings"
    ratings_dir_test_var.mkdir()
    forking_path_dir = tmp_path / "forking_path"
    forking_path_dir.mkdir()

    fork_data = [
        {"position": 1, "prev_uuid": PREDECESSOR_POS1, "uuid": UUID_A, "fork_uuid": "fork-a"},
        {"position": 1, "prev_uuid": PREDECESSOR_POS1, "uuid": UUID_B, "fork_uuid": "fork-b"},
        {"position": 1, "prev_uuid": PREDECESSOR_POS1, "uuid": UUID_C, "fork_uuid": "fork-c"},
    ]
    pd.DataFrame(fork_data).to_csv(forking_path_dir / "test_forks.csv", index=False)

    votes_for_pos1 = [
        {"uuid": "vote1", "voter": "v1", "winner": UUID_A, "loser": UUID_B},
        {"uuid": "vote2", "voter": "v2", "winner": UUID_A, "loser": UUID_C},
        {"uuid": "vote3", "voter": "v3", "winner": UUID_B, "loser": UUID_A},
    ]
    pd.DataFrame(votes_for_pos1).to_csv(ratings_dir_test_var / "position_001.csv", index=False)

    df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=PREDECESSOR_POS1,
        forking_dir=forking_path_dir,
        ratings_dir=ratings_dir_test_var,
    )

    assert list(df["hrönir_uuid"]) == [UUID_A, UUID_B, UUID_C]

    row_a = df[df["hrönir_uuid"] == UUID_A].iloc[0]
    row_b = df[df["hrönir_uuid"] == UUID_B].iloc[0]
    row_c = df[df["hrönir_uuid"] == UUID_C].iloc[0]

    assert row_a["wins"] == 2 and row_a["losses"] == 1
    assert row_a["elo_rating"] == 1513

    assert row_b["wins"] == 1 and row_b["losses"] == 1
    assert row_b["elo_rating"] == 1502

    assert row_c["wins"] == 0 and row_c["losses"] == 1
    assert row_c["elo_rating"] == 1485
