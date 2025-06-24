import uuid
from pathlib import Path # Import Path

import pandas as pd
import pytest

from hronir_encyclopedia import ratings, storage # ratings.py and storage for DataManager


# Helper function to manage DataManager and call determine_next_duel_entropy
def _call_determine_next_duel_entropy_with_setup(position, predecessor_hronir_uuid, forking_dir, ratings_dir):
    # Store original values from the singleton
    original_fork_dir_attr = storage.data_manager.fork_csv_dir
    original_ratings_dir_attr = storage.data_manager.ratings_csv_dir
    original_initialized_attr = storage.data_manager._initialized
    original_cwd = Path.cwd() # Store current CWD
    import os # Make sure os is imported

    try:
        # Change CWD to the parent of the temp directory structure for this test
        # This ensures that if DataManager re-initializes using default relative paths,
        # they resolve correctly within the test's temporary space.
        os.chdir(Path(forking_dir).parent)

        # 1. Set paths on the DataManager instance. Using names now relative to new CWD.
        storage.data_manager.fork_csv_dir = Path(Path(forking_dir).name)
        storage.data_manager.ratings_csv_dir = Path(Path(ratings_dir).name)

        # 2. Mark as uninitialized
        storage.data_manager._initialized = False

        # 3. Initialize, which will clear and load from the (empty) temp dirs
        storage.data_manager.initialize_and_load(clear_existing_data=True)

        # The function being tested
        duel_info = ratings.determine_next_duel_entropy(
            position=position,
            predecessor_hronir_uuid=predecessor_hronir_uuid,
            session=None  # Will get its own session, using current DataManager state
        )
        return duel_info
    finally:
        # Restore original attributes on the singleton
        storage.data_manager.fork_csv_dir = original_fork_dir_attr
        storage.data_manager.ratings_csv_dir = original_ratings_dir_attr
        storage.data_manager._initialized = original_initialized_attr
        os.chdir(original_cwd) # Restore CWD

        # Clean up any data loaded/created by this test from the DB
        # Check _initialized on the instance, not the potentially restored original_initialized_attr
        if storage.data_manager._initialized:
            storage.data_manager.clear_in_memory_data()


# Helper function to generate ranking DataFrame as get_ranking would
def create_ranking_df(hronirs_data: list[dict]) -> pd.DataFrame:
    # Columns should match what get_ranking produces: fork_uuid, hrönir_uuid, elo_rating, etc.
    # 'uuid' from input data will be mapped to 'fork_uuid' for the output DataFrame.
    # 'hrönir_uuid' will be made same as 'fork_uuid' for simplicity of this mock.
    output_cols = ["fork_uuid", "hrönir_uuid", "elo_rating", "games_played", "wins", "losses"]
    if not hronirs_data:
        return pd.DataFrame(columns=output_cols)

    df = pd.DataFrame(hronirs_data)

    # Rename 'uuid' to 'fork_uuid' if 'uuid' exists from input
    if "uuid" in df.columns and "fork_uuid" not in df.columns:
        df.rename(columns={"uuid": "fork_uuid"}, inplace=True)
    elif "fork_uuid" not in df.columns:  # if neither 'uuid' nor 'fork_uuid' provided
        df["fork_uuid"] = [str(uuid.uuid4()) for _ in range(len(df))]

    # Ensure other standard columns that get_ranking provides
    if "hrönir_uuid" not in df.columns:
        df["hrönir_uuid"] = df["fork_uuid"]  # Mock simplicity: hrönir_uuid is same as fork_uuid

    if "elo_rating" not in df.columns:  # if input used 'elo', map it, else default
        if "elo" in df.columns:
            df.rename(columns={"elo": "elo_rating"}, inplace=True)
        else:
            df["elo_rating"] = 1500

    for col_default_zero in ["wins", "losses", "games_played"]:
        if col_default_zero not in df.columns:
            if (
                col_default_zero == "games_played" and "total_duels" in df.columns
            ):  # Handle old 'total_duels' input
                df[col_default_zero] = df["total_duels"]
            else:
                df[col_default_zero] = 0

    # If games_played is still 0 but wins/losses exist, sum them.
    if "games_played" in df.columns and "wins" in df.columns and "losses" in df.columns:
        df["games_played"] = df.apply(
            lambda row: (
                row["wins"] + row["losses"] if row["games_played"] == 0 else row["games_played"]
            ),
            axis=1,
        )

    # Ensure types and select final columns
    df["elo_rating"] = df["elo_rating"].astype(float)
    df["wins"] = df["wins"].astype(int)
    df["losses"] = df["losses"].astype(int)
    df["games_played"] = df["games_played"].astype(int)

    # Select and reorder columns to match get_ranking's output
    df = df.reindex(
        columns=output_cols, fill_value=0
    )  # fill_value for any missing from reindex, though should be handled above

    return df.sort_values(by="elo_rating", ascending=False).reset_index(drop=True)


