import uuid  # Added for uuid.uuid5
from pathlib import Path

from hronir_encyclopedia import (
    graph_logic,
    storage,
)
from hronir_encyclopedia.models import Path as PathModel


def _setup_and_check_consistency(paths_data: list[PathModel]):
    """
    Helper to setup DataManager with specific paths and check narrative consistency.
    Assumes DataManager is configured by conftest.py to use a test DuckDB.
    """
    try:
        # Ensure DataManager is initialized and its DB is clean for the test
        if not storage.data_manager._initialized:
            storage.data_manager.initialize_and_load(clear_existing_data=True)
        else:
            storage.data_manager.clear_in_memory_data()  # Clears tables in the test DB

        # Add provided path data to the database
        for path_model_data in paths_data:
            # If paths_data contains dicts, they need to be PathModel instances
            # Assuming paths_data will be list of PathModel instances or compatible dicts
            if isinstance(path_model_data, dict):
                path_to_add = PathModel(**path_model_data)
            else:  # Assumes PathModel instance
                path_to_add = path_model_data
            storage.data_manager.add_path(path_to_add)

        # Commit data if add_path doesn't auto-commit (DuckDBDataManager.add_path does not auto-commit)
        storage.data_manager.save_all_data()

        return graph_logic.is_narrative_consistent()
    finally:
        # Clean up data from the test DB after the test
        if storage.data_manager._initialized:
            storage.data_manager.clear_in_memory_data()
            storage.data_manager.save_all_data()  # Commit the clear operation


def test_is_narrative_consistent(tmp_path: Path):
    # No longer need fork_dir for CSV files. Data will be added directly to DB.

    # Generate UUIDs for testing using storage.compute_narrative_path_uuid
    hr_uuid_A_str = "hr_A_content"
    hr_uuid_B_str = "hr_B_content"
    hr_uuid_C_str = "hr_C_content"

    # Generate content-based UUIDs for hrönirs
    hr_uuid_A = uuid.uuid5(storage.UUID_NAMESPACE, hr_uuid_A_str)
    hr_uuid_B = uuid.uuid5(storage.UUID_NAMESPACE, hr_uuid_B_str)
    hr_uuid_C = uuid.uuid5(storage.UUID_NAMESPACE, hr_uuid_C_str)

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
    # df_consistent = pd.DataFrame(validated_consistent_data) # No longer creating CSV
    # df_consistent.to_csv(fork_dir / "path_consistent.csv", index=False)
    assert _setup_and_check_consistency(validated_consistent_data)  # Pass data directly

    # (fork_dir / "path_consistent.csv").unlink() # No longer creating CSV

    # Test 2: Graph with a cycle
    df_cycle_nodes_data = [  # This is already a list of dicts compatible with PathModel
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
    # validated_cycle_data = [ # Data is already in suitable format
    #     PathModel(**item).model_dump(mode="json") for item in df_cycle_nodes_data
    # ]
    # df_cycle_nodes = pd.DataFrame(validated_cycle_data) # No longer creating CSV
    # df_cycle_nodes.to_csv(fork_dir / "path_cycle.csv", index=False)
    assert not _setup_and_check_consistency(df_cycle_nodes_data)  # Pass data directly
