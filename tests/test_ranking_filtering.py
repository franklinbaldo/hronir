import uuid

from hronir_encyclopedia import storage  # Added for DataManager
from hronir_encyclopedia.ratings import get_ranking


# Helper para criar UUIDs de teste
def _uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))


# Removed temp_data_dir fixture as it's no longer needed for CSV creation.
# from hronir_encyclopedia.models import Path as PathModel, Vote # Moved import lower for context if needed or keep here

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

        df = get_ranking(
            position=position,
            predecessor_hronir_uuid=predecessor_hronir_uuid,
        )
        return df
    finally:
        # Clean up data from the test DB after the test
        storage.data_manager.clear_in_memory_data()
        storage.data_manager.save_all_data()  # commit the clear


# Hrönirs
H0_ROOT = _uuid("root_hrönir_for_pos0")
H1A = _uuid("hrönir_1A_pos1_from_H0_ROOT")
H1B = _uuid("hrönir_1B_pos1_from_H0_ROOT")
H1C = _uuid("hrönir_1C_pos1_from_H0_ROOT")
H1D_OTHER_PARENT = _uuid("hrönir_1D_pos1_from_OTHER")
H2A_FROM_H1A = _uuid("hrönir_2A_pos2_from_H1A")

# Forking path data
forks_main_data = [
    {
        "position": 0,
        "prev_uuid": None,
        "uuid": uuid.UUID(H0_ROOT),
        "path_uuid": uuid.UUID(_uuid("fork_0_H0_ROOT")),
    },
    {
        "position": 1,
        "prev_uuid": uuid.UUID(H0_ROOT),
        "uuid": uuid.UUID(H1A),
        "path_uuid": uuid.UUID(_uuid("fork_1_H0_ROOT_H1A")),
    },
    {
        "position": 1,
        "prev_uuid": uuid.UUID(H0_ROOT),
        "uuid": uuid.UUID(H1B),
        "path_uuid": uuid.UUID(_uuid("fork_1_H0_ROOT_H1B")),
    },
    {
        "position": 1,
        "prev_uuid": uuid.UUID(H0_ROOT),
        "uuid": uuid.UUID(H1C),
        "path_uuid": uuid.UUID(_uuid("fork_1_H0_ROOT_H1C")),
    },
    {
        "position": 1,
        "prev_uuid": uuid.UUID(_uuid("OTHER_PARENT_UUID")),
        "uuid": uuid.UUID(H1D_OTHER_PARENT),
        "path_uuid": uuid.UUID(_uuid("fork_1_OTHER_H1D")),
    },
    {
        "position": 2,
        "prev_uuid": uuid.UUID(H1A),
        "uuid": uuid.UUID(H2A_FROM_H1A),
        "path_uuid": uuid.UUID(_uuid("fork_2_H1A_H2A")),
    },
]

ratings_pos1_data = [
    {
        "uuid": uuid.UUID(_uuid("vote1")),
        "voter": str(uuid.UUID(_uuid("voter1"))),
        "winner": uuid.UUID(H1A),
        "loser": uuid.UUID(H1B),
        "position": 1,
    },
    {
        "uuid": uuid.UUID(_uuid("vote2")),
        "voter": str(uuid.UUID(_uuid("voter2"))),
        "winner": uuid.UUID(H1A),
        "loser": uuid.UUID(H1B),
        "position": 1,
    },
    {
        "uuid": uuid.UUID(_uuid("vote3")),
        "voter": str(uuid.UUID(_uuid("voter3"))),
        "winner": uuid.UUID(H1B),
        "loser": uuid.UUID(H1A),
        "position": 1,
    },
    {
        "uuid": uuid.UUID(_uuid("vote4")),
        "voter": str(uuid.UUID(_uuid("voter4"))),
        "winner": uuid.UUID(H1A),
        "loser": uuid.UUID(H1D_OTHER_PARENT),
        "position": 1,
    },
    {
        "uuid": uuid.UUID(_uuid("vote5")),
        "voter": str(uuid.UUID(_uuid("voter5"))),
        "winner": uuid.UUID(H1D_OTHER_PARENT),
        "loser": uuid.UUID(H1B),
        "position": 1,
    },
]

ratings_pos0_data = []
ratings_pos2_data = []

# Removed create_csv function as data will be added directly to DB.


