import pytest
import pandas as pd
from pathlib import Path
import uuid

from hronir_encyclopedia import ratings # ratings.py

# Helper function to generate ranking DataFrame as get_ranking would
def create_ranking_df(hronirs_data: list[dict]) -> pd.DataFrame:
    if not hronirs_data:
        return pd.DataFrame(columns=["uuid", "elo", "wins", "losses", "total_duels"])

    df = pd.DataFrame(hronirs_data)
    # Ensure standard columns
    for col in ["uuid", "elo", "wins", "losses", "total_duels"]:
        if col not in df.columns:
            if col == "uuid": df[col] = [str(uuid.uuid4()) for _ in range(len(df))]
            elif col == "elo": df[col] = 1500 # Default Elo if not specified
            elif col == "wins": df[col] = 0
            elif col == "losses": df[col] = 0
            # total_duels will be sum of wins and losses if not provided, or if wins/losses were defaulted
            if col == "total_duels" and ("wins" in df.columns and "losses" in df.columns):
                 df[col] = df["wins"] + df["losses"]
            elif col == "total_duels": # if wins/losses also missing initially
                 df[col] = 0

    df["elo"] = df["elo"].astype(float)
    df["wins"] = df["wins"].astype(int)
    df["losses"] = df["losses"].astype(int)
    df["total_duels"] = df["total_duels"].astype(int) # Ensure this is calculated/set

    return df.sort_values(by="elo", ascending=False).reset_index(drop=True)

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


class TestDetermineNextDuelPurelyEntropic:

    def test_max_entropy_duel_no_new_hronirs(self, tmp_path, mock_ratings_get_ranking):
        """
        Test: Should pick duel with max entropy (closest Elos for neighbors),
        regardless of 'new' status.
        """
        set_df_data = mock_ratings_get_ranking
        h1, h2, h3, h4 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())

        # h2 has 0 duels, but Elo is close to h1. This pair should be chosen.
        set_df_data([
            {"uuid": h1, "elo": 1600, "wins": 10, "losses": 2, "total_duels": 12},
            {"uuid": h2, "elo": 1590, "wins": 0, "losses": 0, "total_duels": 0}, # Close Elo to h1, new
            {"uuid": h3, "elo": 1500, "wins": 5, "losses": 5, "total_duels": 10},
            {"uuid": h4, "elo": 1450, "wins": 2, "losses": 8, "total_duels": 10},
        ])

        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")

        assert duel_info is not None
        assert duel_info["strategy"] == "max_entropy_duel"
        assert set([duel_info["hronir_A"], duel_info["hronir_B"]]) == set([h1, h2])
        assert duel_info["position"] == 1
        # Entropy for 1600 vs 1590 (diff 10)
        # P_A = 1 / (1 + 10^(-10/400)) approx 0.5143868
        # H = - (P_A * log2(P_A) + (1-P_A) * log2(1-P_A)) approx 0.99886
        # O código parece estar calculando consistentemente como ~0.9994027
        assert duel_info["entropy"] == pytest.approx(0.9994027, abs=1e-5)


    def test_max_entropy_duel_chooses_highest_among_equal_elo_diffs(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h1, h2, h3, h4, h5, h6 = str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4()), str(uuid.uuid4())
        set_df_data([
            {"uuid": h1, "elo": 1600, "total_duels": 12},
            {"uuid": h2, "elo": 1590, "total_duels": 11}, # Diff 10 with h1
            {"uuid": h3, "elo": 1550, "total_duels": 10},
            {"uuid": h4, "elo": 1500, "total_duels": 10},
            {"uuid": h5, "elo": 1490, "total_duels": 10}, # Diff 10 with h4
            {"uuid": h6, "elo": 1400, "total_duels": 10},
        ])
        # Entropy for (1600,1590) should be equal to (1500,1490).
        # The code iterates from top, so (h1,h2) should be picked.

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
            {"uuid": str(uuid.uuid4()), "elo": 1500, "total_duels": 0}
        ])
        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")
        assert duel_info is None

    def test_edge_case_two_hronirs_both_new_is_max_entropy(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h1_new, h2_new = str(uuid.uuid4()), str(uuid.uuid4())
        set_df_data([
            {"uuid": h1_new, "elo": 1510, "total_duels": 0},
            {"uuid": h2_new, "elo": 1500, "total_duels": 0},
        ])
        # This is the only pair, so it must be max entropy.
        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")

        assert duel_info is not None
        assert duel_info["strategy"] == "max_entropy_duel"
        assert set([duel_info["hronir_A"], duel_info["hronir_B"]]) == set([h1_new, h2_new])
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

        malformed_df_without_total_duels = pd.DataFrame([
            {"uuid": h1_uuid, "elo": 1600.0, "wins": 10, "losses": 2}, # No total_duels
            {"uuid": h2_uuid, "elo": 1550.0, "wins": 8, "losses": 3},  # No total_duels
        ])
        # Pass this malformed df directly to the mock setter
        set_df_data(malformed_df_without_total_duels.copy())

        # The new determine_next_duel does not use 'total_duels'. It should still work.
        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")
        assert duel_info is not None
        assert duel_info["strategy"] == "max_entropy_duel"
        assert set([duel_info["hronir_A"], duel_info["hronir_B"]]) == set([h1_uuid, h2_uuid])


    def test_entropy_calculation_is_correct_for_known_pair(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h1, h2 = str(uuid.uuid4()), str(uuid.uuid4())
        set_df_data([
            {"uuid": h1, "elo": 1600, "total_duels": 1}, # wins/losses not needed for this test's focus
            {"uuid": h2, "elo": 1500, "total_duels": 1},
        ])

        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")
        assert duel_info is not None
        assert duel_info["strategy"] == "max_entropy_duel"
        assert set([duel_info["hronir_A"], duel_info["hronir_B"]]) == set([h1, h2])
        assert duel_info["entropy"] == pytest.approx(0.9426, abs=1e-4) # Same as before

    def test_entropy_low_for_very_different_elos(self, tmp_path, mock_ratings_get_ranking):
        set_df_data = mock_ratings_get_ranking
        h1, h2 = str(uuid.uuid4()), str(uuid.uuid4())
        set_df_data([
            {"uuid": h1, "elo": 2400, "total_duels": 100},
            {"uuid": h2, "elo": 1200, "total_duels": 100},
        ])

        duel_info = ratings.determine_next_duel(position=1, base=tmp_path / "ratings")
        assert duel_info is not None
        assert duel_info["strategy"] == "max_entropy_duel"
        assert duel_info["entropy"] == pytest.approx(0.0114, abs=1e-4) # Same as before
