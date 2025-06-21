import pytest
import pandas as pd
from pathlib import Path
import shutil
import uuid

from hronir_encyclopedia import ratings # ratings.py

# Helper function to create dummy rating files
def create_dummy_rating_file(tmp_path: Path, position: int, data: list[dict]):
    ratings_dir = tmp_path / "ratings"
    ratings_dir.mkdir(exist_ok=True)
    file_path = ratings_dir / f"position_{position:03d}.csv"

    if not data: # Create empty file if no data
        file_path.touch()
        return file_path

    df = pd.DataFrame(data)
    # Ensure required columns for get_ranking even if not all are directly used by determine_next_duel logic being tested
    if "winner" not in df.columns and not df.empty: # if df is not empty but lacks winner/loser, it's a problem
        # This setup is for testing determine_next_duel which relies on get_ranking's output.
        # get_ranking produces elo, wins, losses, total_duels from winner/loser columns.
        # If we directly provide elo, we are bypassing get_ranking's calculation.
        # For these tests, we'll often directly create the output of get_ranking.
        pass

    df.to_csv(file_path, index=False)
    return file_path

# Helper function to generate ranking DataFrame as get_ranking would
def create_ranking_df(hronirs_data: list[dict]) -> pd.DataFrame:
    if not hronirs_data:
        return pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])

    df = pd.DataFrame(hronirs_data)
    # Ensure standard columns
    for col in ["uuid", "elo", "wins", "losses", "total_duels"]:
        if col not in df.columns:
            if col == "uuid": df[col] = [str(uuid.uuid4()) for _ in range(len(df))]
            elif col == "elo": df[col] = 1500
            elif col in ["wins", "losses", "total_duels"]: df[col] = 0

    df["elo"] = df["elo"].astype(float)
    df["wins"] = df["wins"].astype(int)
    df["losses"] = df["losses"].astype(int)
    df["total_duels"] = df["total_duels"].astype(int)
    return df.sort_values(by="elo", ascending=False).reset_index(drop=True)


@pytest.fixture(autouse=True)
def mock_get_ranking(monkeypatch):
    """
    Mocks ratings.get_ranking to return a controlled DataFrame,
    thus decoupling determine_next_duel from the complexities of get_ranking
    and CSV file interactions during these unit tests.
    """
    mock_ranking_df = pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])

    def _mock_get_ranking(position: int, base: Path | str = "ratings"):
        # This allows tests to set the data they want get_ranking to return
        return mock_ranking_df.copy()

    monkeypatch.setattr(ratings, "get_ranking", _mock_get_ranking)

    # This fixture will provide a way for tests to set the mock_ranking_df
    # e.g., by using another fixture or a helper within the test
# @pytest.fixture(autouse=True) # Removed autouse
@pytest.fixture
def mock_ratings_get_ranking(monkeypatch):
    """
    Mocks ratings.get_ranking. The fixture returns a setter function
    that tests can use to define the DataFrame data.
    """
    df_to_return_holder = [pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])]

    def _mock_get_ranking(position: int, base: Path | str = "ratings"):
        return df_to_return_holder[0].copy()

    monkeypatch.setattr(ratings, "get_ranking", _mock_get_ranking)

    def set_df_data(data_list: list[dict] | pd.DataFrame):
        if isinstance(data_list, pd.DataFrame):
            df_to_return_holder[0] = data_list
        else:
            df_to_return_holder[0] = create_ranking_df(data_list)
    return set_df_data


