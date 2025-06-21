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
    assert list(df["uuid"]) == ["a", "b", "c"]

    row_a = df[df["uuid"] == "a"].iloc[0]
    row_b = df[df["uuid"] == "b"].iloc[0]
    row_c = df[df["uuid"] == "c"].iloc[0]

    assert row_a["wins"] == 2 and row_a["losses"] == 1
    assert row_a["elo"] == 1020

    assert row_b["wins"] == 1 and row_b["losses"] == 1
    assert row_b["elo"] == 1005

    assert row_c["wins"] == 0 and row_c["losses"] == 1
    assert row_c["elo"] == 990
