from hronir_encyclopedia import ratings, database


def test_get_ranking(tmp_path):
    base = tmp_path / "ratings"
    fork_dir = tmp_path / "forking"
    with database.open_database(ratings_dir=base, fork_dir=fork_dir) as conn:
        ratings.record_vote(1, "v1", "a", "b", conn=conn)
        ratings.record_vote(1, "v2", "a", "c", conn=conn)
        ratings.record_vote(1, "v3", "b", "a", conn=conn)

    df = ratings.get_ranking(1, base=base)
    assert list(df["chapter"]) == ["a", "b", "c"]
    row_a = df[df["chapter"] == "a"].iloc[0]
    row_b = df[df["chapter"] == "b"].iloc[0]
    row_c = df[df["chapter"] == "c"].iloc[0]
    assert row_a["wins"] == 2 and row_a["losses"] == 1
    assert row_b["wins"] == 1 and row_b["losses"] == 1
    assert row_c["wins"] == 0 and row_c["losses"] == 1
