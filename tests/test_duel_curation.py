import uuid

import pandas as pd
import pytest

from hronir_encyclopedia import ratings, storage  # ratings.py and storage for DataManager


# Helper function to call determine_next_duel_entropy with a clean DataManager state
def _call_determine_next_duel_entropy_with_setup(position, predecessor_hronir_uuid):
    """
    Calls ratings.determine_next_duel_entropy.
    It assumes DataManager is already configured by conftest.py to use a test DuckDB.
    This helper ensures data is cleared before the call.
    """
    try:
        # Ensure DataManager is initialized and its DB is clean for the test
        # conftest.py should ensure storage.data_manager is a fresh instance pointing to a test DB
        if not storage.data_manager._initialized:
            storage.data_manager.initialize_and_load(clear_existing_data=True)
        else:
            storage.data_manager.clear_in_memory_data()  # Clears tables in the test DB

        # The function being tested
        duel_info = ratings.determine_next_duel_entropy(
            position=position,
            predecessor_hronir_uuid=predecessor_hronir_uuid,
        )
        return duel_info
    finally:
        # Clean up data from the test DB after the test
        if storage.data_manager._initialized:
            storage.data_manager.clear_in_memory_data()


# Helper function to generate ranking DataFrame as get_ranking would
def create_ranking_df(hronirs_data: list[dict]) -> pd.DataFrame:
    # Columns should match what get_ranking produces: path_uuid, hrönir_uuid, elo_rating, etc.
    # 'uuid' from input data will be mapped to 'path_uuid' for the output DataFrame.
    # 'hrönir_uuid' will be made same as 'path_uuid' for simplicity of this mock.
    output_cols = ["path_uuid", "hrönir_uuid", "elo_rating", "games_played", "wins", "losses"]
    if not hronirs_data:
        return pd.DataFrame(columns=output_cols)

    df = pd.DataFrame(hronirs_data)

    # Rename 'uuid' to 'path_uuid' if 'uuid' exists from input
    if "uuid" in df.columns and "path_uuid" not in df.columns:
        df.rename(columns={"uuid": "path_uuid"}, inplace=True)
    elif "path_uuid" not in df.columns:  # if neither 'uuid' nor 'path_uuid' provided
        df["path_uuid"] = [str(uuid.uuid4()) for _ in range(len(df))]

    # Ensure other standard columns that get_ranking provides
    if "hrönir_uuid" not in df.columns:
        df["hrönir_uuid"] = df["path_uuid"]  # Mock simplicity: hrönir_uuid is same as path_uuid

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
            columns=["path_uuid", "hrönir_uuid", "elo_rating", "games_played", "wins", "losses"]
        )
    ]

    # O mock agora precisa aceitar a nova assinatura de get_ranking
    def _mock_get_ranking(
        position: int,
        predecessor_hronir_uuid: str | None,
        # session=None,  # Argument removed
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

        # Call the helper, no need for forking_dir or ratings_dir setup
        duel_info = _call_determine_next_duel_entropy_with_setup(
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
        )

        assert duel_info is not None
        assert duel_info["strategy"] == "max_shannon_entropy"
        assert set(duel_info["duel_pair"].values()) == set([h1, h2])
        assert duel_info["position"] == 1
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
                {"uuid": h2, "elo": 1590, "total_duels": 11},
                {"uuid": h3, "elo": 1550, "total_duels": 10},
                {"uuid": h4, "elo": 1500, "total_duels": 10},
                {"uuid": h5, "elo": 1490, "total_duels": 10},
                {"uuid": h6, "elo": 1400, "total_duels": 10},
            ]
        )

        duel_info = _call_determine_next_duel_entropy_with_setup(
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
        )

        assert duel_info is not None
        assert duel_info["strategy"] == "max_shannon_entropy"
        assert set(duel_info["duel_pair"].values()) == set([h1, h2])

    def test_edge_case_no_hronirs(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        set_df_data([])
        duel_info = _call_determine_next_duel_entropy_with_setup(
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
        )
        assert duel_info is None

    def test_edge_case_one_hronir(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        set_df_data([{"uuid": str(uuid.uuid4()), "elo": 1500, "total_duels": 0}])
        duel_info = _call_determine_next_duel_entropy_with_setup(
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
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
        duel_info = _call_determine_next_duel_entropy_with_setup(
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
        )

        assert duel_info is not None
        assert duel_info["strategy"] == "max_shannon_entropy"
        assert set(duel_info["duel_pair"].values()) == set([h1_new, h2_new])
        assert duel_info["entropy"] == pytest.approx(0.9994027, abs=1e-5)

    def test_no_total_duels_column_handled_by_keyerror(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h1_uuid, h2_uuid = str(uuid.uuid4()), str(uuid.uuid4())

        malformed_df_for_test = pd.DataFrame(
            [
                {
                    "path_uuid": h1_uuid,  # Changed from fork_uuid
                    "hrönir_uuid": h1_uuid,
                    "elo_rating": 1600.0,
                    "wins": 10,
                    "losses": 2,
                },
                {
                    "path_uuid": h2_uuid,  # Changed from fork_uuid
                    "hrönir_uuid": h2_uuid,
                    "elo_rating": 1550.0,
                    "wins": 8,
                    "losses": 3,
                },
            ]
        )
        set_df_data(malformed_df_for_test.copy())

        duel_info = _call_determine_next_duel_entropy_with_setup(
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
        )
        assert duel_info is not None
        assert duel_info["strategy"] == "max_shannon_entropy"
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
                },
                {"uuid": h2, "elo": 1500, "total_duels": 1},
            ]
        )

        duel_info = _call_determine_next_duel_entropy_with_setup(
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
        )
        assert duel_info is not None
        assert duel_info["strategy"] == "max_shannon_entropy"
        assert set(duel_info["duel_pair"].values()) == set([h1, h2])
        assert duel_info["entropy"] == pytest.approx(0.9426, abs=1e-4)

    def test_entropy_low_for_very_different_elos(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h1, h2 = str(uuid.uuid4()), str(uuid.uuid4())
        set_df_data(
            [
                {"uuid": h1, "elo": 2400, "total_duels": 100},
                {"uuid": h2, "elo": 1200, "total_duels": 100},
            ]
        )

        duel_info = _call_determine_next_duel_entropy_with_setup(
            position=1,
            predecessor_hronir_uuid="any-pred-uuid",
        )
        assert duel_info is not None
        assert duel_info["strategy"] == "max_shannon_entropy"
        assert duel_info["entropy"] == pytest.approx(0.0114, abs=1e-4)
