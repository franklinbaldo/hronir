import uuid
from pathlib import Path

import pandas as pd
import pytest

from hronir_encyclopedia import storage  # Added for DataManager
from hronir_encyclopedia.ratings import get_ranking


# Helper para criar UUIDs de teste
def _uuid(name: str) -> str:
    return str(uuid.uuid5(uuid.NAMESPACE_DNS, name))


@pytest.fixture
def temp_data_env(tmp_path: Path) -> dict[str, Path]:
    """
    Sets up a temporary, isolated test environment by configuring data paths
    via environment variables and ensuring DataManager singleton is reset.
    Yields a dictionary of relevant paths.
    """
    original_env_vars = {
        "HRONIR_LIBRARY_DIR": os.getenv("HRONIR_LIBRARY_DIR"),
        "HRONIR_DUCKDB_PATH": os.getenv("HRONIR_DUCKDB_PATH"),
        "HRONIR_DATA_DIR": os.getenv("HRONIR_DATA_DIR"),
    }

    library_dir = tmp_path / "test_library"
    data_dir = tmp_path / "test_data"
    db_file = data_dir / "test_db.duckdb"

    library_dir.mkdir(parents=True, exist_ok=True)
    data_dir.mkdir(parents=True, exist_ok=True)

    os.environ["HRONIR_LIBRARY_DIR"] = str(library_dir)
    os.environ["HRONIR_DUCKDB_PATH"] = str(db_file)
    os.environ["HRONIR_DATA_DIR"] = str(data_dir)

    # Reset DataManager singleton instance to ensure it picks up new env vars
    if storage.data_manager._instance is not None:
        if hasattr(storage.data_manager.backend, 'conn') and storage.data_manager.backend.conn is not None:
            try: storage.data_manager.backend.conn.close()
            except Exception: pass
        storage.data_manager._instance = None

    # Yield paths that might be useful for tests, though DM should use env vars
    yield {
        "library_dir": library_dir,
        "data_dir": data_dir,
        "db_file": db_file,
        "narrative_paths_dir": data_dir / "narrative_paths", # If tests still create CSVs for setup
        "ratings_dir": data_dir / "ratings" # If tests still create CSVs for setup
    }

    # Teardown: Restore original environment variables
    for key, value in original_env_vars.items():
        if value is None:
            if key in os.environ: del os.environ[key]
        else:
            os.environ[key] = value

    # Reset DataManager singleton again after test
    if storage.data_manager._instance is not None:
        if hasattr(storage.data_manager.backend, 'conn') and storage.data_manager.backend.conn is not None:
            try: storage.data_manager.backend.conn.close()
            except Exception: pass
        storage.data_manager._instance = None

# Old fixture, to be replaced by temp_data_env
# @pytest.fixture
# def temp_data_dir(tmp_path: Path) -> tuple[Path, Path]:
#     forking_dir = tmp_path / "narrative_paths"
#     ratings_dir = tmp_path / "ratings"
#     forking_dir.mkdir(exist_ok=True)
#     ratings_dir.mkdir(exist_ok=True)
#     return forking_dir, ratings_dir

import os # For os.getenv and os.environ
import datetime # For duel creation timestamps

# Hrönirs
H0_ROOT = _uuid("root_hrönir_for_pos0")
H1A = _uuid("hrönir_1A_pos1_from_H0_ROOT")
H1B = _uuid("hrönir_1B_pos1_from_H0_ROOT")
H1C = _uuid("hrönir_1C_pos1_from_H0_ROOT")
H1D_OTHER_PARENT = _uuid("hrönir_1D_pos1_from_OTHER")
H2A_FROM_H1A = _uuid("hrönir_2A_pos2_from_H1A")

# Forking path data
forks_main_data = [
    {"position": 0, "prev_uuid": "", "uuid": H0_ROOT, "fork_uuid": _uuid("fork_0_H0_ROOT")},
    {"position": 1, "prev_uuid": H0_ROOT, "uuid": H1A, "fork_uuid": _uuid("fork_1_H0_ROOT_H1A")},
    {"position": 1, "prev_uuid": H0_ROOT, "uuid": H1B, "fork_uuid": _uuid("fork_1_H0_ROOT_H1B")},
    {"position": 1, "prev_uuid": H0_ROOT, "uuid": H1C, "fork_uuid": _uuid("fork_1_H0_ROOT_H1C")},
    {
        "position": 1,
        "prev_uuid": _uuid("OTHER_PARENT_UUID"),
        "uuid": H1D_OTHER_PARENT,
        "fork_uuid": _uuid("fork_1_OTHER_H1D"),
    },
    {"position": 2, "prev_uuid": H1A, "uuid": H2A_FROM_H1A, "fork_uuid": _uuid("fork_2_H1A_H2A")},
]

