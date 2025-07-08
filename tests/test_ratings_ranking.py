

import uuid  # For UUID creation if needed for model instances

from hronir_encyclopedia import (
    ratings,
    storage,
)
from hronir_encyclopedia.models import Path as PathModel  # For direct data creation
from hronir_encyclopedia.models import Vote


# Helper function to call get_ranking with a clean DataManager state
def _call_get_ranking_with_setup(position, predecessor_hronir_uuid, paths_data, votes_data):
    """
    Calls ratings.get_ranking.
    Assumes DataManager is already configured by conftest.py to use a test DuckDB.
    This helper ensures data is cleared before the call and test-specific data is loaded.
    """
    try:
        # DataManager should be initialized by conftest. Ensure it's clean.
        storage.data_manager.clear_in_memory_data()

        # Load test-specific data
        for path_data_item in paths_data:
            storage.data_manager.add_path(PathModel(**path_data_item))

        for vote_data_item in votes_data:
            storage.data_manager.add_vote(Vote(**vote_data_item))

        storage.data_manager.save_all_data()  # commit the data

        df = ratings.get_ranking(
            position=position,
            predecessor_hronir_uuid=predecessor_hronir_uuid,
        )
        return df
    finally:
        # Clean up data from the test DB after the test
        storage.data_manager.clear_in_memory_data()
        storage.data_manager.save_all_data()  # commit the clear


UUID_A = "hr-a"  # These are hrönir UUIDs (content UUIDs)
UUID_B = "hr-b"
UUID_C = "hr-c"
PREDECESSOR_POS1 = "pred-pos1"


def test_get_ranking():  # Removed tmp_path
    # Path data (fork_uuid is path_uuid, uuid is hrönir_uuid)
    path_data_list = [
        {
            "path_uuid": uuid.uuid5(uuid.NAMESPACE_DNS, "fork-a"),
            "position": 1,
            "prev_uuid": uuid.uuid5(uuid.NAMESPACE_DNS, PREDECESSOR_POS1),
            "uuid": uuid.uuid5(uuid.NAMESPACE_DNS, UUID_A),
            "status": "PENDING",
        },
        {
            "path_uuid": uuid.uuid5(uuid.NAMESPACE_DNS, "fork-b"),
            "position": 1,
            "prev_uuid": uuid.uuid5(uuid.NAMESPACE_DNS, PREDECESSOR_POS1),
            "uuid": uuid.uuid5(uuid.NAMESPACE_DNS, UUID_B),
            "status": "PENDING",
        },
        {
            "path_uuid": uuid.uuid5(uuid.NAMESPACE_DNS, "fork-c"),
            "position": 1,
            "prev_uuid": uuid.uuid5(uuid.NAMESPACE_DNS, PREDECESSOR_POS1),
            "uuid": uuid.uuid5(uuid.NAMESPACE_DNS, UUID_C),
            "status": "PENDING",
        },
    ]
    for item in path_data_list:
        storage.data_manager.add_path(PathModel(**item))

    # Vote data (voter is path_uuid of the voting path, winner/loser are hrönir_uuids)
    votes_data_list = [
        {
            "uuid": uuid.uuid5(uuid.NAMESPACE_DNS, "vote1"),
            "voter": str(uuid.uuid5(uuid.NAMESPACE_DNS, "voter-path-1")),
            "winner": uuid.uuid5(uuid.NAMESPACE_DNS, UUID_A),
            "loser": uuid.uuid5(uuid.NAMESPACE_DNS, UUID_B),
            "position": 1,
        },
        {
            "uuid": uuid.uuid5(uuid.NAMESPACE_DNS, "vote2"),
            "voter": str(uuid.uuid5(uuid.NAMESPACE_DNS, "voter-path-2")),
            "winner": uuid.uuid5(uuid.NAMESPACE_DNS, UUID_A),
            "loser": uuid.uuid5(uuid.NAMESPACE_DNS, UUID_C),
            "position": 1,
        },
        {
            "uuid": uuid.uuid5(uuid.NAMESPACE_DNS, "vote3"),
            "voter": str(uuid.uuid5(uuid.NAMESPACE_DNS, "voter-path-3")),
            "winner": uuid.uuid5(uuid.NAMESPACE_DNS, UUID_B),
            "loser": uuid.uuid5(uuid.NAMESPACE_DNS, UUID_A),
            "position": 1,
        },
    ]
    for item in votes_data_list:
        storage.data_manager.add_vote(Vote(**item))
    storage.data_manager.save_all_data()

    # For get_ranking, predecessor_hronir_uuid should be the actual hrönir UUID string
    predecessor_hr_uuid_for_call = str(uuid.uuid5(uuid.NAMESPACE_DNS, PREDECESSOR_POS1))

    df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=predecessor_hr_uuid_for_call,
        paths_data=path_data_list,
        votes_data=votes_data_list,
    )

    # Generate expected UUID strings as they would be after uuid.uuid5 conversion
    expected_uuid_a_str = str(uuid.uuid5(uuid.NAMESPACE_DNS, UUID_A))
    expected_uuid_b_str = str(uuid.uuid5(uuid.NAMESPACE_DNS, UUID_B))
    expected_uuid_c_str = str(uuid.uuid5(uuid.NAMESPACE_DNS, UUID_C))

    assert list(df["hrönir_uuid"]) == [
        expected_uuid_a_str,
        expected_uuid_b_str,
        expected_uuid_c_str,
    ]

    row_a = df[df["hrönir_uuid"] == expected_uuid_a_str].iloc[0]
    row_b = df[df["hrönir_uuid"] == expected_uuid_b_str].iloc[0]
    row_c = df[df["hrönir_uuid"] == expected_uuid_c_str].iloc[0]

    assert row_a["wins"] == 2 and row_a["losses"] == 1
    assert row_a["elo_rating"] == 1513

    assert row_b["wins"] == 1 and row_b["losses"] == 1
    assert row_b["elo_rating"] == 1502

    assert row_c["wins"] == 0 and row_c["losses"] == 1
    assert row_c["elo_rating"] == 1485
