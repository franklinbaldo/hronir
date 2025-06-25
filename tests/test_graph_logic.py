from pathlib import Path

import pandas as pd

from hronir_encyclopedia import (
    graph_logic,
    storage,
)
from hronir_encyclopedia.models import Path as PathModel


def _setup_data_manager_and_check_consistency(fork_dir_path: Path):
    """Helper to setup DataManager, load data, and check consistency."""
    original_fork_csv_dir = storage.data_manager.fork_csv_dir
    original_ratings_csv_dir = storage.data_manager.ratings_csv_dir
    original_initialized = storage.data_manager._initialized
    db_cleared_by_this_run = False

    try:
        storage.data_manager.fork_csv_dir = fork_dir_path
        dummy_ratings_dir = fork_dir_path.parent / "dummy_ratings_for_graph_test"
        dummy_ratings_dir.mkdir(exist_ok=True)
        storage.data_manager.ratings_csv_dir = dummy_ratings_dir

        storage.data_manager._initialized = False
        storage.data_manager.clear_in_memory_data()
        db_cleared_by_this_run = True
        storage.data_manager.initialize_and_load(clear_existing_data=True)

        return graph_logic.is_narrative_consistent()
    finally:
        storage.data_manager.fork_csv_dir = original_fork_csv_dir
        storage.data_manager.ratings_csv_dir = original_ratings_csv_dir
        storage.data_manager._initialized = original_initialized
        if db_cleared_by_this_run and storage.data_manager._initialized:
            storage.data_manager.clear_in_memory_data()


def test_is_narrative_consistent(tmp_path: Path):
    fork_dir = tmp_path / "forking_path"
    fork_dir.mkdir()

    # Generate UUIDs for testing using storage.compute_narrative_path_uuid
    hr_uuid_A_str = "hr_A_content"
    hr_uuid_B_str = "hr_B_content"
    hr_uuid_C_str = "hr_C_content"

    # All UUIDs must be v5 for PathModel
    hr_uuid_A = storage.compute_narrative_path_uuid(0, "namespace_A", hr_uuid_A_str)
    hr_uuid_B = storage.compute_narrative_path_uuid(0, "namespace_B", hr_uuid_B_str)
    hr_uuid_C = storage.compute_narrative_path_uuid(0, "namespace_C", hr_uuid_C_str)

    path_uuid_fA = storage.compute_narrative_path_uuid(0, "", str(hr_uuid_A))
    path_uuid_fB = storage.compute_narrative_path_uuid(1, str(hr_uuid_A), str(hr_uuid_B))
    path_uuid_fC = storage.compute_narrative_path_uuid(2, str(hr_uuid_B), str(hr_uuid_C))

    # For cycle test, ensure hrönir UUIDs are consistent for the cycle
    path_uuid_fA_cycle = storage.compute_narrative_path_uuid(0, "", str(hr_uuid_A))
    path_uuid_fB_cycle = storage.compute_narrative_path_uuid(1, str(hr_uuid_A), str(hr_uuid_B))
    path_uuid_fC_cycle = storage.compute_narrative_path_uuid(2, str(hr_uuid_B), str(hr_uuid_C))
    path_uuid_fX_cycle = storage.compute_narrative_path_uuid(3, str(hr_uuid_C), str(hr_uuid_A))

    # Test 1: Consistent graph
    df_consistent_data = [
        {
            "position": 0,
            "prev_uuid": None,
            "uuid": hr_uuid_A,
            "path_uuid": path_uuid_fA,
            "status": "PENDING",
        },
        {
            "position": 1,
            "prev_uuid": hr_uuid_A,
            "uuid": hr_uuid_B,
            "path_uuid": path_uuid_fB,
            "status": "PENDING",
        },
        {
            "position": 2,
            "prev_uuid": hr_uuid_B,
            "uuid": hr_uuid_C,
            "path_uuid": path_uuid_fC,
            "status": "PENDING",
        },
    ]
    validated_consistent_data = [
        PathModel(**item).model_dump(mode="json") for item in df_consistent_data
    ]
    df_consistent = pd.DataFrame(validated_consistent_data)
    df_consistent.to_csv(fork_dir / "path_consistent.csv", index=False)
    assert _setup_data_manager_and_check_consistency(fork_dir)

    (fork_dir / "path_consistent.csv").unlink()

    # Test 2: Graph with a cycle
    df_cycle_nodes_data = [
        {
            "position": 0,
            "prev_uuid": None,
            "uuid": hr_uuid_A,
            "path_uuid": path_uuid_fA_cycle,
            "status": "PENDING",
        },
        {
            "position": 1,
            "prev_uuid": hr_uuid_A,
            "uuid": hr_uuid_B,
            "path_uuid": path_uuid_fB_cycle,
            "status": "PENDING",
        },
        {
            "position": 2,
            "prev_uuid": hr_uuid_B,
            "uuid": hr_uuid_C,
            "path_uuid": path_uuid_fC_cycle,
            "status": "PENDING",
        },
        {
            "position": 3,
            "prev_uuid": hr_uuid_C,
            "uuid": hr_uuid_A,
            "path_uuid": path_uuid_fX_cycle,
            "status": "PENDING",
        },
    ]
    validated_cycle_data = [
        PathModel(**item).model_dump(mode="json") for item in df_cycle_nodes_data
    ]
    df_cycle_nodes = pd.DataFrame(validated_cycle_data)
    df_cycle_nodes.to_csv(fork_dir / "path_cycle.csv", index=False)
    assert not _setup_data_manager_and_check_consistency(fork_dir)