ratings_pos1_data = [
    {
        "uuid": _uuid("vote1"),
        "voter": _uuid("voter1"),
        "winner": H1A,
        "loser": H1B,
    },
    {
        "uuid": _uuid("vote2"),
        "voter": _uuid("voter2"),
        "winner": H1A,
        "loser": H1B,
    },
    {
        "uuid": _uuid("vote3"),
        "voter": _uuid("voter3"),
        "winner": H1B,
        "loser": H1A,
    },
    {"uuid": _uuid("vote4"), "voter": _uuid("voter4"), "winner": H1A, "loser": H1D_OTHER_PARENT},
    {"uuid": _uuid("vote5"), "voter": _uuid("voter5"), "winner": H1D_OTHER_PARENT, "loser": H1B},
]

ratings_pos0_data = []
ratings_pos2_data = []


def create_csv(data: list[dict], path: Path):
    if data:
        pd.DataFrame(data).to_csv(path, index=False)
    else:
        if data == [] and path.name.startswith("position_"):
            pd.DataFrame(columns=["uuid", "voter", "winner", "loser"]).to_csv(path, index=False)
        elif data == [] and path.name.startswith("forks_"):
            pd.DataFrame(columns=["position", "prev_uuid", "uuid", "fork_uuid"]).to_csv(
                path, index=False
            )
        else:
            path.touch()


