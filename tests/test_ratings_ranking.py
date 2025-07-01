from pathlib import Path

import pandas as pd

from hronir_encyclopedia import (
    ratings,
    storage,
)
import uuid # Import uuid module
import datetime # For creating duel timestamps

# Generate valid UUIDs for testing
# Hrönir content UUIDs (typically UUIDv5 derived from content)
PREDECESSOR_POS1 = str(uuid.uuid5(storage.UUID_NAMESPACE, "test_hrönir_predecessor_pos1"))
UUID_A = str(uuid.uuid5(storage.UUID_NAMESPACE, "test_hrönir_A"))
UUID_B = str(uuid.uuid5(storage.UUID_NAMESPACE, "test_hrönir_B"))
UUID_C = str(uuid.uuid5(storage.UUID_NAMESPACE, "test_hrönir_C"))

# Path UUIDs (UUIDv5 derived from position, predecessor hrönir uuid, current hrönir uuid)
PATH_UUID_A = str(storage.compute_narrative_path_uuid(1, PREDECESSOR_POS1, UUID_A))
PATH_UUID_B = str(storage.compute_narrative_path_uuid(1, PREDECESSOR_POS1, UUID_B))
PATH_UUID_C = str(storage.compute_narrative_path_uuid(1, PREDECESSOR_POS1, UUID_C))

VOTE_ID_1 = str(uuid.uuid4())
VOTE_ID_2 = str(uuid.uuid4())
VOTE_ID_3 = str(uuid.uuid4())

# Mock duel IDs - in a real scenario these would come from pending_duels table
DUEL_ID_AB = str(uuid.uuid4()) # Duel between A and B
DUEL_ID_AC = str(uuid.uuid4()) # Duel between A and C
DUEL_ID_BA = str(uuid.uuid4()) # Duel between B and A (can be same as AB if side matters)

# Mock voting token path UUIDs (these are path_uuids, so should be UUIDv5)
# For simplicity, let's assume these tokens correspond to some hypothetical paths.
# Their actual position/predecessor/hrönir don't matter for this specific test's ranking calculation,
# only that they are valid UUIDv5 if the Vote model expects that for voting_token_path_uuid.
VOTING_TOKEN_1 = str(uuid.uuid5(storage.UUID_NAMESPACE, "test_voting_token_path_1"))
VOTING_TOKEN_2 = str(uuid.uuid5(storage.UUID_NAMESPACE, "test_voting_token_path_2"))
VOTING_TOKEN_3 = str(uuid.uuid5(storage.UUID_NAMESPACE, "test_voting_token_path_3"))


