from hronir_encyclopedia import database, ratings


def test_get_ranking(tmp_path):
    base = tmp_path / "ratings"
    fork_dir = tmp_path / "forking"
    with database.open_database(ratings_dir=base, fork_dir=fork_dir) as conn:
        ratings.record_vote(1, "v1", "a", "b", conn=conn)
        ratings.record_vote(1, "v2", "a", "c", conn=conn)
        ratings.record_vote(1, "v3", "b", "a", conn=conn)

    df = ratings.get_ranking(1, base=base)
    # Ranking should be sorted by Elo (desc), then wins (desc)
    # Expected order: a (Elo 1020), b (Elo 1005), c (Elo 990)
    assert list(df["uuid"]) == ["a", "b", "c"] # Order should remain a, b, c based on new Elo

    row_a = df[df["uuid"] == "a"].iloc[0]
    row_b = df[df["uuid"] == "b"].iloc[0]
    row_c = df[df["uuid"] == "c"].iloc[0]

    # Wins and losses remain the same
    assert row_a["wins"] == 2 and row_a["losses"] == 1
    # Expected Elo for 'a' is round(1500 + 32*(1-0.5) + 32*(1-0.523) + 32*(0-0.568)) = 1513
    assert row_a["elo"] == 1513

    assert row_b["wins"] == 1 and row_b["losses"] == 1
    # Expected Elo for 'b' is round(1500 + 32*(0-0.5) + 32*(1-0.432)) = 1502
    assert row_b["elo"] == 1502

    assert row_c["wins"] == 0 and row_c["losses"] == 1
    # Expected Elo for 'c' is round(1500 + 32*(0-0.477)) = 1485
    assert row_c["elo"] == 1485