def test_get_ranking_filters_by_canonical_predecessor(temp_data_env): # Changed fixture
    dm = storage.DataManager()
    dm.clear_in_memory_data()

    # Define Path UUIDs based on Hrönir UUIDs (as per current PathModel logic)
    PATH_0_H0_ROOT = _uuid("fork_0_H0_ROOT") # Path leading to H0_ROOT
    PATH_1_H0_ROOT_H1A = _uuid("fork_1_H0_ROOT_H1A")
    PATH_1_H0_ROOT_H1B = _uuid("fork_1_H0_ROOT_H1B")
    PATH_1_H0_ROOT_H1C = _uuid("fork_1_H0_ROOT_H1C")
    OTHER_PARENT_UUID = _uuid("OTHER_PARENT_UUID")
    PATH_1_OTHER_H1D = _uuid("fork_1_OTHER_H1D") # Path to H1D from a different parent
    PATH_2_H1A_H2A = _uuid("fork_2_H1A_H2A")

    # Add paths
    paths_to_add = [
        storage.PathModel(path_uuid=PATH_0_H0_ROOT, position=0, prev_uuid=None, uuid=uuid.UUID(H0_ROOT)),
        storage.PathModel(path_uuid=PATH_1_H0_ROOT_H1A, position=1, prev_uuid=uuid.UUID(H0_ROOT), uuid=uuid.UUID(H1A)),
        storage.PathModel(path_uuid=PATH_1_H0_ROOT_H1B, position=1, prev_uuid=uuid.UUID(H0_ROOT), uuid=uuid.UUID(H1B)),
        storage.PathModel(path_uuid=PATH_1_H0_ROOT_H1C, position=1, prev_uuid=uuid.UUID(H0_ROOT), uuid=uuid.UUID(H1C)),
        storage.PathModel(path_uuid=PATH_1_OTHER_H1D, position=1, prev_uuid=uuid.UUID(OTHER_PARENT_UUID), uuid=uuid.UUID(H1D_OTHER_PARENT)),
        storage.PathModel(path_uuid=PATH_2_H1A_H2A, position=2, prev_uuid=uuid.UUID(H1A), uuid=uuid.UUID(H2A_FROM_H1A)),
    ]
    for p_model in paths_to_add:
        dm.add_path(p_model)

    # Define Duel IDs (must be unique for each distinct duel instance)
    DUEL_H1A_H1B_1 = _uuid("duel_H1A_H1B_1")
    DUEL_H1A_H1B_2 = _uuid("duel_H1A_H1B_2") # Second duel between A and B
    DUEL_H1B_H1A_1 = _uuid("duel_H1B_H1A_1")
    # DUEL_H1A_H1D  # H1D is not part of this test's ranking context (different parent)
    # DUEL_H1D_H1B  # Same as above

    # Add relevant duels (these are historical, so mark inactive)
    # Vote 1 & 2: H1A wins vs H1B (twice)
    dm.add_pending_duel(1, PATH_1_H0_ROOT_H1A, PATH_1_H0_ROOT_H1B, datetime.datetime.now(datetime.timezone.utc), duel_id_override=DUEL_H1A_H1B_1)
    dm.deactivate_duel(DUEL_H1A_H1B_1)
    # For the second vote where H1A beats H1B again, we need a distinct duel ID if it was a separate duel event.
    # If get_ranking processes votes against the *same* duel instance multiple times, that's different.
    # Assuming distinct duel events for these votes for now.
    dm.add_pending_duel(1, PATH_1_H0_ROOT_H1A, PATH_1_H0_ROOT_H1B, datetime.datetime.now(datetime.timezone.utc), duel_id_override=DUEL_H1A_H1B_2)
    dm.deactivate_duel(DUEL_H1A_H1B_2)

    # Vote 3: H1B wins vs H1A
    dm.add_pending_duel(1, PATH_1_H0_ROOT_H1B, PATH_1_H0_ROOT_H1A, datetime.datetime.now(datetime.timezone.utc), duel_id_override=DUEL_H1B_H1A_1)
    dm.deactivate_duel(DUEL_H1B_H1A_1)

    # Add votes
    VOTING_TOKEN_1, VOTING_TOKEN_2, VOTING_TOKEN_3 = _uuid("vtr1"), _uuid("vtr2"), _uuid("vtr3")
    votes_to_add = [
        storage.Vote(vote_id=_uuid("vote1"), duel_id=uuid.UUID(DUEL_H1A_H1B_1), voting_token_path_uuid=uuid.UUID(VOTING_TOKEN_1), chosen_winner_side='A', position=1), # H1A (as path_A) wins
        storage.Vote(vote_id=_uuid("vote2"), duel_id=uuid.UUID(DUEL_H1A_H1B_2), voting_token_path_uuid=uuid.UUID(VOTING_TOKEN_2), chosen_winner_side='A', position=1), # H1A (as path_A) wins again
        storage.Vote(vote_id=_uuid("vote3"), duel_id=uuid.UUID(DUEL_H1B_H1A_1), voting_token_path_uuid=uuid.UUID(VOTING_TOKEN_3), chosen_winner_side='A', position=1), # H1B (as path_A) wins
    ]
    for v_model in votes_to_add:
        dm.add_vote(v_model)
    dm.save_all_data_to_csvs() # Commit to DB

    ranking_df = get_ranking(
        position=1,
        predecessor_hronir_uuid=H0_ROOT
    )

    assert not ranking_df.empty, "Ranking DataFrame should not be empty"

    expected_heirs = {H1A, H1B, H1C} # H1C has no votes, should appear with base Elo
    retrieved_heirs = set(ranking_df["hrönir_uuid"].tolist())
    assert retrieved_heirs == expected_heirs, f"Retrieved heirs {retrieved_heirs} do not match expected {expected_heirs}"

    # Re-evaluate Elo and win/loss counts based on this specific setup
    # H1A: 2 wins (vs H1B twice), 1 loss (vs H1B once)
    # H1B: 1 win (vs H1A once), 2 losses (vs H1A twice)
    # H1C: 0 wins, 0 losses

    h1a_data = ranking_df[ranking_df["hrönir_uuid"] == H1A].iloc[0]
    h1b_data = ranking_df[ranking_df["hrönir_uuid"] == H1B].iloc[0]
    h1c_data = ranking_df[ranking_df["hrönir_uuid"] == H1C].iloc[0]

    assert h1a_data["wins"] == 2, f"H1A actual wins: {h1a_data['wins']}"
    assert h1a_data["losses"] == 1, f"H1A actual losses: {h1a_data['losses']}"
    # Elo for H1A: Base 1500.
    # Win vs B (+16), Win vs B (+16), Loss vs B (-16) -> Approx 1500 + 16 = 1516. Let's use a range or recompute.
    # Elo calculation:
    # Duel 1 (A vs B, A wins): A: 1500, B: 1500. p(A wins)=0.5. A_new = 1500+32*(1-0.5)=1516. B_new = 1500+32*(0-0.5)=1484
    # Duel 2 (A vs B, A wins): A: 1516, B: 1484. p(A wins)=1/(1+10^((1484-1516)/400)) = 1/(1+10^(-32/400)) = 1/(1+10^-0.08) = 1/(1+0.8317) = 0.5459
    #   A_new = 1516+32*(1-0.5459) = 1516+32*0.4541 = 1516+14.53 = 1530.53 -> 1531
    #   B_new = 1484+32*(0-0.5459) = 1484-14.53 = 1469.47 -> 1469
    # Duel 3 (B vs A, B wins): B: 1469, A: 1531. p(B wins)=1/(1+10^((1531-1469)/400)) = 1/(1+10^(62/400)) = 1/(1+10^0.155) = 1/(1+1.428) = 0.4115
    #   B_new = 1469+32*(1-0.4115) = 1469+32*0.5885 = 1469+18.83 = 1487.83 -> 1488
    #   A_new = 1531+32*(0-0.4115) = 1531-18.83 = 1512.17 -> 1512
    assert h1a_data["elo_rating"] == 1512, f"H1A actual ELO: {h1a_data['elo_rating']}"


    assert h1b_data["wins"] == 1, f"H1B actual wins: {h1b_data['wins']}"
    assert h1b_data["losses"] == 2, f"H1B actual losses: {h1b_data['losses']}"
    assert h1b_data["elo_rating"] == 1488, f"H1B actual ELO: {h1b_data['elo_rating']}"

    assert h1c_data["wins"] == 0, f"H1C actual wins: {h1c_data['wins']}"
    assert h1c_data["losses"] == 0, f"H1C actual losses: {h1c_data['losses']}"
    assert h1c_data["elo_rating"] == 1500, f"H1C actual ELO: {h1c_data['elo_rating']}"

    # Ranking order depends on Elo, then wins, then games played.
    # Expected order: H1A (1512), H1C (1500), H1B (1488)
    ranking_df_sorted_for_check = ranking_df.sort_values(by=["elo_rating", "wins", "games_played"], ascending=[False, False, True])

    assert ranking_df_sorted_for_check.iloc[0]["hrönir_uuid"] == H1A
    assert ranking_df_sorted_for_check.iloc[1]["hrönir_uuid"] == H1C
    assert ranking_df_sorted_for_check.iloc[2]["hrönir_uuid"] == H1B