def test_get_ranking_filters_by_canonical_predecessor():  # Removed temp_data_dir
    # Setup data directly in DB

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        paths_data=forks_main_data,
        votes_data=ratings_pos1_data,
    )

    assert not ranking_df.empty
    expected_heirs = {H1A, H1B, H1C}
    retrieved_heirs = set(ranking_df["hrönir_uuid"].tolist())
    assert retrieved_heirs == expected_heirs

    h1a_data = ranking_df[ranking_df["hrönir_uuid"] == H1A].iloc[0]
    h1b_data = ranking_df[ranking_df["hrönir_uuid"] == H1B].iloc[0]
    h1c_data = ranking_df[ranking_df["hrönir_uuid"] == H1C].iloc[0]

    assert h1a_data["wins"] == 2
    assert h1a_data["losses"] == 1
    assert h1a_data["elo_rating"] == 1515

    assert h1b_data["wins"] == 1
    assert h1b_data["losses"] == 2
    assert h1b_data["elo_rating"] == 1485

    assert h1c_data["wins"] == 0
    assert h1c_data["losses"] == 0
    assert h1c_data["elo_rating"] == 1500

    assert ranking_df.iloc[0]["hrönir_uuid"] == H1A
    assert ranking_df.iloc[1]["hrönir_uuid"] == H1C
    assert ranking_df.iloc[2]["hrönir_uuid"] == H1B


def test_get_ranking_no_heirs_for_predecessor():  # Removed temp_data_dir
    # Setup data directly in DB (same as previous test for path data)

    NON_EXISTENT_PREDECESSOR = _uuid("non_existent_predecessor")
    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=NON_EXISTENT_PREDECESSOR,
        paths_data=forks_main_data,
        votes_data=ratings_pos1_data,
    )
    assert ranking_df.empty


def test_get_ranking_no_votes_for_heirs():  # Removed temp_data_dir
    simple_forks_data = [
        {
            "position": 1,
            "prev_uuid": uuid.UUID(H0_ROOT),
            "uuid": uuid.UUID(H1A),
            "path_uuid": uuid.UUID(_uuid("f1")),
        },
        {
            "position": 1,
            "prev_uuid": uuid.UUID(H0_ROOT),
            "uuid": uuid.UUID(H1B),
            "path_uuid": uuid.UUID(_uuid("f2")),
        },
    ]

    ranking_df = _call_get_ranking_with_setup(
        position=1, predecessor_hronir_uuid=H0_ROOT, paths_data=simple_forks_data, votes_data=[]
    )
    expected_heirs = {H1A, H1B}
    retrieved_heirs = set(ranking_df["hrönir_uuid"].tolist())
    assert retrieved_heirs == expected_heirs

    for _, row in ranking_df.iterrows():
        assert row["elo_rating"] == 1500
        assert row["wins"] == 0
        assert row["losses"] == 0
        assert row["games_played"] == 0


def test_get_ranking_for_position_0_no_predecessor():  # Removed temp_data_dir
    H0_ALT = _uuid("hrönir_0_ALT_pos0")
    forks_for_pos0_data = forks_main_data + [
        {
            "position": 0,
            "prev_uuid": None,
            "uuid": uuid.UUID(H0_ALT),
            "path_uuid": uuid.UUID(_uuid("fork_0_H0_ALT")),
        }
    ]
    for fork_data_item in forks_for_pos0_data:
        path_model_data = {
            "path_uuid": fork_data_item["path_uuid"],
            "position": fork_data_item["position"],
            "prev_uuid": fork_data_item["prev_uuid"],
            "uuid": fork_data_item["uuid"],
            "status": "PENDING",
        }
        storage.data_manager.add_path(PathModel(**path_model_data))

    ratings_data_pos0_duels_data = [
        {
            "uuid": uuid.UUID(_uuid("v_p0_1")),
            "voter": str(uuid.UUID(_uuid("v_p0_v1"))),
            "winner": uuid.UUID(H0_ROOT),
            "loser": uuid.UUID(H0_ALT),
            "position": 0,
        },
        {
            "uuid": uuid.UUID(_uuid("v_p0_2")),
            "voter": str(uuid.UUID(_uuid("v_p0_v2"))),
            "winner": uuid.UUID(H0_ROOT),
            "loser": uuid.UUID(H0_ALT),
            "position": 0,
        },
    ]
    for rating_data_item in ratings_data_pos0_duels_data:
        storage.data_manager.add_vote(Vote(**rating_data_item))
    storage.data_manager.save_all_data()

    ranking_df = _call_get_ranking_with_setup(
        position=0,
        predecessor_hronir_uuid=None,
        paths_data=forks_for_pos0_data,
        votes_data=ratings_data_pos0_duels_data,
    )

    assert len(ranking_df) == 2
    expected_pos0_hrs = {H0_ROOT, H0_ALT}
    retrieved_pos0_hrs = set(ranking_df["hrönir_uuid"].tolist())
    assert retrieved_pos0_hrs == expected_pos0_hrs

    h0_root_data = ranking_df[ranking_df["hrönir_uuid"] == H0_ROOT].iloc[0]
    h0_alt_data = ranking_df[ranking_df["hrönir_uuid"] == H0_ALT].iloc[0]

    assert h0_root_data["elo_rating"] == 1531
    assert h0_root_data["wins"] == 2
    assert h0_alt_data["elo_rating"] == 1469
    assert h0_alt_data["losses"] == 2