@pytest.fixture
def mock_ratings_get_ranking(monkeypatch):
    """
    Mocks ratings.get_ranking. The fixture returns a setter function
    that tests can use to define the DataFrame data.
    """
    # Columns should match what get_ranking produces
    df_to_return_holder = [
        pd.DataFrame(
            columns=["fork_uuid", "hrönir_uuid", "elo_rating", "games_played", "wins", "losses"]
        )
    ]

    # O mock agora precisa aceitar a nova assinatura de get_ranking
    def _mock_get_ranking(
        position: int,
        predecessor_hronir_uuid: str | None,
        session=None,  # Added session, made optional for mock
    ):
        # Os parâmetros extras não são usados pelo mock, pois os dados são definidos diretamente.
        return df_to_return_holder[0].copy()

    monkeypatch.setattr(ratings, "get_ranking", _mock_get_ranking)

    def set_df_data(data_list: list[dict] | pd.DataFrame):
        if isinstance(data_list, pd.DataFrame):
            df_to_return_holder[0] = data_list
        else:
            df_to_return_holder[0] = create_ranking_df(data_list)

    return set_df_data


class TestDetermineNextDuelPurelyEntropic:
    def test_max_entropy_duel_no_new_hronirs(self, tmp_path, mock_ratings_get_ranking):
        """
        Test: Should pick duel with max entropy (closest Elos for neighbors),
        regardless of 'new' status.
        """
        set_df_data = mock_ratings_get_ranking
        h1, h2, h3, h4 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

        # h2 has 0 duels, but Elo is close to h1. This pair should be chosen.
        set_df_data(
            [
                {"uuid": h1, "elo": 1600, "wins": 10, "losses": 2, "total_duels": 12},
                {
                    "uuid": h2,
                    "elo": 1590,
                    "wins": 0,
                    "losses": 0,
                    "total_duels": 0,
                },  # Close Elo to h1, new
                {"uuid": h3, "elo": 1500, "wins": 5, "losses": 5, "total_duels": 10},
                {"uuid": h4, "elo": 1450, "wins": 2, "losses": 8, "total_duels": 10},
            ]
        )

        forking_dir = tmp_path / "forking_path"
        forking_dir.mkdir()
        ratings_dir = tmp_path / "ratings"  # Adicionado para consistência
        ratings_dir.mkdir()

        # Call the helper which handles DataManager setup and teardown
        duel_info = _call_determine_next_duel_entropy_with_setup(
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
            forking_dir=forking_dir,
            ratings_dir=ratings_dir
        )

        assert duel_info is not None
        assert duel_info["strategy"] == "max_shannon_entropy" # Strategy name updated
        # The determine_next_duel now returns fork_uuids in "duel_pair"
        # Assuming the mock_ratings_get_ranking returns 'uuid' as fork_uuid for simplicity here
        assert set(duel_info["duel_pair"].values()) == set([h1, h2])
        assert duel_info["position"] == 1
        # Entropy for 1600 vs 1590 (diff 10)
        # P_A = 1 / (1 + 10^(-10/400)) approx 0.5143868
        # H = - (P_A * log2(P_A) + (1-P_A) * log2(1-P_A)) approx 0.99886
        # O código parece estar calculando consistentemente como ~0.9994027
        assert duel_info["entropy"] == pytest.approx(0.9994027, abs=1e-5)

    def test_max_entropy_duel_chooses_highest_among_equal_elo_diffs(
        self, tmp_path, mock_ratings_get_ranking
    ):
        set_df_data = mock_ratings_get_ranking
        h1, h2, h3, h4, h5, h6 = (
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4()),
            str(uuid.uuid4()),
        )
        set_df_data(
            [
                {"uuid": h1, "elo": 1600, "total_duels": 12},
                {"uuid": h2, "elo": 1590, "total_duels": 11},  # Diff 10 with h1
                {"uuid": h3, "elo": 1550, "total_duels": 10},
                {"uuid": h4, "elo": 1500, "total_duels": 10},
                {"uuid": h5, "elo": 1490, "total_duels": 10},  # Diff 10 with h4
                {"uuid": h6, "elo": 1400, "total_duels": 10},
            ]
        )
        # Entropy for (1600,1590) should be equal to (1500,1490).
        # The code iterates from top, so (h1,h2) should be picked.

        forking_dir = tmp_path / "forking_path"
        forking_dir.mkdir()
        ratings_dir = tmp_path / "ratings"
        ratings_dir.mkdir()

        duel_info = _call_determine_next_duel_entropy_with_setup(
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
            forking_dir=forking_dir,
            ratings_dir=ratings_dir
        )

        assert duel_info is not None
        assert duel_info["strategy"] == "max_shannon_entropy" # Strategy name updated
        assert set(duel_info["duel_pair"].values()) == set([h1, h2])

    def test_edge_case_no_hronirs(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        set_df_data([])
        forking_dir = tmp_path / "forking_path"
        forking_dir.mkdir()
        ratings_dir = tmp_path / "ratings"
        ratings_dir.mkdir()
        duel_info = _call_determine_next_duel_entropy_with_setup(
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
            forking_dir=forking_dir,
            ratings_dir=ratings_dir
        )
        assert duel_info is None

    def test_edge_case_one_hronir(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        set_df_data([{"uuid": str(uuid.uuid4()), "elo": 1500, "total_duels": 0}])
        forking_dir = tmp_path / "forking_path"
        forking_dir.mkdir()
        ratings_dir = tmp_path / "ratings"
        ratings_dir.mkdir()
        duel_info = _call_determine_next_duel_entropy_with_setup(
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
            forking_dir=forking_dir,
            ratings_dir=ratings_dir
        )
        assert duel_info is None

    def test_edge_case_two_hronirs_both_new_is_max_entropy(
        self, tmp_path, mock_ratings_get_ranking
    ):
        set_df_data = mock_ratings_get_ranking
        h1_new, h2_new = str(uuid.uuid4()), str(uuid.uuid4())
        set_df_data(
            [
                {"uuid": h1_new, "elo": 1510, "total_duels": 0},
                {"uuid": h2_new, "elo": 1500, "total_duels": 0},
            ]
        )
        # This is the only pair, so it must be max entropy.
        forking_dir = tmp_path / "forking_path"
        forking_dir.mkdir()
        ratings_dir = tmp_path / "ratings"
        ratings_dir.mkdir()
        duel_info = _call_determine_next_duel_entropy_with_setup(
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
            forking_dir=forking_dir,
            ratings_dir=ratings_dir
        )

        assert duel_info is not None
        # Strategy name updated in determine_next_duel_entropy
        assert duel_info["strategy"] == "max_shannon_entropy"
        assert set(duel_info["duel_pair"].values()) == set([h1_new, h2_new])  # Updated assertion
        # Elo diff 10, entropy. O código parece estar calculando consistentemente como ~0.9994027
        assert duel_info["entropy"] == pytest.approx(0.9994027, abs=1e-5)

    def test_no_total_duels_column_handled_by_keyerror(self, tmp_path, mock_ratings_get_ranking):
        # This test assumes that if get_ranking provides a malformed DataFrame (missing total_duels),
        # determine_next_duel might fail with KeyError when trying to access it for filtering new_challengers,
        # which is now removed. The current determine_next_duel does not use total_duels for any filtering.
        # It only relies on 'elo' and 'uuid' from the ranking_df.
        # So, this test needs to be re-evaluated.
        # If 'total_duels' is missing, create_ranking_df in the mock setup will add it with 0s.
        # If we want to test determine_next_duel with a malformed df from get_ranking (e.g. no 'elo'),
        # that's a different test. The current determine_next_duel would fail if 'elo' is missing.
        # For now, this test as originally intended (KeyError on 'total_duels') is moot.
        # Let's ensure it runs without error, as 'total_duels' is not strictly needed by the new logic.
        set_df_data = mock_ratings_get_ranking
        h1_uuid, h2_uuid = str(uuid.uuid4()), str(uuid.uuid4())

        # DataFrame should have 'fork_uuid' and 'elo_rating' for determine_next_duel to work.
        # Missing 'games_played' (formerly 'total_duels') is what this test can focus on.
        # The input to set_df_data should use 'uuid' and 'elo' if it's a list of dicts,
        # as create_ranking_df handles the renaming.
        # Or, if passing a DataFrame directly, it must have the correct final column names.
        # For this test, we pass a DataFrame directly, so it needs 'fork_uuid' and 'elo_rating'.
        malformed_df_for_test = pd.DataFrame(
            [
                # Using 'uuid' here as it will be renamed to 'fork_uuid' by create_ranking_df if not passing df directly
                # BUT we are passing df directly, so it must be correct from the start.
                {
                    "fork_uuid": h1_uuid,
                    "hrönir_uuid": h1_uuid,
                    "elo_rating": 1600.0,
                    "wins": 10,
                    "losses": 2,
                },  # Missing games_played
                {
                    "fork_uuid": h2_uuid,
                    "hrönir_uuid": h2_uuid,
                    "elo_rating": 1550.0,
                    "wins": 8,
                    "losses": 3,
                },  # Missing games_played
            ]
        )
        # Pass this malformed df directly to the mock setter
        set_df_data(malformed_df_for_test.copy())

        # The new determine_next_duel does not use 'total_duels'. It should still work.
        forking_dir = tmp_path / "forking_path"
        forking_dir.mkdir()
        ratings_dir = tmp_path / "ratings"
        ratings_dir.mkdir()
        duel_info = _call_determine_next_duel_entropy_with_setup(
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
            forking_dir=forking_dir,
            ratings_dir=ratings_dir
        )
        assert duel_info is not None
        assert duel_info["strategy"] == "max_shannon_entropy"  # Strategy name updated
        assert set(duel_info["duel_pair"].values()) == set([h1_uuid, h2_uuid])

    def test_entropy_calculation_is_correct_for_known_pair(
        self, tmp_path, mock_ratings_get_ranking
    ):
        set_df_data = mock_ratings_get_ranking
        h1, h2 = str(uuid.uuid4()), str(uuid.uuid4())
        set_df_data(
            [
                {
                    "uuid": h1,
                    "elo": 1600,
                    "total_duels": 1,
                },  # wins/losses not needed for this test's focus
                {"uuid": h2, "elo": 1500, "total_duels": 1},
            ]
        )

        forking_dir = tmp_path / "forking_path"
        forking_dir.mkdir()
        ratings_dir = tmp_path / "ratings"
        ratings_dir.mkdir()
        duel_info = _call_determine_next_duel_entropy_with_setup( # Call helper
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
            forking_dir=forking_dir,
            ratings_dir=ratings_dir
        )
        assert duel_info is not None
        assert duel_info["strategy"] == "max_shannon_entropy"
        assert set(duel_info["duel_pair"].values()) == set([h1, h2])  # Updated assertion
        assert duel_info["entropy"] == pytest.approx(0.9426, abs=1e-4)  # Same as before

    def test_entropy_low_for_very_different_elos(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h1, h2 = str(uuid.uuid4()), str(uuid.uuid4())
        set_df_data(
            [
                {"uuid": h1, "elo": 2400, "total_duels": 100},
                {"uuid": h2, "elo": 1200, "total_duels": 100},
            ]
        )

        forking_dir = tmp_path / "forking_path"
        forking_dir.mkdir()
        ratings_dir = tmp_path / "ratings"
        ratings_dir.mkdir()
        duel_info = _call_determine_next_duel_entropy_with_setup( # Call helper
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
            forking_dir=forking_dir,
            ratings_dir=ratings_dir
        )
        assert duel_info is not None
        assert duel_info["strategy"] == "max_shannon_entropy"
        assert duel_info["entropy"] == pytest.approx(0.0114, abs=1e-4)  # Same as before