def test_get_ranking_no_heirs_for_predecessor(temp_data_env): # Changed fixture
    # temp_data_env sets up isolated environment variables for DataManager.
    # The fixture ensures a clean temp directory for any side effects if DataManager writes something.
    dm = storage.DataManager()
    dm.clear_in_memory_data()

    # Add some paths to the system, but none that descend from NON_EXISTENT_PREDECESSOR
    # Path leading to H0_ROOT
    PATH_0_H0_ROOT = _uuid("fork_0_H0_ROOT_for_no_heirs_test")
    dm.add_path(storage.PathModel(path_uuid=PATH_0_H0_ROOT, position=0, prev_uuid=None, uuid=uuid.UUID(H0_ROOT)))
    # Path from H0_ROOT to H1A
    PATH_1_H0_ROOT_H1A = _uuid("fork_1_H0_ROOT_H1A_for_no_heirs_test")
    dm.add_path(storage.PathModel(path_uuid=PATH_1_H0_ROOT_H1A, position=1, prev_uuid=uuid.UUID(H0_ROOT), uuid=uuid.UUID(H1A)))

    dm.save_all_data_to_csvs() # Commit to DB

    NON_EXISTENT_PREDECESSOR = _uuid("non_existent_predecessor_for_ranking_test")

    ranking_df = get_ranking(
        position=1, # Check for heirs at position 1
        predecessor_hronir_uuid=NON_EXISTENT_PREDECESSOR
    )
    assert ranking_df.empty, \
        f"Ranking DF should be empty when querying for heirs of a non-existent predecessor. Got: \n{ranking_df}"