def test_get_ranking_empty_paths_table():  # Renamed, removed temp_data_dir
    # No paths added to DB.
    # Add ratings, though they won't be used if no paths match.
    for rating_data_item in ratings_pos1_data:
        vote_model_data = {
            "uuid": rating_data_item["uuid"],
            "position": 1,
            "voter": rating_data_item["voter"],
            "winner": rating_data_item["winner"],
            "loser": rating_data_item["loser"],
        }
        storage.data_manager.add_vote(Vote(**vote_model_data))
    storage.data_manager.save_all_data()

    ranking_df = _call_get_ranking_with_setup(
        position=1, predecessor_hronir_uuid=H0_ROOT, paths_data=[], votes_data=ratings_pos1_data
    )
    assert ranking_df.empty


def test_get_ranking_empty_votes_table():  # Renamed, removed temp_data_dir
    # Add paths to DB
    # Setup data directly in DB (same as previous test for path data)
    # Data is now passed via _call_get_ranking_with_setup, so direct DB setup is removed from here.

    ranking_df = _call_get_ranking_with_setup(
        position=1, predecessor_hronir_uuid=H0_ROOT, paths_data=forks_main_data, votes_data=[]
    )
    for _, row in ranking_df.iterrows():
        assert row["elo_rating"] == 1500
    # Removed second part of the test that dealt with zero-byte CSV files as it's no longer applicable.


def test_get_ranking_malformed_data_handling_equivalent():  # Renamed, removed temp_data_dir
    # This test used to check malformed CSVs.
    # With direct DB insertion, "malformed" data means data that Pydantic models reject
    # or that violates DB constraints. DataManager/DuckDBDataManager should handle this.
    # For get_ranking, if data is already in DB, it's assumed to be valid per models.
    # We can test how get_ranking handles incomplete but structurally valid data if necessary,
    # but the concept of "malformed CSV" doesn't directly translate.
    # Here, we'll add valid minimal data and expect default Elo.
    path_data = {
        "path_uuid": _uuid("f1"),
        "position": 1,
        "prev_uuid": uuid.UUID(H0_ROOT),
        "uuid": uuid.UUID(H1A),
        "status": "PENDING",
    }
    storage.data_manager.add_path(PathModel(**path_data))
    storage.data_manager.save_all_data()  # No votes

    ranking_df = _call_get_ranking_with_setup(
        position=1, predecessor_hronir_uuid=H0_ROOT, paths_data=[path_data], votes_data=[]
    )
    assert ranking_df.iloc[0]["hrönir_uuid"] == H1A
    assert ranking_df.iloc[0]["elo_rating"] == 1500


# Removed test_get_ranking_malformed_ratings_csv as it's CSV specific.


def test_get_ranking_canonical_predecessor_none_not_pos_0():  # Removed temp_data_dir
    # Add main fork data
    # Data is now passed via _call_get_ranking_with_setup, so direct DB setup is removed from here.

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=None,  # Key part of this test
        paths_data=forks_main_data,
        votes_data=ratings_pos1_data,
    )
    assert ranking_df.empty


# Removed test_get_ranking_narrative_paths_missing_columns (CSV specific)
# Removed test_get_ranking_ratings_path_missing_columns (CSV specific)