class TestDetermineNextDuel:

    def test_calibration_duel_new_hronir_vs_champion(self, tmp_path, mock_ratings_get_ranking):
        """
        Test 1: A new hrönir (0 duels) should duel the champion.
        """
        set_df_data = mock_ratings_get_ranking
        h1_uuid, h2_uuid, h3_uuid_new = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

        set_df_data([
            {"uuid": h1_uuid, "elo": 1600, "wins": 10, "losses": 2, "total_duels": 12}, # Champion
            {"uuid": h2_uuid, "elo": 1550, "wins": 8, "losses": 3, "total_duels": 11},
            {"uuid": h3_uuid_new, "elo": 1500, "wins": 0, "losses": 0, "total_duels": 0}, # New hrönir
        ])

        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")

        assert duel_info is not None
        assert duel_info["strategy"] == "calibration_duel"
        assert duel_info["hronir_A"] == h1_uuid
        assert duel_info["hronir_B"] == h3_uuid_new
        assert duel_info["position"] == 1

    def test_calibration_duel_multiple_new_hronirs(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h1_uuid_champ, h2_uuid_new_high_elo, h3_uuid_new_low_elo = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

        set_df_data([
            {"uuid": h1_uuid_champ, "elo": 1600, "wins": 10, "losses": 2, "total_duels": 12},
            {"uuid": h2_uuid_new_high_elo, "elo": 1510, "wins": 0, "losses": 0, "total_duels": 0},
            {"uuid": h3_uuid_new_low_elo, "elo": 1500, "wins": 0, "losses": 0, "total_duels": 0},
        ])

        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")

        assert duel_info is not None
        assert duel_info["strategy"] == "calibration_duel"
        assert duel_info["hronir_A"] == h1_uuid_champ
        assert duel_info["hronir_B"] == h2_uuid_new_high_elo

    def test_calibration_duel_champion_is_also_new(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h1_uuid_new_champ, h2_uuid_other_new = str(uuid.uuid4()), str(uuid.uuid4()),
        h3_uuid_established = str(uuid.uuid4())

        set_df_data([
            {"uuid": h1_uuid_new_champ, "elo": 1600, "wins": 0, "losses": 0, "total_duels": 0},
            {"uuid": h2_uuid_other_new, "elo": 1550, "wins": 0, "losses": 0, "total_duels": 0},
            {"uuid": h3_uuid_established, "elo": 1500, "wins": 5, "losses": 5, "total_duels": 10},
        ])

        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")
        assert duel_info is not None
        assert duel_info["strategy"] == "max_entropy_duel"
        assert set([duel_info["hronir_A"], duel_info["hronir_B"]]) == set([h1_uuid_new_champ, h2_uuid_other_new])


    def test_max_entropy_duel_no_new_hronirs(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h1, h2, h3, h4 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        set_df_data([
            {"uuid": h1, "elo": 1600, "wins": 10, "losses": 2, "total_duels": 12},
            {"uuid": h2, "elo": 1590, "wins": 8, "losses": 3, "total_duels": 11},
            {"uuid": h3, "elo": 1500, "wins": 5, "losses": 5, "total_duels": 10},
            {"uuid": h4, "elo": 1450, "wins": 2, "losses": 8, "total_duels": 10},
        ])

        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")

        assert duel_info is not None
        assert duel_info["strategy"] == "max_entropy_duel"
        assert set([duel_info["hronir_A"], duel_info["hronir_B"]]) == set([h1, h2])
        assert duel_info["position"] == 1

    def test_max_entropy_duel_chooses_highest_among_equal_elo_diffs(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h1, h2, h3, h4, h5, h6 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        set_df_data([
            {"uuid": h1, "elo": 1600, "wins": 10, "losses": 2, "total_duels": 12},
            {"uuid": h2, "elo": 1590, "wins": 8, "losses": 3, "total_duels": 11},
            {"uuid": h3, "elo": 1550, "wins": 5, "losses": 5, "total_duels": 10},
            {"uuid": h4, "elo": 1500, "wins": 7, "losses": 3, "total_duels": 10},
            {"uuid": h5, "elo": 1490, "wins": 6, "losses": 4, "total_duels": 10},
            {"uuid": h6, "elo": 1400, "wins": 2, "losses": 8, "total_duels": 10},
        ])

        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")

        assert duel_info is not None
        assert duel_info["strategy"] == "max_entropy_duel"
        assert set([duel_info["hronir_A"], duel_info["hronir_B"]]) == set([h1, h2])


    def test_edge_case_no_hronirs(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        set_df_data([])
        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")
        assert duel_info is None

    def test_edge_case_one_hronir(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        set_df_data([
            {"uuid": str(uuid.uuid4()), "elo": 1500, "wins": 0, "losses": 0, "total_duels": 0}
        ])
        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")
        assert duel_info is None

    def test_edge_case_two_hronirs_both_new(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h1_new, h2_new = str(uuid.uuid4()), str(uuid.uuid4())
        set_df_data([
            {"uuid": h1_new, "elo": 1510, "wins": 0, "losses": 0, "total_duels": 0},
            {"uuid": h2_new, "elo": 1500, "wins": 0, "losses": 0, "total_duels": 0},
        ])
        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")

        assert duel_info is not None
        assert duel_info["strategy"] == "max_entropy_duel"
        assert set([duel_info["hronir_A"], duel_info["hronir_B"]]) == set([h1_new, h2_new])

    def test_edge_case_two_hronirs_one_new_one_established(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h_established, h_new = str(uuid.uuid4()), str(uuid.uuid4())

        # Scenario 1: Established is champion
        set_df_data([
            {"uuid": h_established, "elo": 1550, "wins": 1, "losses": 0, "total_duels": 1},
            {"uuid": h_new, "elo": 1500, "wins": 0, "losses": 0, "total_duels": 0},
        ])
        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")
        assert duel_info is not None
        assert duel_info["strategy"] == "calibration_duel"
        assert duel_info["hronir_A"] == h_established
        assert duel_info["hronir_B"] == h_new

        # Scenario 2: New is champion
        set_df_data([
            {"uuid": h_new, "elo": 1550, "wins": 0, "losses": 0, "total_duels": 0},
            {"uuid": h_established, "elo": 1500, "wins": 1, "losses": 0, "total_duels": 1},
        ])
        duel_info_s2 = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")
        assert duel_info_s2 is not None
        assert duel_info_s2["strategy"] == "max_entropy_duel"
        assert set([duel_info_s2["hronir_A"], duel_info_s2["hronir_B"]]) == set([h_new, h_established])

    def test_no_total_duels_column_handled_gracefully(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h1_uuid, h2_uuid = str(uuid.uuid4()), str(uuid.uuid4())

        bad_ranking_df = pd.DataFrame([
            {"uuid": h1_uuid, "elo": 1600.0, "wins": 10, "losses": 2},
            {"uuid": h2_uuid, "elo": 1550.0, "wins": 8, "losses": 3},
        ])
        # Set the mock to return this specific DataFrame that lacks 'total_duels'
        set_df_data(bad_ranking_df.copy()) # Pass the DataFrame directly

        with pytest.raises(KeyError, match="total_duels"):
            ratings.determine_next_duel(position=1, base=tmp_path / "ratings")


    def test_entropy_calculation_is_correct_for_known_pair(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h1, h2 = str(uuid.uuid4()), str(uuid.uuid4())
        set_df_data([
            {"uuid": h1, "elo": 1600, "wins": 1, "losses": 0, "total_duels": 1},
            {"uuid": h2, "elo": 1500, "wins": 1, "losses": 0, "total_duels": 1},
        ])

        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")
        assert duel_info is not None
        assert duel_info["strategy"] == "max_entropy_duel"
        assert set([duel_info["hronir_A"], duel_info["hronir_B"]]) == set([h1, h2])
        assert duel_info["entropy"] == pytest.approx(0.9426, abs=1e-4)

    def test_entropy_zero_for_certain_outcome(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h1, h2 = str(uuid.uuid4()), str(uuid.uuid4())
        set_df_data([
            {"uuid": h1, "elo": 2400, "wins": 100, "losses": 0, "total_duels": 100},
            {"uuid": h2, "elo": 1200, "wins": 0, "losses": 100, "total_duels": 100},
        ])

        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")
        assert duel_info is not None
        assert duel_info["strategy"] == "max_entropy_duel"
        assert duel_info["entropy"] == pytest.approx(0.0114, abs=1e-4)

    def test_calibration_skipped_if_champion_is_the_only_new_hronir(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h_champ_new, h_established1, h_established2 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        set_df_data([
            {"uuid": h_champ_new, "elo": 1600, "wins": 0, "losses": 0, "total_duels": 0},
            {"uuid": h_established1, "elo": 1550, "wins": 5, "losses": 2, "total_duels": 7},
            {"uuid": h_established2, "elo": 1500, "wins": 3, "losses": 3, "total_duels": 6},
        ])

        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")
        assert duel_info is not None
        assert duel_info["strategy"] == "max_entropy_duel"
        assert set([duel_info["hronir_A"], duel_info["hronir_B"]]) == set([h_champ_new, h_established1])

# It might be good to also have tests for _calculate_elo_probability and _calculate_duel_entropy directly
# but the above tests cover their usage by determine_next_duel.

# To run these tests: pytest tests/test_duel_curation.py
# Ensure that conftest.py or a similar mechanism is not interfering if running all tests,
# or that necessary fixtures (like tmp_path) are available.
# These tests use monkeypatching for ratings.get_ranking.