def test_get_ranking_no_votes_for_heirs(temp_data_env): # Changed fixture
    # temp_data_env sets up isolated environment variables for DataManager.
    dm = storage.DataManager()
    dm.clear_in_memory_data()

    # Define Path UUIDs
    PATH_H1A_NO_VOTES = _uuid("path_H1A_no_votes")
    PATH_H1B_NO_VOTES = _uuid("path_H1B_no_votes")

    # Add paths that are heirs of H0_ROOT
    paths_to_add = [
        storage.PathModel(path_uuid=PATH_H1A_NO_VOTES, position=1, prev_uuid=uuid.UUID(H0_ROOT), uuid=uuid.UUID(H1A)),
        storage.PathModel(path_uuid=PATH_H1B_NO_VOTES, position=1, prev_uuid=uuid.UUID(H0_ROOT), uuid=uuid.UUID(H1B)),
    ]
    for p_model in paths_to_add:
        dm.add_path(p_model)

    # No votes are added for these paths or duels involving them.
    # No duels need to be added as get_ranking processes votes, and there are no votes.

    dm.save_all_data_to_csvs() # Commit paths to DB

    ranking_df = get_ranking(
        position=1,
        predecessor_hronir_uuid=H0_ROOT
    )

    assert len(ranking_df) == 2, f"Expected 2 paths, got {len(ranking_df)}"

    # Sort by hrönir_uuid for consistent assertion order
    ranking_df_sorted = ranking_df.sort_values(by="hrönir_uuid").reset_index(drop=True)

    expected_heirs_sorted = sorted([H1A, H1B])
    retrieved_heirs_sorted = sorted(ranking_df_sorted["hrönir_uuid"].tolist())
    assert retrieved_heirs_sorted == expected_heirs_sorted, \
        f"Retrieved heirs {retrieved_heirs_sorted} do not match expected {expected_heirs_sorted}"

    for _, row in ranking_df_sorted.iterrows():
        assert row["elo_rating"] == 1500, f"Expected ELO 1500 for path {row['path_uuid']}, got {row['elo_rating']}"
        assert row["wins"] == 0, f"Expected 0 wins for path {row['path_uuid']}, got {row['wins']}"
        assert row["losses"] == 0, f"Expected 0 losses for path {row['path_uuid']}, got {row['losses']}"
        assert row["games_played"] == 0, f"Expected 0 games for path {row['path_uuid']}, got {row['games_played']}"


def test_get_ranking_for_position_0_no_predecessor(temp_data_env): # Changed fixture
    # temp_data_env sets up isolated environment variables for DataManager
    dm = storage.DataManager() # This DM will use paths from temp_data_env
    dm.clear_in_memory_data() # Clears the test-specific DB

    H0_ALT_HRONIR = _uuid("hrönir_0_ALT_pos0_for_test") # Content UUID for alternative H0

    # Path UUIDs for position 0
    PATH_H0_ROOT = _uuid("path_to_H0_ROOT_pos0_test")
    PATH_H0_ALT = _uuid("path_to_H0_ALT_pos0_test")

    paths_to_add = [
        storage.PathModel(path_uuid=PATH_H0_ROOT, position=0, prev_uuid=None, uuid=uuid.UUID(H0_ROOT)),
        storage.PathModel(path_uuid=PATH_H0_ALT, position=0, prev_uuid=None, uuid=uuid.UUID(H0_ALT_HRONIR)),
    ]
    for p_model in paths_to_add:
        dm.add_path(p_model)
    # print(f"DEBUG_TEST: Paths after adding 2 in test_get_ranking_for_position_0: {len(dm.get_all_paths())}") # Removed debug print

    # Duel and Vote data for position 0
    # Position 0 should not have duels or votes affecting its ranking for canonical selection,
    # but get_ranking might still be callable for pos 0 to see ratings if votes existed.
    # However, the core logic is that pos 0 is immutable via votes.
    # For this test, we want to see if get_ranking can process votes if they were hypothetically present for pos 0.

    DUEL_P0_ROOT_ALT = _uuid("duel_P0_ROOT_vs_ALT")
    # Add duel (inactive, as it's historical for vote processing)
    # Note: add_pending_duel will raise ValueError for position 0.
    # This means we cannot store duels for position 0 using the public API.
    # And ratings.get_ranking depends on get_duel_details.
    # This test's premise (votes at pos 0 influencing Elo) is against the new immutability rule for pos 0 duels.
    # get_ranking for pos 0 should just return paths with base Elo if no votes (which is the case as no duels can be made for pos 0).

    # If we strictly follow "no duels for pos 0", then no votes can be recorded for pos 0.
    # So, get_ranking(0, None) should return the two paths with base Elo.

    # Let's adjust the test to reflect this:
    # 1. Add two paths at position 0.
    # 2. Call get_ranking(0, None).
    # 3. Assert both paths are returned with base Elo and 0 wins/losses.

    dm.save_all_data_to_csvs() # Commit paths

    ranking_df = get_ranking(
        position=0,
        predecessor_hronir_uuid=None
    )

    assert len(ranking_df) == 2, f"Expected 2 paths at position 0, got {len(ranking_df)}"

    expected_pos0_hrönirs_sorted = sorted([H0_ROOT, H0_ALT_HRONIR])
    ranking_df_sorted = ranking_df.sort_values(by="hrönir_uuid").reset_index(drop=True)
    retrieved_pos0_hrönirs_sorted = sorted(ranking_df_sorted["hrönir_uuid"].tolist())

    assert retrieved_pos0_hrönirs_sorted == expected_pos0_hrönirs_sorted, \
        f"Retrieved hrönirs {retrieved_pos0_hrönirs_sorted} do not match expected {expected_pos0_hrönirs_sorted}"

    for _, row in ranking_df_sorted.iterrows():
        assert row["elo_rating"] == 1500
        assert row["wins"] == 0
        assert row["losses"] == 0
        assert row["games_played"] == 0

