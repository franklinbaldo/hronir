from pathlib import Path

import pandas as pd

from hronir_encyclopedia import (
    ratings,
    storage,
)
from hronir_encyclopedia.models import Path as PathModel, Vote # For direct data creation
import uuid # For UUID creation if needed for model instances


# Helper function to call get_ranking with a clean DataManager state
def _call_get_ranking_with_setup(position, predecessor_hronir_uuid):
    """
    Calls ratings.get_ranking.
    Assumes DataManager is already configured by conftest.py to use a test DuckDB.
    This helper ensures data is cleared before the call (though tests should populate data).
    """
    try:
        # DataManager should be initialized by conftest. Ensure it's clean.
        if not storage.data_manager._initialized:
             storage.data_manager.initialize_and_load(clear_existing_data=True)
        else:
            storage.data_manager.clear_in_memory_data()
            storage.data_manager.save_all_data() # commit the clear

        # Ensure any data added by tests is committed before get_ranking is called
        storage.data_manager.save_all_data()

        df = ratings.get_ranking(
            position=position,
            predecessor_hronir_uuid=predecessor_hronir_uuid,
        )
        return df
    finally:
        # Clean up data from the test DB after the test
        if storage.data_manager._initialized:
            storage.data_manager.clear_in_memory_data()
            storage.data_manager.save_all_data() # commit the clear


UUID_A = "hr-a" # These are hrönir UUIDs (content UUIDs)
UUID_B = "hr-b"
UUID_C = "hr-c"
PREDECESSOR_POS1 = "pred-pos1"


def test_get_ranking(): # Removed tmp_path
    # Path data (fork_uuid is path_uuid, uuid is hrönir_uuid)
    path_data_list = [
        {"path_uuid": "fork-a", "position": 1, "prev_uuid": PREDECESSOR_POS1, "uuid": UUID_A, "status": "PENDING"},
        {"path_uuid": "fork-b", "position": 1, "prev_uuid": PREDECESSOR_POS1, "uuid": UUID_B, "status": "PENDING"},
        {"path_uuid": "fork-c", "position": 1, "prev_uuid": PREDECESSOR_POS1, "uuid": UUID_C, "status": "PENDING"},
    ]
    for item in path_data_list:
        # Ensure UUIDs are actual UUID objects for the model if they are not just placeholder strings
        # For this test, assuming PREDECESSOR_POS1, UUID_A etc. are valid UUID strings or convert them.
        # For simplicity, if they are just strings, let's ensure PathModel can handle them or cast them.
        # The model expects prev_uuid and uuid to be uuid.UUID.
        # Let's generate them on the fly if they are simple strings for test clarity.
        path_model_data = {
            "path_uuid": uuid.uuid5(uuid.NAMESPACE_DNS, item["path_uuid"]), # Make it a UUID
            "position": item["position"],
            "prev_uuid": uuid.uuid5(uuid.NAMESPACE_DNS, item["prev_uuid"]) if item["prev_uuid"] else None,
            "uuid": uuid.uuid5(uuid.NAMESPACE_DNS, item["uuid"]),
            "status": item["status"]
        }
        storage.data_manager.add_path(PathModel(**path_model_data))

    # Vote data (voter is path_uuid of the voting path, winner/loser are hrönir_uuids)
    votes_data_list = [
        {"uuid": "vote1", "voter": str(uuid.uuid5(uuid.NAMESPACE_DNS, "voter-path-1")), "winner": UUID_A, "loser": UUID_B, "position": 1},
        {"uuid": "vote2", "voter": str(uuid.uuid5(uuid.NAMESPACE_DNS, "voter-path-2")), "winner": UUID_A, "loser": UUID_C, "position": 1},
        {"uuid": "vote3", "voter": str(uuid.uuid5(uuid.NAMESPACE_DNS, "voter-path-3")), "winner": UUID_B, "loser": UUID_A, "position": 1},
    ]
    for item in votes_data_list:
        # Ensure winner/loser are valid UUIDs if they are simple strings
        vote_model_data = {
            "uuid": uuid.uuid5(uuid.NAMESPACE_DNS, item["uuid"]), # Make it a UUID
            "voter": item["voter"], # Voter path_uuid string
            "winner": uuid.uuid5(uuid.NAMESPACE_DNS, item["winner"]), # hrönir uuid
            "loser": uuid.uuid5(uuid.NAMESPACE_DNS, item["loser"]),   # hrönir uuid
            "position": item["position"]
        }
        storage.data_manager.add_vote(Vote(**vote_model_data))
    storage.data_manager.save_all_data()

    # For get_ranking, predecessor_hronir_uuid should be the actual hrönir UUID string
    predecessor_hr_uuid_for_call = str(uuid.uuid5(uuid.NAMESPACE_DNS, PREDECESSOR_POS1))

    df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=predecessor_hr_uuid_for_call,
    )

    # Generate expected UUID strings as they would be after uuid.uuid5 conversion
    expected_uuid_a_str = str(uuid.uuid5(uuid.NAMESPACE_DNS, UUID_A))
    expected_uuid_b_str = str(uuid.uuid5(uuid.NAMESPACE_DNS, UUID_B))
    expected_uuid_c_str = str(uuid.uuid5(uuid.NAMESPACE_DNS, UUID_C))

    assert list(df["hrönir_uuid"]) == [expected_uuid_a_str, expected_uuid_b_str, expected_uuid_c_str]

    row_a = df[df["hrönir_uuid"] == expected_uuid_a_str].iloc[0]
    row_b = df[df["hrönir_uuid"] == expected_uuid_b_str].iloc[0]
    row_c = df[df["hrönir_uuid"] == expected_uuid_c_str].iloc[0]

    assert row_a["wins"] == 2 and row_a["losses"] == 1
    assert row_a["elo_rating"] == 1513

    assert row_b["wins"] == 1 and row_b["losses"] == 1
    assert row_b["elo_rating"] == 1502

    assert row_c["wins"] == 0 and row_c["losses"] == 1
    assert row_c["elo_rating"] == 1485