def test_get_ranking(tmp_path: Path):
    ratings_dir_test_var = tmp_path / "ratings" # This is not used by DuckDB backend directly for votes
    ratings_dir_test_var.mkdir(exist_ok=True)
    # This test will now directly use DataManager to set up DB state.
    # Csv loading helpers are no longer used for this test.
    # The tmp_path fixture is still useful for isolating any files created by the DataManager,
    # although with DuckDB in-memory or specific file, it's less critical for CSVs.

    dm = storage.DataManager()
    dm.clear_in_memory_data() # Ensure a clean slate for each test run

    # 1. Add Paths to DataManager
    path_models = [
        storage.PathModel(path_uuid=PATH_UUID_A, position=1, prev_uuid=uuid.UUID(PREDECESSOR_POS1), uuid=uuid.UUID(UUID_A)),
        storage.PathModel(path_uuid=PATH_UUID_B, position=1, prev_uuid=uuid.UUID(PREDECESSOR_POS1), uuid=uuid.UUID(UUID_B)),
        storage.PathModel(path_uuid=PATH_UUID_C, position=1, prev_uuid=uuid.UUID(PREDECESSOR_POS1), uuid=uuid.UUID(UUID_C)),
    ]
    for p_model in path_models:
        dm.add_path(p_model)

    # 2. Add corresponding Duels to DataManager (so get_ranking can find duel details)
    # These duels are marked is_active=False as they represent past, completed duels whose votes are being processed.
    # The duel_id in the Vote record will be used to fetch these.
    # Note: DataManager.add_pending_duel sets is_active=True by default.
    # We need a way to add these as historical/inactive if that's how get_ranking expects them,
    # or ensure get_ranking can fetch details of inactive duels too.
    # The DuckDBDataManager.add_pending_duel_direct was a workaround.
    # Let's use the public add_pending_duel and then deactivate them if necessary.

    # Duel 1: Path A vs Path B
    dm.add_pending_duel(position=1, path_A_uuid=PATH_UUID_A, path_B_uuid=PATH_UUID_B, created_at=datetime.datetime.now(datetime.timezone.utc), duel_id_override=DUEL_ID_AB)
    dm.deactivate_duel(DUEL_ID_AB) # Mark as inactive as it's a past duel for ranking

    # Duel 2: Path A vs Path C
    dm.add_pending_duel(position=1, path_A_uuid=PATH_UUID_A, path_B_uuid=PATH_UUID_C, created_at=datetime.datetime.now(datetime.timezone.utc), duel_id_override=DUEL_ID_AC)
    dm.deactivate_duel(DUEL_ID_AC)

    # Duel 3: Path B vs Path A (B is winner, A is loser, so B was effectively 'path_A_uuid' in this duel context if chosen_winner_side='A')
    dm.add_pending_duel(position=1, path_A_uuid=PATH_UUID_B, path_B_uuid=PATH_UUID_A, created_at=datetime.datetime.now(datetime.timezone.utc), duel_id_override=DUEL_ID_BA)
    dm.deactivate_duel(DUEL_ID_BA)

    # 3. Add Votes to DataManager
    vote_models = [
        storage.Vote(vote_id=VOTE_ID_1, duel_id=uuid.UUID(DUEL_ID_AB), voting_token_path_uuid=uuid.UUID(VOTING_TOKEN_1), chosen_winner_side='A', position=1), # A (winner) vs B (loser)
        storage.Vote(vote_id=VOTE_ID_2, duel_id=uuid.UUID(DUEL_ID_AC), voting_token_path_uuid=uuid.UUID(VOTING_TOKEN_2), chosen_winner_side='A', position=1), # A (winner) vs C (loser)
        storage.Vote(vote_id=VOTE_ID_3, duel_id=uuid.UUID(DUEL_ID_BA), voting_token_path_uuid=uuid.UUID(VOTING_TOKEN_3), chosen_winner_side='A', position=1), # B (winner, was path_A_uuid in this duel) vs A (loser, was path_B_uuid)
    ]
    for v_model in vote_models:
        dm.add_vote(v_model)

    dm.save_all_data_to_csvs() # Commits changes to DuckDB

    # 4. Call ratings.get_ranking directly
    df = ratings.get_ranking(
        position=1,
        predecessor_hronir_uuid=PREDECESSOR_POS1,
    )

    # 5. Assertions
    # Sort by hrönir_uuid for consistent comparison before checking content
    df_sorted = df.sort_values(by="hrönir_uuid").reset_index(drop=True)
    expected_hrönirs_sorted = sorted([UUID_A, UUID_B, UUID_C])

    assert list(df_sorted["hrönir_uuid"]) == expected_hrönirs_sorted, \
        f"Expected hrönirs {expected_hrönirs_sorted}, got {list(df_sorted['hrönir_uuid'])}"

    row_a = df_sorted[df_sorted["hrönir_uuid"] == UUID_A].iloc[0]
    row_b = df[df["hrönir_uuid"] == UUID_B].iloc[0]
    row_c = df[df["hrönir_uuid"] == UUID_C].iloc[0]

    assert row_a["wins"] == 2 and row_a["losses"] == 1
    assert row_a["elo_rating"] == 1513

    assert row_b["wins"] == 1 and row_b["losses"] == 1
    assert row_b["elo_rating"] == 1502

    assert row_c["wins"] == 0 and row_c["losses"] == 1
    assert row_c["elo_rating"] == 1485