def test_get_ranking_empty_narrative_paths_dir(temp_data_env): # Changed fixture
    # Test that if no paths exist for the given position and predecessor, an empty DataFrame is returned.
    dm = storage.DataManager()
    dm.clear_in_memory_data()

    # No paths are added to the DataManager.
    # Votes or duels are irrelevant if there are no paths to rank.

    ranking_df = get_ranking(
        position=1, # Arbitrary position
        predecessor_hronir_uuid=H0_ROOT # Arbitrary predecessor
    )
    assert ranking_df.empty, \
        f"Expected empty DataFrame when no paths exist, got: \n{ranking_df}"


def test_get_ranking_empty_ratings_files(temp_data_env): # Changed fixture
    dm = storage.DataManager()
    dm.clear_in_memory_data()

    # Add some paths that would normally be ranked
    PATH_0_H0_ROOT = _uuid("fork_0_H0_ROOT_empty_ratings")
    PATH_1_H0_ROOT_H1A = _uuid("fork_1_H0_ROOT_H1A_empty_ratings")
    PATH_1_H0_ROOT_H1B = _uuid("fork_1_H0_ROOT_H1B_empty_ratings")

    paths_to_add = [
        storage.PathModel(path_uuid=PATH_0_H0_ROOT, position=0, prev_uuid=None, uuid=uuid.UUID(H0_ROOT)),
        storage.PathModel(path_uuid=PATH_1_H0_ROOT_H1A, position=1, prev_uuid=uuid.UUID(H0_ROOT), uuid=uuid.UUID(H1A)),
        storage.PathModel(path_uuid=PATH_1_H0_ROOT_H1B, position=1, prev_uuid=uuid.UUID(H0_ROOT), uuid=uuid.UUID(H1B)),
    ]
    for p_model in paths_to_add:
        dm.add_path(p_model)

    # No votes are added. No duels need to be added as there are no votes to link them to.
    dm.save_all_data_to_csvs() # Commit paths

    ranking_df = get_ranking(
        position=1,
        predecessor_hronir_uuid=H0_ROOT
    )

    # Expecting paths H1A and H1B to be returned, with base Elo and no game history.
    assert len(ranking_df) == 2, f"Expected 2 paths, got {len(ranking_df)}"

    expected_heirs_sorted = sorted([H1A, H1B])
    ranking_df_sorted = ranking_df.sort_values(by="hrönir_uuid").reset_index(drop=True)
    retrieved_heirs_sorted = sorted(ranking_df_sorted["hrönir_uuid"].tolist())
    assert retrieved_heirs_sorted == expected_heirs_sorted

    for _, row in ranking_df_sorted.iterrows():
        assert row["elo_rating"] == 1500
        assert row["wins"] == 0
        assert row["losses"] == 0
        assert row["games_played"] == 0

    # Test with zero-byte votes file is implicitly covered by DuckDB backend not loading from CSVs
    # unless DB is empty and CSVs are present for initial import.
    # In this test, DB is cleared, then paths are added programmatically. Votes table will be empty.


