from pathlib import Path

import pandas as pd

from hronir_encyclopedia import graph_logic
from hronir_encyclopedia import storage # Added for DataManager setup


def _setup_data_manager_and_check_consistency(fork_dir_path: Path):
    """Helper to setup DataManager, load data, and check consistency."""
    original_fork_csv_dir = storage.data_manager.fork_csv_dir
    original_ratings_csv_dir = storage.data_manager.ratings_csv_dir # Though not used by graph_logic
    original_initialized = storage.data_manager._initialized
    db_cleared_by_this_run = False

    try:
        storage.data_manager.fork_csv_dir = fork_dir_path
        # Set ratings_dir to a dummy to avoid issues if it's expected by DataManager init
        dummy_ratings_dir = fork_dir_path.parent / "dummy_ratings_for_graph_test"
        dummy_ratings_dir.mkdir(exist_ok=True)
        storage.data_manager.ratings_csv_dir = dummy_ratings_dir

        storage.data_manager._initialized = False
        storage.data_manager.clear_in_memory_data()
        db_cleared_by_this_run = True
        storage.data_manager.initialize_and_load(clear_existing_data=False)

        # is_narrative_consistent can get its own session if None is passed
        return graph_logic.is_narrative_consistent(session=None)
    finally:
        storage.data_manager.fork_csv_dir = original_fork_csv_dir
        storage.data_manager.ratings_csv_dir = original_ratings_csv_dir
        storage.data_manager._initialized = original_initialized
        if db_cleared_by_this_run and storage.data_manager._initialized:
             storage.data_manager.clear_in_memory_data()


def test_is_narrative_consistent(tmp_path: Path):
    fork_dir = tmp_path / "forking_path"
    fork_dir.mkdir()

    # Test 1: Consistent graph
    df_consistent = pd.DataFrame(
        [
            {"position": 0, "prev_uuid": "", "uuid": "A", "fork_uuid": "fA", "status": "PENDING"},
            {"position": 1, "prev_uuid": "A", "uuid": "B", "fork_uuid": "fB", "status": "PENDING"},
            {"position": 2, "prev_uuid": "B", "uuid": "C", "fork_uuid": "fC", "status": "PENDING"},
        ]
    )
    df_consistent.to_csv(fork_dir / "path_consistent.csv", index=False)
    assert _setup_data_manager_and_check_consistency(fork_dir)

    # Clean up the CSV for the next part of the test to avoid interference
    (fork_dir / "path_consistent.csv").unlink()

    # Test 2: Graph with a cycle
    df_cycle_nodes = pd.DataFrame(
        [
            {"position": 0, "prev_uuid": "", "uuid": "A", "fork_uuid": "fA_cycle", "status": "PENDING"},
            {"position": 1, "prev_uuid": "A", "uuid": "B", "fork_uuid": "fB_cycle", "status": "PENDING"},
            {"position": 2, "prev_uuid": "B", "uuid": "C", "fork_uuid": "fC_cycle", "status": "PENDING"},
            {"position": 3, "prev_uuid": "C", "uuid": "A", "fork_uuid": "fX_cycle_back_to_A", "status": "PENDING"}, # Cycle C -> A
        ]
    )
    df_cycle_nodes.to_csv(fork_dir / "path_cycle.csv", index=False)
    assert not _setup_data_manager_and_check_consistency(fork_dir)