@pytest.mark.skip(reason="CSV loading tests are obsolete with DuckDB backend.")
def test_get_ranking_malformed_forking_csv(temp_data_dir):
    forking_dir, ratings_dir = temp_data_dir

    create_csv(
        [{"position": 1, "prev_uuid": H0_ROOT, "uuid": H1A, "fork_uuid": _uuid("f1")}],
        forking_dir / "good_forks.csv",
    )
    (forking_dir / "bad_forks.csv").write_text(
        "position,prev_uuid\ninvalid,row,with,too,many,columns"
    )

    create_csv([], ratings_dir / "position_001.csv")

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert len(ranking_df) == 1
    assert ranking_df.iloc[0]["hrönir_uuid"] == H1A
    assert ranking_df.iloc[0]["elo_rating"] == 1500


@pytest.mark.skip(reason="CSV loading tests are obsolete with DuckDB backend.")
def test_get_ranking_ratings_path_missing_columns(temp_data_env): # Corrected fixture name
    # This test is skipped, but its signature was causing a setup error.
    # The body still uses create_csv and _call_get_ranking_with_setup which are obsolete.
    # If unskipped, it would need full refactoring.
    forking_dir, ratings_dir = temp_data_env["narrative_paths_dir"], temp_data_env["ratings_dir"]
    create_csv(
        [{"position": 1, "prev_uuid": H0_ROOT, "uuid": H1A, "fork_uuid": _uuid("f1")}],
        forking_dir / "forks.csv",
    )
    (ratings_dir / "position_001.csv").write_text("winner,loser\ninvalid,row")

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert len(ranking_df) == 1
    assert ranking_df.iloc[0]["hrönir_uuid"] == H1A
    assert ranking_df.iloc[0]["elo_rating"] == 1500
    assert ranking_df.iloc[0]["wins"] == 0
    assert ranking_df.iloc[0]["losses"] == 0


def test_get_ranking_canonical_predecessor_none_not_pos_0(temp_data_env): # Changed fixture & logic
    # This test checks that if predecessor_hronir_uuid is None for a position > 0,
    # get_ranking returns an empty DataFrame because paths at pos > 0 must have a predecessor in a lineage.
    dm = storage.DataManager()
    dm.clear_in_memory_data()

    # Add some paths at position 1, they all have H0_ROOT as predecessor
    PATH_H1A_FILTER_TEST = _uuid("path_H1A_filter_test_canon_none")
    PATH_H1B_FILTER_TEST = _uuid("path_H1B_filter_test_canon_none")

    paths_to_add = [
        storage.PathModel(path_uuid=PATH_H1A_FILTER_TEST, position=1, prev_uuid=uuid.UUID(H0_ROOT), uuid=uuid.UUID(H1A)),
        storage.PathModel(path_uuid=PATH_H1B_FILTER_TEST, position=1, prev_uuid=uuid.UUID(H0_ROOT), uuid=uuid.UUID(H1B)),
    ]
    for p_model in paths_to_add:
        dm.add_path(p_model)
    dm.save_all_data_to_csvs()

    ranking_df = get_ranking(
        position=1, # A position > 0
        predecessor_hronir_uuid=None # But no predecessor specified
    )
    assert ranking_df.empty, \
        f"Expected empty DataFrame for pos > 0 with no predecessor. Got: \n{ranking_df}"


@pytest.mark.skip(reason="CSV loading tests are obsolete with DuckDB backend.")
def test_get_ranking_narrative_paths_missing_columns(temp_data_dir):
    forking_dir, ratings_dir = temp_data_dir
    (forking_dir / "missing_cols.csv").write_text("uuid,fork_uuid\nval1,val2")
    create_csv(ratings_pos1_data, ratings_dir / "position_001.csv")

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert ranking_df.empty


def test_get_ranking_ratings_path_missing_columns(temp_data_dir):
    forking_dir, ratings_dir = temp_data_dir
    create_csv(
        [{"position": 1, "prev_uuid": H0_ROOT, "uuid": H1A, "fork_uuid": _uuid("f1")}],
        forking_dir / "forks.csv",
    )
    (ratings_dir / "position_001.csv").write_text("voter_id,winning_id,losing_id\nv1,w1,l1")

    ranking_df = _call_get_ranking_with_setup(
        position=1,
        predecessor_hronir_uuid=H0_ROOT,
        forking_dir=forking_dir,
        ratings_dir=ratings_dir,
    )
    assert len(ranking_df) == 1
    assert ranking_df.iloc[0]["hrönir_uuid"] == H1A
    assert ranking_df.iloc[0]["elo_rating"] == 1500
